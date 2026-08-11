from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import quote

from migration_lantern_scan.i18n import category_label, confidence_label, severity_label
from migration_lantern_scan.models import Locale, ScanReport

_DISPLAY_CONTROL_PATTERN = re.compile(
    r"[\x00-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]"
)


def visible_text(value: object) -> str:
    """Render terminal and bidi controls visibly without changing ordinary Unicode text."""

    encoded = json.dumps(str(value), ensure_ascii=False)
    return _DISPLAY_CONTROL_PATTERN.sub(
        lambda match: f"\\u{ord(match.group(0)):04x}", encoded[1:-1]
    )


def markdown_code(value: object) -> str:
    """Render one safe inline-code value, including inside a Markdown table."""

    content = visible_text(value).replace("|", r"\|")
    runs = [len(match.group(0)) for match in re.finditer(r"`+", content)]
    fence = "`" * (max(runs, default=0) + 1)
    return f"{fence}{content}{fence}"


def markdown_text(value: object) -> str:
    """Escape untrusted text for a Markdown paragraph, list item, or link label."""

    return re.sub(r"([\\`*_{}\[\]<>|])", r"\\\1", visible_text(value))


class UnsafeReportContentError(RuntimeError):
    """Raised before source-controlled metadata could disclose a credential-like value."""


_CREDENTIAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<![A-Za-z0-9])sk-ant-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?<![A-Za-z0-9])sk-(?!ant-)[A-Za-z0-9_-]{16,}"),
    re.compile(
        r"(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{20,255}|"
        r"github_pat_[A-Za-z0-9_]{20,255})"
    ),
    re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(
        r"(?i)\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss)://"
        r"[^\s:/?#]+:[^@\s/?#]+@"
    ),
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|password|passwd|token|secret)\s*[:=]\s*"
        r"[A-Za-z0-9._~+/=-]{8,}"
    ),
)


def _contains_credential_like_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in _CREDENTIAL_PATTERNS)


def require_safe_report_metadata(report: ScanReport) -> None:
    """Fail closed if source-controlled report fields resemble credentials."""

    values = [report.target]
    for finding in report.findings:
        values.extend(
            [
                finding.finding_id,
                finding.path,
                finding.call,
                finding.matched_value,
            ]
        )
    for issue in report.issues:
        values.extend([issue.path, issue.detail])
    if any(_contains_credential_like_value(value) for value in values):
        raise UnsafeReportContentError(
            "Credential-like source metadata was blocked; no report content was emitted."
        )


def require_safe_output_directory(output_dir: Path) -> None:
    """Reject secret-like or control-shaped output paths before creating artifacts."""

    value = str(output_dir)
    if _contains_credential_like_value(value) or _DISPLAY_CONTROL_PATTERN.search(value):
        raise UnsafeReportContentError(
            "Unsafe output directory was blocked; no report artifact was created."
        )


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def render_markdown(report: ScanReport) -> str:
    require_safe_report_metadata(report)
    ja = report.locale == Locale.JA
    title = "# Migration Lantern Scan レポート" if ja else "# Migration Lantern Scan report"
    not_published = "公表なし" if ja else "Not published"
    english_table_header = (
        "| Severity | Provider | Type | Location | Deprecated | "
        "Recommended | Deadline | Confidence |"
    )
    lines = [
        title,
        "",
        (
            f"- 生成日時: `{report.generated_at.isoformat()}`"
            if ja
            else f"- Generated: `{report.generated_at.isoformat()}`"
        ),
        (
            f"- ルール確認日: `{report.registry_verified_on}`"
            if ja
            else f"- Rules verified: `{report.registry_verified_on}`"
        ),
        (
            f"- Pythonファイル: `{report.files_scanned}`件"
            if ja
            else f"- Python files: `{report.files_scanned}`"
        ),
        (f"- 検出: `{len(report.findings)}`件" if ja else f"- Findings: `{len(report.findings)}`"),
        "",
        "## 影響箇所" if ja else "## Impacted locations",
        "",
        (
            "| 深刻度 | 提供元 | 種別 | 場所 | 非推奨対象 | 推奨先 | 期限 | 確度 |"
            if ja
            else english_table_header
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for finding in report.findings:
        deadline = finding.deadline.isoformat() if finding.deadline else not_published
        lines.append(
            f"| {severity_label(finding.severity.value, report.locale)} | "
            f"{finding.provider.value} | {category_label(finding.category, report.locale)} | "
            f"{markdown_code(f'{finding.path}:{finding.line}:{finding.column}')} | "
            f"{markdown_code(finding.deprecated_target)} | "
            f"{markdown_code(finding.recommended_target)} | "
            f"{deadline} | {confidence_label(finding.confidence, report.locale)} |"
        )
    if not report.findings:
        empty = "一致なし" if ja else "No matching deprecations"
        lines.append(f"| - | - | - | {empty} | - | - | - | - |")
    lines.extend(["", "## 公式根拠" if ja else "## Official evidence", ""])
    sources: dict[str, tuple[str, str]] = {}
    for finding in report.findings:
        for source in finding.evidence:
            sources[source.url] = (source.title, source.checked_on.isoformat())
    lines.extend(
        f"- [{markdown_text(title)}]({quote(url, safe=':/?&=%#._~-')}) - "
        f"{'確認日' if ja else 'checked'} {checked}"
        for url, (title, checked) in sources.items()
    )
    if not sources:
        lines.append("- 該当なし" if ja else "- None required; no rule matched.")
    context = list(
        dict.fromkeys(
            finding.migration_note
            for finding in report.findings
            if finding.migration_note is not None
        )
    )
    if context:
        lines.extend(["", "## 移行上の注記" if ja else "## Migration context", ""])
        lines.extend(f"- {markdown_text(note)}" for note in context)
    lines.extend(["", "## 要確認事項" if ja else "## Review notes", ""])
    for issue in report.issues:
        location = f"{issue.path}:{issue.line}" if issue.line else issue.path
        lines.append(f"- {markdown_code(location)}: {markdown_text(issue.detail)}")
    if not report.issues:
        lines.append("- 追加の解析問題はありません。" if ja else "- No additional parse issues.")
    lines.extend(
        [
            "",
            "## 制約" if ja else "## Limitations",
            "",
            (
                "Migration Lantern Scanはコードを実行せず静的に解析します。"
                "動的設定、ラッパー、別名、"
                "クラウド固有IDを見逃す可能性があり、`要確認`（JSONでは`review`）は"
                "provider bindingを証明できない一致です。"
                if ja
                else "Migration Lantern Scan parses source without executing it. "
                "Dynamic configuration, "
                "wrappers, aliases, and cloud-specific IDs can be missed; `review` findings are "
                "matches whose provider type is not proven."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(report: ScanReport, output_dir: Path) -> tuple[Path, Path]:
    require_safe_report_metadata(report)
    require_safe_output_directory(output_dir)
    json_path = output_dir / "migration-lantern-scan.json"
    markdown_path = output_dir / "migration-lantern-scan.md"
    atomic_write(json_path, report.model_dump_json(indent=2, ensure_ascii=True) + "\n")
    atomic_write(markdown_path, render_markdown(report))
    return json_path, markdown_path
