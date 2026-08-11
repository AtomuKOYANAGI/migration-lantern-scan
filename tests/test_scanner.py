import os
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path

import pytest

from migration_lantern_scan import scanner as scanner_module
from migration_lantern_scan.models import Locale, ScanIssue
from migration_lantern_scan.registry import load_registry
from migration_lantern_scan.reporting import (
    markdown_code,
    render_markdown,
    visible_text,
    write_reports,
)
from migration_lantern_scan.scanner import scan_repository


def test_detects_model_sdk_and_endpoint_without_executing_code(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "import openai\n"
        "def run(openai_client, anthropic_client):\n"
        "    openai.ChatCompletion.create(model='anything', messages=[])\n"
        "    openai_client.responses.create(model='gpt-5.2-chat-latest', input='x')\n"
        "    anthropic_client.messages.create("
        "model='claude-opus-4-1-20250805', max_tokens=1, messages=[])\n"
        "    return anthropic_client.completions.create("
        "model='claude-2.1', max_tokens_to_sample=1, prompt='x')\n",
        encoding="utf-8",
    )

    report = scan_repository(
        tmp_path,
        load_registry(),
        locale=Locale.EN,
        as_of=date(2026, 8, 10),
    )

    assert len(report.findings) == 4
    assert {finding.category for finding in report.findings} == {
        "model",
        "sdk_syntax",
        "endpoint",
    }
    assert all(finding.evidence for finding in report.findings)
    assert any(finding.deadline == date(2026, 8, 10) for finding in report.findings)
    assert all(finding.lifecycle_status != "scheduled" for finding in report.findings)
    anthropic_model = next(
        finding
        for finding in report.findings
        if finding.rule_id == "anthropic-claude-opus-4-1-retirement"
    )
    assert anthropic_model.replacement_at_announcement == "claude-opus-4-8"
    assert "current official migration guide" in (anthropic_model.migration_note or "")


def test_comments_strings_and_similar_suffixes_do_not_match(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "# openai.ChatCompletion.create(model='gpt-5.2-chat-latest')\n"
        'TEXT = "gpt-5.2-chat-latest"\n'
        "def run(fake):\n"
        "    return fake.notresponses.create(model='gpt-5.2-chat-latest')\n",
        encoding="utf-8",
    )
    report = scan_repository(tmp_path, load_registry())
    assert not report.findings


def test_generic_legacy_endpoint_receiver_is_review_confidence(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def run(client):\n    return client.completions.create(model='claude-2.1', prompt='x')\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, load_registry())

    assert len(report.findings) == 1
    assert report.findings[0].rule_id == "anthropic-legacy-text-completions-endpoint"
    assert report.findings[0].confidence == "review"


