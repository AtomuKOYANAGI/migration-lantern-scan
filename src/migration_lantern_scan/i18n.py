from __future__ import annotations

from migration_lantern_scan.models import Locale

MESSAGES: dict[str, dict[Locale, str]] = {
    "summary": {
        Locale.EN: "Scanned {files} Python files; found {findings} deprecation impact(s).",
        Locale.JA: "Pythonファイル{files}件を検査し、非推奨の影響を{findings}件検出しました。",
    },
    "clean": {
        Locale.EN: "No configured deprecation rule matched.",
        Locale.JA: "登録済みの非推奨ルールに一致する箇所はありませんでした。",
    },
    "issues_summary": {
        Locale.EN: "Review notes: {issues} issue(s).",
        Locale.JA: "要確認事項: {issues}件。",
    },
    "issue": {Locale.EN: "review", Locale.JA: "要確認"},
    "source": {Locale.EN: "source", Locale.JA: "根拠"},
    "deadline": {Locale.EN: "deadline", Locale.JA: "期限"},
    "not_published": {Locale.EN: "not published", Locale.JA: "公表なし"},
    "review": {Locale.EN: "review", Locale.JA: "要確認"},
    "reports_written": {
        Locale.EN: "Wrote JSON and Markdown reports to {path}",
        Locale.JA: "JSON・Markdownレポートを {path} に出力しました。",
    },
    "invalid_target": {
        Locale.EN: "Target must be an existing directory: {path}",
        Locale.JA: "対象には既存のディレクトリを指定してください: {path}",
    },
    "scan_failed": {
        Locale.EN: "Scan failed safely. No exception details were emitted.",
        Locale.JA: "安全に検査を中止しました。例外の詳細は出力していません。",
    },
}

SEVERITY_LABELS = {
    "medium": {Locale.EN: "medium", Locale.JA: "中"},
    "high": {Locale.EN: "high", Locale.JA: "高"},
    "critical": {Locale.EN: "critical", Locale.JA: "緊急"},
}
CATEGORY_LABELS = {
    "model": {Locale.EN: "model", Locale.JA: "モデル"},
    "endpoint": {Locale.EN: "endpoint", Locale.JA: "エンドポイント"},
    "sdk_syntax": {Locale.EN: "sdk_syntax", Locale.JA: "SDK記法"},
}
CONFIDENCE_LABELS = {
    "high": {Locale.EN: "high", Locale.JA: "高"},
    "review": {Locale.EN: "review", Locale.JA: "要確認"},
}
ISSUE_KIND_LABELS = {
    "read_error": {Locale.EN: "read_error", Locale.JA: "読取エラー"},
    "parse_error": {Locale.EN: "parse_error", Locale.JA: "構文エラー"},
    "dynamic_value": {Locale.EN: "dynamic_value", Locale.JA: "動的値"},
    "limit_exceeded": {Locale.EN: "limit_exceeded", Locale.JA: "上限超過"},
    "unsafe_path": {Locale.EN: "unsafe_path", Locale.JA: "安全でないパス"},
}


def tr(key: str, locale: Locale, **values: object) -> str:
    return MESSAGES[key][locale].format(**values)


def severity_label(value: str, locale: Locale) -> str:
    return SEVERITY_LABELS[value][locale]


def category_label(value: str, locale: Locale) -> str:
    return CATEGORY_LABELS[value][locale]


def confidence_label(value: str, locale: Locale) -> str:
    return CONFIDENCE_LABELS[value][locale]


def issue_kind_label(value: str, locale: Locale) -> str:
    return ISSUE_KIND_LABELS[value][locale]
