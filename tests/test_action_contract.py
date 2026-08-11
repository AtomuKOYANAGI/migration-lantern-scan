from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_publication_identity_license_and_policy_links_are_resolved() -> None:
    metadata = json.loads((ROOT / "publication.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    action = (ROOT / "action.yml").read_text(encoding="utf-8")
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")

    assert metadata["schema_version"] == "1.1"
    assert metadata["status"] == "approved"
    assert metadata["publisher"] == "AtomuKOYANAGI"
    assert metadata["contact_email"] == "atom01090109@icloud.com"
    assert metadata["license_spdx"] == "Apache-2.0"
    assert metadata["copyright_notice"] == "Copyright 2026 4tomStudio"
    assert project["license"] == metadata["license_spdx"]
    assert f"author: {metadata['publisher']}" in action
    assert metadata["copyright_notice"] in notice
    assert (
        (ROOT / "LICENSE")
        .read_text(encoding="utf-8")
        .startswith("                                 Apache License\n")
    )
    for policy in ("PRIVACY.md", "TERMS.md"):
        assert (ROOT / policy).is_file()
    for readme in ("README.md", "README.ja.md"):
        text = (ROOT / readme).read_text(encoding="utf-8")
        for field in (
            "publisher",
            "contact_email",
            "copyright_notice",
            "support_url",
            "privacy_url",
            "terms_url",
        ):
            assert metadata[field] in text


def test_public_gitignore_excludes_local_secrets_and_generated_outputs() -> None:
    patterns = {
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {
        ".env",
        ".env.*",
        ".local/",
        "secrets/",
        "*.key",
        "*.pem",
        "*.p12",
        "*.pfx",
        "*.log",
        ".coverage",
        "coverage.xml",
        "htmlcov/",
        "migration-lantern-scan-reports/",
    } <= patterns
    assert "!.env.example" not in patterns


def test_release_coordinates_use_the_reviewed_version_tag() -> None:
    metadata = json.loads((ROOT / "publication.json").read_text(encoding="utf-8"))
    coordinate = "AtomuKOYANAGI/migration-lantern-scan@v0.1.0"

    assert metadata["action_ref"] == "v0.1.0"
    for path in (
        ROOT / "README.md",
        ROOT / "README.ja.md",
        ROOT / "examples" / "migration-lantern-scan.yml",
        ROOT / "docs" / "MARKETPLACE.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert coordinate in text
        assert "AtomuKOYANAGI/migration-lantern-scan@main" not in text
        assert "replace main" not in text.lower()


def test_action_is_static_read_only_and_secret_free() -> None:
    action = (ROOT / "action.yml").read_text(encoding="utf-8")
    workflow = (ROOT / "examples" / "migration-lantern-scan.yml").read_text(encoding="utf-8")

    for text in (action, workflow):
        assert "pull_request_target" not in text
        assert "contents: write" not in text
        assert "${{ secrets." not in text
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "if: always()" in workflow
    assert "retention-days: 7" in workflow
    assert "--fail-on-findings" in action
    assert "--fail-on-issues" in action
    assert "--require-hashes" in action
    assert "--only-binary=:all:" in action
    assert "python -P -m pip" in action
    assert "python -P -m migration_lantern_scan scan" in action
    assert 'PYTHONNOUSERSITE: "1"' in action
    assert "tempfile.mkdtemp" in action
    assert 'dir=sys.argv[1]))\' "$RUNNER_TEMP"' in action
    assert '--target "$dependency_root"' in action
    assert "--ignore-installed" in action
    assert "MIGRATION_LANTERN_DEPENDENCY_ROOT" in action
    assert "os.pathsep" in action
    assert (
        'export PYTHONPATH="${MIGRATION_LANTERN_MODULE_ROOT}${MIGRATION_LANTERN_PATH_SEPARATOR}'
        '${MIGRATION_LANTERN_DEPENDENCY_ROOT}"'
    ) in action
    assert "${PYTHONPATH:+:$PYTHONPATH}" not in action
    assert "requirements-action.lock" in action
    assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1" in action
    assert "output-dir must be non-empty and single-line" in action
    guard = action.index("require_safe_output_directory")
    json_output = action.index(
        'echo "json-report=${MIGRATION_LANTERN_OUTPUT_DIR}/migration-lantern-scan.json"'
    )
    markdown_output = action.index(
        'echo "markdown-report=${MIGRATION_LANTERN_OUTPUT_DIR}/migration-lantern-scan.md"'
    )
    scanner = action.index("python -P -m migration_lantern_scan scan")
    assert guard < json_output < scanner
    assert guard < markdown_output < scanner


def test_ci_covers_supported_python_and_runs_the_action_on_three_platforms() -> None:
    workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")

    for platform in ("ubuntu-latest", "windows-latest", "macos-latest"):
        assert f'- os: {platform}\n            python: "3.11"' in workflow
    for version in ("3.12", "3.13"):
        assert f'- os: ubuntu-latest\n            python: "{version}"' in workflow
    assert "os: [ubuntu-latest, windows-latest, macos-latest]" in workflow
    assert "uses: ./" in workflow
    assert '"pydantic==2.12.5"' in workflow
    assert "CALLER_PYDANTIC_VERSION" in workflow
    assert 'importlib.metadata.version("pydantic") ==' in workflow
    assert "run: python -m pip install --only-binary=:all:" not in workflow
    assert (
        'run: |\n          python -m pip install --only-binary=:all: "pydantic==2.12.5"' in workflow
    )


def test_isolated_dependency_target_does_not_replace_caller_package(tmp_path: Path) -> None:
    package_name = "migration_lantern_action_sentinel"
    caller_root = tmp_path / "caller"
    caller_package = caller_root / package_name
    caller_package.mkdir(parents=True)
    caller_source = '__version__ = "caller-1.0"\n'
    (caller_package / "__init__.py").write_text(caller_source, encoding="utf-8")

    wheel = tmp_path / "migration_lantern_action_sentinel-9.9.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"{package_name}/__init__.py", '__version__ = "action-9.9"\n')
        dist_info = "migration_lantern_action_sentinel-9.9.0.dist-info"
        archive.writestr(
            f"{dist_info}/METADATA",
            "Metadata-Version: 2.1\nName: migration-lantern-action-sentinel\nVersion: 9.9.0\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: migration-lantern-test\nRoot-Is-Purelib: true\n"
            "Tag: py3-none-any\n",
        )
        archive.writestr(f"{dist_info}/RECORD", "")

    def installed_version(module_root: Path) -> str:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(module_root)
        environment["PYTHONNOUSERSITE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-P",
                "-c",
                f"import {package_name}; print({package_name}.__version__)",
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        return completed.stdout.strip()

    assert installed_version(caller_root) == "caller-1.0"
    action_target = tmp_path / "action-dependencies"
    completed = subprocess.run(
        [
            sys.executable,
            "-P",
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-index",
            "--no-deps",
            "--ignore-installed",
            "--target",
            str(action_target),
            str(wheel),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert installed_version(action_target) == "action-9.9"
    assert installed_version(caller_root) == "caller-1.0"
    assert (caller_package / "__init__.py").read_text(encoding="utf-8") == caller_source


def test_public_action_never_invokes_target_tests_or_private_engine() -> None:
    action = (ROOT / "action.yml").read_text(encoding="utf-8")

    assert "python -P -m migration_lantern_scan scan" in action
    assert "pytest" not in action
    assert "migration-lantern-scan apply" not in action
    assert "migration-lantern-scan verify" not in action
    assert "transform" not in action.lower()


def test_public_issue_form_routes_sensitive_reports_away_from_public_issues() -> None:
    issue_root = ROOT / ".github" / "ISSUE_TEMPLATE"
    bug_report = (issue_root / "bug_report.yml").read_text(encoding="utf-8")
    config = (issue_root / "config.yml").read_text(encoding="utf-8")

    for warning in ("API keys", "private source", "customer data"):
        assert warning in bug_report
    assert "This is not a security vulnerability" in bug_report
    assert "required: true" in bug_report
    assert "blank_issues_enabled: false" in config
    assert "/security/advisories/new" in config
    assert "Do not disclose vulnerabilities" in config


def test_security_copy_discloses_full_source_parsing_and_report_fields() -> None:
    english = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    japanese = (ROOT / "SECURITY.ja.md").read_text(encoding="utf-8")

    assert "parses every eligible Python source file in full" in english
    assert "does not independently access provider-credential environment variables" in english
    assert "do not include source excerpts" in english
    assert "read API keys" not in english
    assert "対象となるPythonソースファイルを全文解析" in japanese
    assert "認証情報を取得する目的で、環境変数" in japanese
    assert "ソースコードの抜粋は含みません" in japanese
    assert "APIキーの読取り" not in japanese


def test_isolated_module_execution_does_not_run_target_shadow_package(
    tmp_path: Path,
) -> None:
    target = tmp_path / "customer-repository"
    shadow_package = target / "migration_lantern_scan"
    shadow_package.mkdir(parents=True)
    marker = target / "shadow-module-ran"
    (shadow_package / "__init__.py").write_text("", encoding="utf-8")
    (shadow_package / "__main__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('unsafe')\n",
        encoding="utf-8",
    )
    (target / "app.py").write_text("VALUE = 1\n", encoding="utf-8")

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    environment["PYTHONNOUSERSITE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-P", "-m", "migration_lantern_scan", "scan", str(target)],
        cwd=target,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert not marker.exists()