def test_openai_chat_completions_is_not_an_anthropic_endpoint(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def run(openai_client):\n"
        "    return openai_client.chat.completions.create("
        "model='gpt-5.6-sol', messages=[])\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, load_registry())

    assert not report.findings


def test_known_openai_receiver_is_not_an_anthropic_legacy_endpoint(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def run(openai_client):\n"
        "    return openai_client.completions.create(model='custom', prompt='x')\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, load_registry())

    assert not report.findings


def test_same_named_local_gateways_are_review_only(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "class Gateway:\n"
        "    pass\n"
        "openai = Gateway()\n"
        "openai_client = Gateway()\n"
        "anthropic_client = Gateway()\n"
        "openai.ChatCompletion.create(model='x')\n"
        "openai_client.responses.create(model='gpt-5.2-chat-latest', input='x')\n"
        "anthropic_client.messages.create("
        "model='claude-opus-4-1', max_tokens=1, messages=[])\n"
        "anthropic_client.completions.create(model='claude-2.1', prompt='x')\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, load_registry())

    assert len(report.findings) == 4
    assert {finding.confidence for finding in report.findings} == {"review"}


def test_local_provider_modules_downgrade_imports_to_review(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "openai.py").write_text("class ChatCompletion: ...\n", encoding="utf-8")
    local_anthropic = source_root / "anthropic"
    local_anthropic.mkdir()
    (local_anthropic / "__init__.py").write_text("class Anthropic: ...\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "import openai\n"
        "from anthropic import Anthropic\n"
        "anthropic_client = Anthropic()\n"
        "openai.ChatCompletion.create(model='x')\n"
        "anthropic_client.messages.create("
        "model='claude-opus-4-1', max_tokens=1, messages=[])\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, load_registry())

    assert len(report.findings) == 2
    assert {finding.confidence for finding in report.findings} == {"review"}


def test_rebound_provider_and_client_bindings_are_review_only(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "import openai\n"
        "from anthropic import Anthropic\n"
        "openai = local_gateway\n"
        "client = Anthropic()\n"
        "client = local_gateway\n"
        "openai.ChatCompletion.create(model='x')\n"
        "client.messages.create(model='claude-opus-4-1', max_tokens=1, messages=[])\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, load_registry())

    assert len(report.findings) == 2
    assert {finding.confidence for finding in report.findings} == {"review"}


def test_import_aliases_and_sdk_constructors_prove_provider_bindings(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "import openai as openai_sdk\n"
        "from openai import OpenAI\n"
        "import anthropic\n"
        "from anthropic import AsyncAnthropic as ClaudeClient\n"
        "openai_client = OpenAI()\n"
        "anthropic_client = anthropic.Anthropic()\n"
        "async_anthropic_client = ClaudeClient()\n"
        "openai_sdk.ChatCompletion.create(model='x')\n"
        "openai_client.responses.create(model='gpt-5.2-chat-latest', input='x')\n"
        "anthropic_client.messages.create("
        "model='claude-opus-4-1', max_tokens=1, messages=[])\n"
        "async_anthropic_client.completions.create(model='claude-2.1', prompt='x')\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, load_registry())

    assert len(report.findings) == 4
    assert {finding.confidence for finding in report.findings} == {"high"}


def test_proven_other_provider_suppresses_same_named_receiver(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "from anthropic import Anthropic\n"
        "openai_client = Anthropic()\n"
        "openai_client.responses.create(model='gpt-5.2-chat-latest', input='x')\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, load_registry())

    assert not report.findings


def test_proven_provider_does_not_make_nested_suffix_chains_provider_calls(
    tmp_path: Path,
) -> None:
    (tmp_path / "app.py").write_text(
        "import openai\n"
        "from anthropic import Anthropic\n"
        "client = Anthropic()\n"
        "openai.foo.responses.create(model='gpt-5.2-chat-latest', input='x')\n"
        "client.foo.messages.create(model='claude-opus-4-1', max_tokens=1, messages=[])\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, load_registry())

    assert not report.findings


@pytest.mark.parametrize(
    ("constructor", "arguments", "call"),
    [
        (
            "from openai import OpenAI",
            "base_url='https://gateway.invalid/v1'",
            "client.responses.create(model='gpt-5.2-chat-latest', input='x')",
        ),
        (
            "from openai import OpenAI",
            "default_headers={'x-provider': 'gateway'}",
            "client.responses.create(model='gpt-5.2-chat-latest', input='x')",
        ),
        (
            "from anthropic import Anthropic",
            "http_client=custom_transport",
            "client.messages.create(model='claude-opus-4-1', max_tokens=1, messages=[])",
        ),
    ],
)
def test_explicit_constructor_endpoint_or_transport_override_is_review_only(
    tmp_path: Path,
    constructor: str,
    arguments: str,
    call: str,
) -> None:
    (tmp_path / "app.py").write_text(
        f"{constructor}\nclient = {constructor.rsplit(' ', 1)[-1]}({arguments})\n{call}\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, load_registry())

    assert len(report.findings) == 1
    assert report.findings[0].confidence == "review"


@pytest.mark.parametrize("attribute", ["api_base", "base_url"])
def test_explicit_module_endpoint_override_is_review_only(tmp_path: Path, attribute: str) -> None:
    (tmp_path / "app.py").write_text(
        "import openai\n"
        f"openai.{attribute} = 'https://gateway.invalid/v1'\n"
        "openai.ChatCompletion.create(model='x')\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, load_registry())

    assert len(report.findings) == 1
    assert report.findings[0].confidence == "review"


@pytest.mark.parametrize(
    "override",
    [
        "client.base_url = 'https://gateway.invalid/v1'",
        "client.default_headers: dict[str, str] = {'x-provider': 'gateway'}",
        "client.default_headers |= {'x-provider': 'gateway'}",
        "client.http_client = custom_transport",
    ],
)
def test_explicit_client_endpoint_or_transport_override_is_review_only(
    tmp_path: Path, override: str
) -> None:
    (tmp_path / "app.py").write_text(
        "from openai import OpenAI\n"
        "client = OpenAI()\n"
        f"{override}\n"
        "client.responses.create(model='gpt-5.2-chat-latest', input='x')\n",
        encoding="utf-8",
    )

    report = scan_repository(tmp_path, load_registry())

    assert len(report.findings) == 1
    assert report.findings[0].confidence == "review"


def test_advertised_after_demo_is_clean() -> None:
    target = Path(__file__).resolve().parents[1] / "demo" / "after"

    report = scan_repository(target, load_registry())

    assert not report.findings
    assert not report.issues


def test_dynamic_model_and_invalid_python_are_review_issues(tmp_path: Path) -> None:
    (tmp_path / "dynamic.py").write_text(
        "def run(openai_client, model):\n"
        "    return openai_client.responses.create(model=model, input='x')\n",
        encoding="utf-8",
    )
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    report = scan_repository(tmp_path, load_registry(), locale=Locale.JA)
    assert not report.findings
    assert {issue.kind for issue in report.issues} == {"dynamic_value", "parse_error"}
    assert any("手動確認" in issue.detail for issue in report.issues)


def test_parse_errors_never_copy_source_or_secrets_into_reports(tmp_path: Path) -> None:
    secret_marker = "sk-" + "proj-THIS_MUST_NOT_APPEAR_IN_A_REPORT_123456"
    (tmp_path / "broken.py").write_text(f"def broken(:  # {secret_marker}\n", encoding="utf-8")
    report = scan_repository(tmp_path, load_registry(), locale=Locale.EN)
    json_path, markdown_path = write_reports(report, tmp_path / "reports")

    assert secret_marker not in report.model_dump_json()
    assert secret_marker not in json_path.read_text(encoding="utf-8")
    assert secret_marker not in markdown_path.read_text(encoding="utf-8")


def test_scan_skips_generated_directories_and_accepts_crlf(tmp_path: Path) -> None:
    excluded = tmp_path / ".venv"
    excluded.mkdir()
    (excluded / "hidden.py").write_text(
        "openai.ChatCompletion.create(model='x')\n", encoding="utf-8"
    )
    (tmp_path / "app.py").write_bytes(
        b"import openai\r\nopenai.ChatCompletion.create(model='x')\r\n"
    )

    report = scan_repository(tmp_path, load_registry())

    assert report.files_scanned == 1
    assert len(report.findings) == 1
    assert report.findings[0].path == "app.py"
    assert report.findings[0].line == 2


def test_discovery_prunes_deep_excluded_trees_before_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scanner_module, "MAX_METADATA_ENTRIES", 2)
    hidden = tmp_path / ".venv" / "deep" / "nested"
    hidden.mkdir(parents=True)
    (hidden / "ignored.py").write_text(
        "import openai\nopenai.ChatCompletion.create(model='x')\n",
        encoding="utf-8",
    )
    source = tmp_path / "src"
    source.mkdir()
    (source / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    visited: list[Path] = []
    real_walk = os.walk

    def tracking_walk(
        top: str | os.PathLike[str],
        topdown: bool = True,
        onerror: Callable[[OSError], object] | None = None,
        followlinks: bool = False,
    ) -> Iterator[tuple[str, list[str], list[str]]]:
        for current, directories, files in real_walk(
            top,
            topdown=topdown,
            onerror=onerror,
            followlinks=followlinks,
        ):
            visited.append(Path(current).relative_to(tmp_path))
            yield current, directories, files

    monkeypatch.setattr(os, "walk", tracking_walk)

    report = scan_repository(tmp_path, load_registry())

    assert report.files_scanned == 1
    assert not report.findings
    assert not report.issues
    assert all(".venv" not in path.parts for path in visited)


def test_metadata_entry_limit_is_exact_and_one_over_is_blocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert scanner_module.MAX_METADATA_ENTRIES == 50_000
    monkeypatch.setattr(scanner_module, "MAX_METADATA_ENTRIES", 2)
    (tmp_path / "first.txt").write_text("one\n", encoding="utf-8")
    (tmp_path / "second.txt").write_text("two\n", encoding="utf-8")

    exact = scan_repository(tmp_path, load_registry())

    assert exact.files_scanned == 0
    assert not exact.issues

    (tmp_path / "third.txt").write_text("three\n", encoding="utf-8")
    over = scan_repository(tmp_path, load_registry())

    assert over.files_scanned == 0
    assert [issue.kind for issue in over.issues] == ["limit_exceeded"]
    assert "metadata" in over.issues[0].detail


def test_aggregate_source_byte_limit_is_exact_and_one_over_is_blocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert scanner_module.MAX_TOTAL_BYTES == 50_000_000
    first = tmp_path / "first.py"
    first.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(scanner_module, "MAX_TOTAL_BYTES", first.stat().st_size)

    exact = scan_repository(tmp_path, load_registry())

    assert exact.files_scanned == 1
    assert not exact.issues

    (tmp_path / "second.py").write_text("VALUE = 2\n", encoding="utf-8")
    over = scan_repository(tmp_path, load_registry())

    assert over.files_scanned == 1
    assert [issue.kind for issue in over.issues] == ["limit_exceeded"]
    assert "aggregate Python source limit" in over.issues[0].detail


def test_unreadable_encoding_and_size_limit_are_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "invalid.py").write_bytes(b"\xff\xfe\x00")
    (tmp_path / "large.py").write_text("VALUE = 'large'\n", encoding="utf-8")
    monkeypatch.setattr(scanner_module, "MAX_FILE_BYTES", 4)

    report = scan_repository(tmp_path, load_registry())

    assert not report.findings
    assert {issue.kind for issue in report.issues} == {"read_error", "limit_exceeded"}


def test_file_count_limit_reports_incomplete_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("VALUE = 2\n", encoding="utf-8")
    monkeypatch.setattr(scanner_module, "MAX_FILES", 1)

    report = scan_repository(tmp_path, load_registry())

    assert report.files_scanned == 1
    assert any(issue.kind == "limit_exceeded" for issue in report.issues)


def test_exact_file_count_limit_is_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert scanner_module.MAX_FILES == 5_000
    (tmp_path / "only.py").write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(scanner_module, "MAX_FILES", 1)

    report = scan_repository(tmp_path, load_registry())

    assert report.files_scanned == 1
    assert not any(issue.kind == "limit_exceeded" for issue in report.issues)


def test_shadow_inventory_is_independent_of_the_file_count_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "app.py").write_text(
        "import openai\nopenai.ChatCompletion.create(model='x')\n",
        encoding="utf-8",
    )
    shadow = tmp_path / "z_after_scan_limit" / "openai.py"
    shadow.parent.mkdir()
    shadow.write_text("class ChatCompletion: ...\n", encoding="utf-8")
    # A reduced test boundary exercises the same path as the production 5,000-file limit
    # without constructing and parsing thousands of fixtures.
    monkeypatch.setattr(scanner_module, "MAX_FILES", 1)

    report = scan_repository(tmp_path, load_registry())

    assert report.files_scanned == 1
    assert any(issue.kind == "limit_exceeded" for issue in report.issues)
    assert len(report.findings) == 1
    assert report.findings[0].confidence == "review"


def test_symlinked_python_file_is_not_followed(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
    outside.write_text(
        "import openai\nopenai.ChatCompletion.create(model='x')\n",
        encoding="utf-8",
    )
    link = tmp_path / "linked.py"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("creating symlinks is not permitted in this Windows environment")

    report = scan_repository(tmp_path, load_registry())

    assert not report.findings
    assert report.files_scanned == 0
    assert len(report.issues) == 1
    assert report.issues[0].kind == "unsafe_path"
    assert report.issues[0].path == "linked.py"
    assert str(outside) not in report.issues[0].detail


def test_symlinked_source_directory_is_an_incomplete_scan(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-private-source"
    outside.mkdir()
    (outside / "app.py").write_text(
        "import openai\nopenai.ChatCompletion.create(model='x')\n",
        encoding="utf-8",
    )
    link = tmp_path / "linked_source"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("creating directory symlinks is not permitted in this environment")

    report = scan_repository(tmp_path, load_registry())

    assert not report.findings
    assert report.files_scanned == 0
    assert len(report.issues) == 1
    assert report.issues[0].kind == "unsafe_path"
    assert report.issues[0].path == "linked_source"
    assert str(outside) not in report.issues[0].detail


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO creation requires POSIX support")
def test_non_regular_python_path_is_rejected_without_reading(tmp_path: Path) -> None:
    fifo = tmp_path / "blocked.py"
    mkfifo: Callable[[Path], None] = vars(os)["mkfifo"]
    mkfifo(fifo)

    report = scan_repository(tmp_path, load_registry())

    assert not report.findings
    assert report.files_scanned == 0
    assert len(report.issues) == 1
    assert report.issues[0].kind == "unsafe_path"
    assert report.issues[0].path == "blocked.py"
    assert "non-regular Python path" in report.issues[0].detail


def test_reports_are_bilingual_and_machine_readable(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "app.py").write_text(
        "def run(openai_client):\n"
        "    return openai_client.responses.create("
        "model='gpt-5.2-chat-latest', input='x')\n",
        encoding="utf-8",
    )
    report = scan_repository(target, load_registry(), locale=Locale.JA)
    markdown = render_markdown(report)
    assert "影響箇所" in markdown
    assert "2026-08-10" in markdown
    markdown.encode("cp932")
    json_path, markdown_path = write_reports(report, tmp_path / "reports")
    assert '"locale": "ja"' in json_path.read_text(encoding="utf-8")
    assert "公式根拠" in markdown_path.read_text(encoding="utf-8")


def test_markdown_escapes_malicious_finding_and_issue_paths(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "app.py").write_text(
        "def run(openai_client):\n"
        "    return openai_client.responses.create("
        "model='gpt-5.2-chat-latest', input='x')\n",
        encoding="utf-8",
    )
    report = scan_repository(target, load_registry())
    malicious = "src/row|`break`\n\x1b[31m.py"
    report.findings[0].path = malicious
    report.issues = [
        ScanIssue(
            path=malicious,
            kind="unsafe_path",
            detail="unsafe\n\x1b[31m detail",
        )
    ]

    markdown = render_markdown(report)

    assert "\x1b" not in markdown
    assert "\\u001b" in markdown
    assert "\\n" in markdown
    assert r"\|" in markdown
    assert "\n\x1b[31m.py" not in markdown
    assert visible_text("src/app.py") == "src/app.py"
    assert markdown_code("src/app.py") == "`src/app.py`"
