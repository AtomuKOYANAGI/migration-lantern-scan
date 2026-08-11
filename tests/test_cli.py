import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from migration_lantern_scan.cli import app
from migration_lantern_scan.models import ScanIssue
from migration_lantern_scan.registry import load_registry
from migration_lantern_scan.scanner import scan_repository


def _target(tmp_path: Path) -> Path:
    target = tmp_path / "repo"
    target.mkdir()
    (target / "app.py").write_text(
        "def run(openai_client):\n"
        "    return openai_client.responses.create("
        "model='gpt-5.2-chat-latest', input='x')\n",
        encoding="utf-8",
    )
    return target


def test_cli_writes_reports_and_supports_ci_exit_code(tmp_path: Path) -> None:
    target = _target(tmp_path)
    output = tmp_path / "reports"
    result = CliRunner().invoke(
        app,
        [
            "scan",
            str(target),
            "--locale",
            "en",
            "--format",
            "json",
            "--output-dir",
            str(output),
            "--fail-on-findings",
        ],
    )
    assert result.exit_code == 3, result.output
    payload = json.loads((output / "migration-lantern-scan.json").read_text(encoding="utf-8"))
    assert payload["target"] == "repo"
    assert payload["findings"][0]["path"] == "app.py"
    assert payload["findings"][0]["deadline"] == "2026-08-10"
    assert (output / "migration-lantern-scan.md").is_file()


@pytest.mark.parametrize("unsafe_field", ["target", "finding_path", "issue_path"])
def test_cli_blocks_credential_like_source_metadata_without_echoing_it(
    tmp_path: Path,
    unsafe_field: str,
) -> None:
    secret_marker = "sk-" + "proj-THIS_MUST_NOT_APPEAR_IN_REPORTS_123456"
    target_name = secret_marker if unsafe_field == "target" else "repository"
    target = tmp_path / target_name
    target.mkdir()
    source_name = secret_marker if unsafe_field in {"finding_path", "issue_path"} else "app"
    source = target / f"{source_name}.py"
    if unsafe_field == "issue_path":
        source.write_text("def broken(:\n", encoding="utf-8")
    else:
        source.write_text(
            "def run(openai_client):\n"
            "    return openai_client.responses.create("
            "model='gpt-5.2-chat-latest', input='x')\n",
            encoding="utf-8",
        )
    output = tmp_path / "reports"

    result = CliRunner().invoke(
        app,
        ["scan", str(target), "--format", "json", "--output-dir", str(output)],
    )

    assert result.exit_code == 2
    assert "Scan failed safely" in result.output
    assert secret_marker not in result.output
    assert not output.exists()


def test_cli_blocks_secret_or_control_shaped_output_directory_before_creation(
    tmp_path: Path,
) -> None:
    target = _target(tmp_path)
    secret_marker = "sk-" + "proj-OUTPUT_PATH_MUST_NOT_BE_REFLECTED_123456"
    unsafe_outputs = [tmp_path / secret_marker, tmp_path / "reports\n\x1b[31m"]

    for output in unsafe_outputs:
        result = CliRunner().invoke(app, ["scan", str(target), "--output-dir", str(output)])

        assert result.exit_code == 2
        assert "Scan failed safely" in result.output
        assert secret_marker not in result.output
        assert "\x1b" not in result.output
        assert not output.exists()


def test_cli_japanese_output_and_invalid_target(tmp_path: Path) -> None:
    output = tmp_path / "r"
    result = CliRunner().invoke(
        app,
        ["scan", str(_target(tmp_path)), "--locale", "ja", "--output-dir", str(output)],
    )
    assert result.exit_code == 0
    assert "非推奨の影響" in result.output
    assert "[緊急]" in result.output
    assert "; 要確認" in result.output
    assert "[critical]" not in result.output
    markdown = (output / "migration-lantern-scan.md").read_text(encoding="utf-8")
    assert "| 緊急 | openai | モデル |" in markdown
    assert "| 要確認 |" in markdown

    invalid = CliRunner().invoke(app, ["scan", str(tmp_path / "missing"), "--locale", "ja"])
    assert invalid.exit_code == 2
    assert "既存のディレクトリ" in invalid.output


@pytest.mark.parametrize("locale", ["en", "ja"])
def test_invalid_target_escapes_control_and_ansi_characters(tmp_path: Path, locale: str) -> None:
    malicious = tmp_path / "missing\n\x1b[31m-target"

    result = CliRunner().invoke(app, ["scan", str(malicious), "--locale", locale])

    assert result.exit_code == 2
    assert "\x1b" not in result.output
    assert r"\u001b" in result.output
    assert r"\n" in result.output
    assert "\n\x1b[31m-target" not in result.output


