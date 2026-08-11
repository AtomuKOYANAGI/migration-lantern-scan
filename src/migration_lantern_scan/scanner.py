from __future__ import annotations

import ast
import os
import stat
from collections.abc import Collection
from contextlib import suppress
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import libcst as cst
from libcst.metadata import (
    MetadataWrapper,
    ParentNodeProvider,
    PositionProvider,
    QualifiedName,
    QualifiedNameProvider,
    QualifiedNameSource,
    ScopeProvider,
)
from libcst.metadata.scope_provider import Assignment

from migration_lantern_scan import __version__
from migration_lantern_scan.models import (
    Finding,
    Locale,
    Provider,
    PublicRegistry,
    PublicRule,
    ScanIssue,
    ScanReport,
)
from migration_lantern_scan.registry import registry_digest

EXCLUDED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".migration-lantern",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
    "site-packages",
}
MAX_FILES = 5_000
MAX_FILE_BYTES = 1_000_000
MAX_METADATA_ENTRIES = 50_000
MAX_TOTAL_BYTES = 50_000_000
PROVIDER_CONSTRUCTORS: dict[Provider, frozenset[str]] = {
    Provider.OPENAI: frozenset({"openai.OpenAI", "openai.AsyncOpenAI"}),
    Provider.ANTHROPIC: frozenset({"anthropic.Anthropic", "anthropic.AsyncAnthropic"}),
}
CUSTOM_ENDPOINT_KEYWORDS = {
    "api_base",
    "api_type",
    "api_version",
    "azure_endpoint",
    "base_url",
    "default_headers",
    "default_query",
    "http_client",
    "transport",
    "websocket_base_url",
}


