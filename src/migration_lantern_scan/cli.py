from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from migration_lantern_scan.i18n import confidence_label, issue_kind_label, severity_label, tr
from migration_lantern_scan.models import Locale
from migration_lantern_scan.registry import load_registry
from migration_lantern_scan.reporting import render_markdown, visible_text, write_reports
from migration_lantern_scan.scanner import scan_repository


class OutputFormat(StrEnum):
    SUMMARY = "summary"
    JSON = "json"
    MARKDOWN = "markdown"


BLOCKING_ISSUE_KINDS = {"read_error", "parse_error", "limit_exceeded", "unsafe_path"}


app = typer.Typer(
    name="migration-lantern-scan",
    help="Offline OpenAI and Anthropic deprecation scanner for Python repositories.",
    no_args_is_help=True,
)


@app.command()
def scan(
    path: Annotated[Path, typer.Argument(help="Python repository to scan.")] = Path("."),
    locale: Annotated[Locale, typer.Option("--locale", help="Output language: en or ja.")] = (
        Locale.EN
    ),
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for JSON and Markdown reports."),
    ] = Path("migration-lantern-scan-reports"),
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Stdout format."),
    ] = OutputFormat.SUMMARY,
    fail_on_findings: Annotated[
        bool,
        typer.Option(
            "--fail-on-findings/--no-fail-on-findings",
            help="Exit with code 3 when findings exist.",
        ),
    ] = False,
    fail_on_issues: Annotated[
        bool,
        typer.Option(
            "--fail-on-issues/--no-fail-on-issues",
            help="Exit with code 4 for review issues; incomplete scans always exit 2.",
        ),
    ] = False,
    registry: Annotated[
        Path | None,
        typer.Option("--registry", exists=True, dir_okay=False, help="Custom public rules."),
    ] = None,
) -> None:
    """Scan without importing or executing target code."""
    if not path.exists() or not path.is_dir():
        typer.echo(tr("invalid_target", locale, path=visible_text(path)), err=True)
        raise typer.Exit(2)
    try:
        report = scan_repository(path, load_registry(registry), locale=locale)
        json_path, markdown_path = write_reports(report, output_dir)
    except Exception:
        typer.echo(tr("scan_failed", locale), err=True)
        raise typer.Exit(2) from None
    if output_format == OutputFormat.JSON:
        typer.echo(report.model_dump_json(indent=2, ensure_ascii=True))
    elif output_format == OutputFormat.MARKDOWN:
        typer.echo(render_markdown(report))
    else:
        typer.echo(
            tr(
                "summary",
                locale,
                files=report.files_scanned,
                findings=len(report.findings),
            )
        )
        for finding in report.findings:
            deadline = (
                finding.deadline.isoformat() if finding.deadline else tr("not_published", locale)
            )
            typer.echo(
                f"[{severity_label(finding.severity.value, locale)}] "
                f"{visible_text(finding.path)}:{finding.line}:{finding.column} "
                f"{visible_text(finding.deprecated_target)} -> "
                f"{visible_text(finding.recommended_target)}; "
                f"{tr('deadline', locale)} {deadline}; "
                f"{confidence_label(finding.confidence, locale)}"
            )
            for source in finding.evidence:
                typer.echo(
                    f"  {tr('source', locale)} ({source.checked_on.isoformat()}): "
                    f"{visible_text(source.url)}"
                )
            if finding.migration_note:
                typer.echo(f"  {tr('review', locale)}: {visible_text(finding.migration_note)}")
        if not report.findings:
            typer.echo(tr("clean", locale))
        if report.issues:
            typer.echo(tr("issues_summary", locale, issues=len(report.issues)))
            for issue in report.issues:
                location = (
                    f"{visible_text(issue.path)}:{issue.line}"
                    if issue.line
                    else visible_text(issue.path)
                )
                typer.echo(
                    f"[{tr('issue', locale)}:{issue_kind_label(issue.kind, locale)}] "
                    f"{location}: {visible_text(issue.detail)}"
                )
        typer.echo(tr("reports_written", locale, path=visible_text(output_dir.resolve())))
        typer.echo(f"JSON: {visible_text(json_path)}")
        typer.echo(f"Markdown: {visible_text(markdown_path)}")
    if any(issue.kind in BLOCKING_ISSUE_KINDS for issue in report.issues):
        raise typer.Exit(2)
    if fail_on_findings and report.findings:
        raise typer.Exit(3)
    if fail_on_issues and report.issues:
        raise typer.Exit(4)


@app.command()
def rules(
    locale: Annotated[Locale, typer.Option("--locale")] = Locale.EN,
) -> None:
    """List the bundled public detection rules and evidence dates."""
    registry = load_registry()
    typer.echo(
        ("Rules verified" if locale == Locale.EN else "ルール確認日") + f": {registry.verified_on}"
    )
    for rule in registry.rules:
        title = rule.title_en if locale == Locale.EN else rule.title_ja
        deadline = rule.deadline.isoformat() if rule.deadline else tr("not_published", locale)
        typer.echo(f"- {rule.rule_id}: {title}; {tr('deadline', locale)} {deadline}")


@app.command("help-ja")
def help_ja() -> None:
    """Show Japanese command guidance."""
    typer.echo(
        "Migration Lantern Scan - Python向けOpenAI・Anthropic非推奨検査\n\n"
        "使い方:\n"
        "  migration-lantern-scan scan [PATH] [OPTIONS]\n"
        "  migration-lantern-scan rules [--locale ja]\n\n"
        "コマンド:\n"
        "  scan   Pythonコードを実行・変更せずに検査し、JSONとMarkdownを生成します。\n"
        "  rules  同梱ルール、公式根拠の確認日、廃止期限を表示します。\n\n"
        "scanの引数とオプション:\n"
        "  PATH                         対象リポジトリ（既定: 現在のディレクトリ .）\n"
        "  --locale en|ja               出力言語（既定: en）\n"
        "  --output-dir DIRECTORY       レポート保存先（既定: migration-lantern-scan-reports）\n"
        "  --format summary|json|markdown  標準出力形式（既定: summary）\n"
        "  --fail-on-findings           検出ありの場合に終了コード3を返します。\n"
        "  --fail-on-issues             要確認事項ありの場合に終了コード4を返します。\n"
        "  --registry FILE              検証済みのカスタム公開ルールJSONを使用します。\n\n"
        "rulesのオプション:\n"
        "  --locale en|ja               表示言語（既定: en）\n\n"
        "終了コード:\n"
        "  0=成功、2=設定エラーまたは不完全な解析、3=非推奨検出、4=要確認事項。\n\n"
        "安全性と既定動作:\n"
        "  対象モジュールのimport、対象テスト、外部API通信、ソース変更は行いません。\n"
        "  APIキーは不要です。レポートはローカルへ保存され、Scanner自身はuploadしません。"
    )