def test_japanese_help_command() -> None:
    result = CliRunner().invoke(app, ["help-ja"])
    assert result.exit_code == 0
    result.output.encode("cp932")
    for option in (
        "PATH",
        "--locale",
        "--output-dir",
        "--format",
        "--fail-on-findings",
        "--fail-on-issues",
        "--registry",
        "rules",
    ):
        assert option in result.output
    for explanation in (
        "既定: en",
        "既定: migration-lantern-scan-reports",
        "終了コード",
        "対象モジュールのimport",
        "外部API通信",
        "Scanner自身はuploadしません",
    ):
        assert explanation in result.output


def test_incomplete_scan_fails_safely_without_echoing_source(tmp_path: Path) -> None:
    secret_marker = "sk-" + "proj-THIS_MUST_NOT_APPEAR_IN_OUTPUT_123456"
    target = tmp_path / "broken"
    target.mkdir()
    (target / "app.py").write_text(f"def broken(: # {secret_marker}\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["scan", str(target), "--locale", "en"])

    assert result.exit_code == 2
    assert "Review notes: 1 issue" in result.output
    assert "parse_error" in result.output
    assert secret_marker not in result.output


def test_dynamic_review_can_fail_ci_with_distinct_exit_code(tmp_path: Path) -> None:
    target = tmp_path / "dynamic"
    target.mkdir()
    (target / "app.py").write_text(
        "def run(openai_client, model):\n"
        "    return openai_client.responses.create(model=model, input='x')\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["scan", str(target), "--fail-on-issues"])

    assert result.exit_code == 4
    assert "dynamic_value" in result.output


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("en", "Scan failed safely. No exception details were emitted."),
        ("ja", "安全に検査を中止しました。例外の詳細は出力していません。"),
    ],
)
def test_scan_failure_never_reflects_exception_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    locale: str,
    expected: str,
) -> None:
    secret_marker = "sk-" + "proj-DO_NOT_REFLECT_THIS_INPUT_123456789"

    def fail_registry(_path: Path | None = None) -> None:
        raise ValueError(secret_marker)

    monkeypatch.setattr("migration_lantern_scan.cli.load_registry", fail_registry)
    result = CliRunner().invoke(
        app,
        ["scan", str(_target(tmp_path)), "--locale", locale],
    )

    assert result.exit_code == 2
    assert expected in result.output
    assert secret_marker not in result.output


def test_symlinked_python_file_is_an_incomplete_scan_without_target_disclosure(
    tmp_path: Path,
) -> None:
    target = tmp_path / "repository"
    target.mkdir()
    outside = tmp_path / "private-target.py"
    outside.write_text("VALUE = 1\n", encoding="utf-8")
    link = target / "linked.py"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("creating symlinks is not permitted in this Windows environment")

    result = CliRunner().invoke(app, ["scan", str(target), "--locale", "en"])

    assert result.exit_code == 2
    assert "unsafe_path" in result.output
    assert "symbolic-link Python path was not scanned" in result.output
    assert str(outside) not in result.output


def test_summary_escapes_control_characters_in_finding_and_issue_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _target(tmp_path)
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
    monkeypatch.setattr(
        "migration_lantern_scan.cli.scan_repository", lambda *_args, **_kwargs: report
    )

    result = CliRunner().invoke(
        app,
        ["scan", str(target), "--output-dir", str(tmp_path / "reports")],
    )

    assert result.exit_code == 2
    assert "\x1b" not in result.output
    assert "\\u001b" in result.output
    assert "\\n" in result.output
    assert "\n\x1b[31m.py" not in result.output


def test_json_stdout_and_artifact_ascii_escape_bidi_and_control_characters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _target(tmp_path)
    report = scan_repository(target, load_registry())
    malicious = "src/normal\u202ereversed\n\x1b[31m.py"
    report.findings[0].path = malicious
    monkeypatch.setattr(
        "migration_lantern_scan.cli.scan_repository", lambda *_args, **_kwargs: report
    )
    output = tmp_path / "reports"

    result = CliRunner().invoke(
        app,
        ["scan", str(target), "--format", "json", "--output-dir", str(output)],
    )

    assert result.exit_code == 0
    for rendered in (
        result.output,
        (output / "migration-lantern-scan.json").read_text(encoding="utf-8"),
    ):
        assert "\u202e" not in rendered
        assert "\x1b" not in rendered
        assert "\\u202e" in rendered.lower()
        assert "\\u001b" in rendered.lower()
        assert "\\n" in rendered
        assert json.loads(rendered)["findings"][0]["path"] == malicious