def read_source(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def call_components(node: cst.BaseExpression) -> tuple[str, ...] | None:
    if isinstance(node, cst.Name):
        return (node.value,)
    if isinstance(node, cst.Attribute):
        parent = call_components(node.value)
        return (*parent, node.attr.value) if parent else None
    return None


def call_name(node: cst.BaseExpression) -> str | None:
    components = call_components(node)
    return ".".join(components) if components else None


def call_root_name(node: cst.BaseExpression) -> cst.Name | None:
    while isinstance(node, cst.Attribute):
        node = node.value
    return node if isinstance(node, cst.Name) else None


def literal_string(node: cst.BaseExpression) -> str | None:
    if not isinstance(node, cst.SimpleString):
        return None
    try:
        value = ast.literal_eval(node.value)
    except (SyntaxError, ValueError):
        return None
    return value if isinstance(value, str) else None


def keyword_argument(call: cst.Call, keyword: str) -> cst.Arg | None:
    for argument in call.args:
        if isinstance(argument.keyword, cst.Name) and argument.keyword.value == keyword:
            return argument
    return None


def _matches_path(components: tuple[str, ...], rule: PublicRule) -> tuple[str, ...] | None:
    matches: list[tuple[str, ...]] = []
    for text in rule.call_paths:
        expected = tuple(text.split("."))
        if rule.call_match == "exact":
            if components == expected:
                matches.append(expected)
            elif (
                len(expected) > 1
                and expected[0] == rule.provider.value
                and len(components) == len(expected)
                and components[1:] == expected[1:]
            ):
                # Preserve detection through an import alias or same-shaped local gateway.
                # Binding analysis decides whether this is high-confidence or review-only.
                matches.append(expected)
        if (
            rule.call_match == "suffix"
            and len(components) >= len(expected)
            and components[-len(expected) :] == expected
        ):
            matches.append(expected)
    return max(matches, key=len) if matches else None


def _confidence(
    components: tuple[str, ...],
    matched_path: tuple[str, ...],
    rule: PublicRule,
    known_receiver_providers: dict[str, frozenset[Provider]],
    proven_provider: Provider | None,
) -> Literal["high", "review"] | None:
    if proven_provider is not None:
        if proven_provider != rule.provider:
            return None
        if rule.call_match == "suffix" and len(components) != len(matched_path) + 1:
            return None
        return "high"
    if not rule.receiver_names:
        return "review"
    if len(components) <= len(matched_path):
        return None
    receiver = components[-len(matched_path) - 1]
    if receiver in rule.receiver_names:
        return "review"
    configured_providers = known_receiver_providers.get(receiver, frozenset())
    if configured_providers and rule.provider not in configured_providers:
        return None
    if len(components) == len(matched_path) + 1:
        return "review"
    return None


def _imported_provider(
    names: Collection[QualifiedName],
    trusted_providers: frozenset[Provider],
) -> Provider | None:
    """Return a provider only for one unambiguous provider-module import binding."""

    if not names or any(name.source is not QualifiedNameSource.IMPORT for name in names):
        return None
    providers = {
        provider
        for provider in trusted_providers
        if all(name.name == provider.value for name in names)
    }
    return next(iter(providers)) if len(providers) == 1 else None


def _constructor_provider(
    names: Collection[QualifiedName],
    trusted_providers: frozenset[Provider],
) -> Provider | None:
    """Return a provider for an unambiguous import of an approved SDK constructor."""

    if not names or any(name.source is not QualifiedNameSource.IMPORT for name in names):
        return None
    providers = {
        provider
        for provider in trusted_providers
        if all(name.name in PROVIDER_CONSTRUCTORS[provider] for name in names)
    }
    return next(iter(providers)) if len(providers) == 1 else None


def _lifecycle(
    rule: PublicRule, as_of: date
) -> Literal["scheduled", "retired", "legacy-no-deadline"]:
    if rule.deadline is None:
        return "legacy-no-deadline"
    return "retired" if as_of >= rule.deadline else "scheduled"


class RuleVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (
        ParentNodeProvider,
        PositionProvider,
        QualifiedNameProvider,
        ScopeProvider,
    )

    def __init__(
        self,
        *,
        relative_path: str,
        rules: list[PublicRule],
        as_of: date,
        locale: Locale,
        trusted_providers: frozenset[Provider],
    ) -> None:
        self.relative_path = relative_path
        self.rules = rules
        self.as_of = as_of
        self.locale = locale
        self.trusted_providers = trusted_providers
        receiver_providers: dict[str, set[Provider]] = {}
        for rule in rules:
            for receiver in rule.receiver_names:
                receiver_providers.setdefault(receiver, set()).add(rule.provider)
        self.known_receiver_providers = {
            receiver: frozenset(providers) for receiver, providers in receiver_providers.items()
        }
        self.findings: list[Finding] = []
        self.issues: list[ScanIssue] = []
        self._issue_keys: set[tuple[int, int, str]] = set()
        self._module_overrides: set[Provider] = set()
        self._receiver_overrides: set[str] = set()

    def _local_constructor_provider(self, root: cst.Name) -> Provider | None:
        names = self.get_metadata(QualifiedNameProvider, root, set())
        if not names or any(name.source is not QualifiedNameSource.LOCAL for name in names):
            return None
        scope = self.get_metadata(ScopeProvider, root)
        if scope is None:
            return None
        assignments = list(scope[root.value])
        if len(assignments) != 1:
            return None
        binding = assignments[0]
        if not isinstance(binding, Assignment):
            return None
        target = binding.node
        parent = self.get_metadata(ParentNodeProvider, target, None)
        value: cst.BaseExpression | None = None
        if isinstance(parent, cst.AssignTarget):
            assignment = self.get_metadata(ParentNodeProvider, parent, None)
            if (
                isinstance(assignment, cst.Assign)
                and len(assignment.targets) == 1
                and assignment.targets[0] is parent
            ):
                value = assignment.value
        elif isinstance(parent, cst.AnnAssign) and parent.target is target:
            value = parent.value
        if not isinstance(value, cst.Call):
            return None
        for argument in value.args:
            if argument.star or argument.keyword is None:
                return None
            if argument.keyword.value in CUSTOM_ENDPOINT_KEYWORDS:
                return None
        constructor_names = self.get_metadata(QualifiedNameProvider, value.func, set())
        return _constructor_provider(constructor_names, self.trusted_providers)

    def _record_endpoint_override(self, target: cst.BaseExpression) -> None:
        components = call_components(target)
        if components is None or len(components) != 2:
            return
        if components[1] not in CUSTOM_ENDPOINT_KEYWORDS:
            return
        root = call_root_name(target)
        if root is None:
            return
        provider = _imported_provider(
            self.get_metadata(QualifiedNameProvider, root, set()),
            self.trusted_providers,
        )
        if provider is not None:
            self._module_overrides.add(provider)
        elif self._local_constructor_provider(root) is not None:
            self._receiver_overrides.add(root.value)

    def visit_Assign(self, node: cst.Assign) -> bool:
        for target in node.targets:
            self._record_endpoint_override(target.target)
        return True

    def visit_AnnAssign(self, node: cst.AnnAssign) -> bool:
        self._record_endpoint_override(node.target)
        return True

    def visit_AugAssign(self, node: cst.AugAssign) -> bool:
        self._record_endpoint_override(node.target)
        return True

    def _provider_binding(self, call: cst.Call) -> Provider | None:
        root = call_root_name(call.func)
        if root is None:
            return None
        names = self.get_metadata(QualifiedNameProvider, root, set())
        imported = _imported_provider(names, self.trusted_providers)
        if imported is not None:
            return None if imported in self._module_overrides else imported
        if root.value in self._receiver_overrides:
            return None
        return self._local_constructor_provider(root)

    def visit_Call(self, node: cst.Call) -> bool:
        components = call_components(node.func)
        qualified = call_name(node.func)
        if components is None or qualified is None:
            return True
        call_position = self.get_metadata(PositionProvider, node).start
        proven_provider = self._provider_binding(node)
        for rule in self.rules:
            matched_path = _matches_path(components, rule)
            if matched_path is None:
                continue
            confidence = _confidence(
                components,
                matched_path,
                rule,
                self.known_receiver_providers,
                proven_provider,
            )
            if confidence is None:
                continue
            matched_value = qualified
            value_position = call_position
            if rule.match_kind == "model_argument":
                if rule.keyword is None:
                    continue
                argument = keyword_argument(node, rule.keyword)
                if argument is None:
                    continue
                value = literal_string(argument.value)
                if value is None:
                    key = (call_position.line, call_position.column, rule.rule_id)
                    if key not in self._issue_keys:
                        self._issue_keys.add(key)
                        detail = (
                            "A matching call uses a dynamic model value; review manually"
                            if self.locale == Locale.EN
                            else "一致した呼び出しのモデル値は動的です。手動確認してください。"
                        )
                        self.issues.append(
                            ScanIssue(
                                path=self.relative_path,
                                kind="dynamic_value",
                                detail=detail,
                                line=call_position.line,
                            )
                        )
                    continue
                if value not in rule.deprecated_values:
                    continue
                matched_value = value
                value_position = self.get_metadata(PositionProvider, argument.value).start
            self.findings.append(
                Finding(
                    finding_id=(
                        f"{rule.rule_id}:{self.relative_path}:"
                        f"{value_position.line}:{value_position.column + 1}"
                    ),
                    rule_id=rule.rule_id,
                    provider=rule.provider,
                    category=rule.category,
                    severity=rule.severity,
                    confidence=confidence,
                    path=self.relative_path,
                    line=value_position.line,
                    column=value_position.column + 1,
                    call=qualified,
                    matched_value=matched_value,
                    deprecated_target=rule.deprecated_target,
                    recommended_target=rule.recommended_target,
                    replacement_at_announcement=rule.replacement_at_announcement,
                    migration_note=(
                        rule.migration_note_en
                        if self.locale == Locale.EN
                        else rule.migration_note_ja
                    ),
                    announced_on=rule.announced_on,
                    deadline=rule.deadline,
                    lifecycle_status=_lifecycle(rule, self.as_of),
                    evidence=rule.evidence,
                )
            )
        return True


def discover_python_files(
    root: Path, locale: Locale
) -> tuple[list[Path], list[ScanIssue], frozenset[Provider]]:
    files: list[Path] = []
    issues: list[ScanIssue] = []
    shadowed: set[Provider] = set()
    limit_hit = False
    metadata_entries = 0
    total_bytes = 0

    def record_walk_error(error: OSError) -> None:
        relative = "."
        if error.filename:
            with suppress(OSError, ValueError):
                relative = Path(error.filename).resolve(strict=False).relative_to(root).as_posix()
        detail = (
            "directory metadata could not be inspected safely"
            if locale == Locale.EN
            else "ディレクトリ情報を安全に確認できませんでした。"
        )
        issues.append(ScanIssue(path=relative, kind="read_error", detail=detail))

    for current_text, directory_names, file_names in os.walk(
        root,
        topdown=True,
        onerror=record_walk_error,
        followlinks=False,
    ):
        current = Path(current_text)
        directory_names.sort(key=lambda value: (value.casefold(), value))
        file_names.sort(key=lambda value: (value.casefold(), value))

        retained_directories: list[str] = []
        for directory_name in directory_names:
            if directory_name in EXCLUDED_DIRECTORIES:
                continue
            metadata_entries += 1
            if metadata_entries > MAX_METADATA_ENTRIES:
                detail = (
                    f"repository metadata exceeds the {MAX_METADATA_ENTRIES}-entry limit"
                    if locale == Locale.EN
                    else f"リポジトリのメタデータが{MAX_METADATA_ENTRIES}件の上限を超えています。"
                )
                issues.append(ScanIssue(path=".", kind="limit_exceeded", detail=detail))
                return files, issues, frozenset(shadowed)
            candidate = current / directory_name
            relative = candidate.relative_to(root).as_posix()
            try:
                metadata = candidate.lstat()
            except OSError:
                detail = (
                    "directory metadata could not be inspected safely"
                    if locale == Locale.EN
                    else "ディレクトリ情報を安全に確認できませんでした。"
                )
                issues.append(ScanIssue(path=relative, kind="read_error", detail=detail))
                continue
            if stat.S_ISLNK(metadata.st_mode):
                for provider in Provider:
                    if directory_name.casefold() == provider.value.casefold():
                        shadowed.add(provider)
                detail = (
                    "symbolic-link Python path was not scanned; scan is incomplete"
                    if locale == Locale.EN
                    else "シンボリックリンクのPythonパスは検査していないため、検査は不完全です。"
                )
                issues.append(ScanIssue(path=relative, kind="unsafe_path", detail=detail))
                continue
            if not stat.S_ISDIR(metadata.st_mode):
                detail = (
                    "non-directory path was not traversed; scan is incomplete"
                    if locale == Locale.EN
                    else "ディレクトリではないパスは探索していないため、検査は不完全です。"
                )
                issues.append(ScanIssue(path=relative, kind="unsafe_path", detail=detail))
                continue
            retained_directories.append(directory_name)
        directory_names[:] = retained_directories

        for file_name in file_names:
            metadata_entries += 1
            if metadata_entries > MAX_METADATA_ENTRIES:
                detail = (
                    f"repository metadata exceeds the {MAX_METADATA_ENTRIES}-entry limit"
                    if locale == Locale.EN
                    else f"リポジトリのメタデータが{MAX_METADATA_ENTRIES}件の上限を超えています。"
                )
                issues.append(ScanIssue(path=".", kind="limit_exceeded", detail=detail))
                return files, issues, frozenset(shadowed)
            if not file_name.casefold().endswith(".py"):
                continue
            path = current / file_name
            relative_path = path.relative_to(root)
            for provider in Provider:
                module_name = provider.value.casefold()
                if file_name.casefold() == f"{module_name}.py" or (
                    file_name.casefold() == "__init__.py" and current.name.casefold() == module_name
                ):
                    shadowed.add(provider)
            try:
                metadata = path.lstat()
                if stat.S_ISLNK(metadata.st_mode):
                    detail = (
                        "symbolic-link Python path was not scanned; scan is incomplete"
                        if locale == Locale.EN
                        else (
                            "シンボリックリンクのPythonパスは検査していないため、"
                            + "検査は不完全です。"
                        )
                    )
                    issues.append(
                        ScanIssue(
                            path=relative_path.as_posix(),
                            kind="unsafe_path",
                            detail=detail,
                        )
                    )
                    continue
                if not stat.S_ISREG(metadata.st_mode):
                    detail = (
                        "non-regular Python path was not read; scan is incomplete"
                        if locale == Locale.EN
                        else (
                            "通常ファイルではないPythonパスは読み取っていないため、"
                            + "検査は不完全です。"
                        )
                    )
                    issues.append(
                        ScanIssue(
                            path=relative_path.as_posix(),
                            kind="unsafe_path",
                            detail=detail,
                        )
                    )
                    continue
                resolved = path.resolve(strict=True)
                resolved.relative_to(root)
                size = metadata.st_size
            except (OSError, ValueError):
                detail = (
                    "file metadata could not be inspected safely"
                    if locale == Locale.EN
                    else "ファイル情報を安全に確認できませんでした。"
                )
                issues.append(
                    ScanIssue(path=relative_path.as_posix(), kind="read_error", detail=detail)
                )
                continue
            if size > MAX_FILE_BYTES:
                detail = (
                    f"file exceeds the {MAX_FILE_BYTES}-byte limit"
                    if locale == Locale.EN
                    else f"ファイルが{MAX_FILE_BYTES}バイトの上限を超えています。"
                )
                issues.append(
                    ScanIssue(path=relative_path.as_posix(), kind="limit_exceeded", detail=detail)
                )
                continue
            if len(files) >= MAX_FILES:
                detail = (
                    f"scan stopped at {MAX_FILES} Python files"
                    if locale == Locale.EN
                    else f"Pythonファイル{MAX_FILES}件で検査を停止しました。"
                )
                issues.append(ScanIssue(path=".", kind="limit_exceeded", detail=detail))
                limit_hit = True
                break
            if total_bytes + size > MAX_TOTAL_BYTES:
                detail = (
                    f"scan exceeds the {MAX_TOTAL_BYTES}-byte aggregate Python source limit"
                    if locale == Locale.EN
                    else f"Pythonソースの合計が{MAX_TOTAL_BYTES}バイトの上限を超えています。"
                )
                issues.append(ScanIssue(path=".", kind="limit_exceeded", detail=detail))
                limit_hit = True
                break
            total_bytes += size
            files.append(resolved)
        if limit_hit:
            directory_names[:] = []
            break
    return files, issues, frozenset(shadowed)


def scan_repository(
    root: Path,
    registry: PublicRegistry,
    *,
    locale: Locale = Locale.EN,
    as_of: date | None = None,
) -> ScanReport:
    resolved_root = root.resolve(strict=True)
    if not resolved_root.is_dir():
        raise ValueError(f"not a directory: {root}")
    scan_date = as_of or date.today()
    paths, issues, shadowed_providers = discover_python_files(resolved_root, locale)
    incomplete_inventory = any(
        issue.kind in {"read_error", "limit_exceeded", "unsafe_path"} for issue in issues
    )
    trusted_providers = (
        frozenset() if incomplete_inventory else frozenset(set(Provider) - set(shadowed_providers))
    )
    findings: list[Finding] = []
    scanned = 0
    for path in paths:
        relative = path.relative_to(resolved_root).as_posix()
        try:
            source = read_source(path)
        except (OSError, UnicodeError):
            detail = (
                "file could not be read as UTF-8"
                if locale == Locale.EN
                else "ファイルをUTF-8として読み取れませんでした。"
            )
            issues.append(ScanIssue(path=relative, kind="read_error", detail=detail))
            continue
        try:
            module = cst.parse_module(source)
        except cst.ParserSyntaxError as exc:
            issues.append(
                ScanIssue(
                    path=relative,
                    kind="parse_error",
                    detail=(
                        "Python syntax could not be parsed"
                        if locale == Locale.EN
                        else "Python構文を解析できませんでした。"
                    ),
                    line=getattr(exc, "raw_line", None),
                )
            )
            continue
        scanned += 1
        visitor = RuleVisitor(
            relative_path=relative,
            rules=registry.rules,
            as_of=scan_date,
            locale=locale,
            trusted_providers=trusted_providers,
        )
        MetadataWrapper(module).visit(visitor)
        findings.extend(visitor.findings)
        issues.extend(visitor.issues)
    findings.sort(key=lambda finding: (finding.path, finding.line, finding.rule_id))
    issues.sort(key=lambda issue: (issue.path, issue.line or 0, issue.kind))
    return ScanReport(
        tool_version=__version__,
        generated_at=datetime.now(UTC),
        locale=locale,
        target=resolved_root.name,
        as_of=scan_date,
        registry_verified_on=registry.verified_on,
        registry_sha256=registry_digest(registry),
        files_scanned=scanned,
        findings=findings,
        issues=issues,
    )
