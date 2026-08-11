# Privacy Notice / プライバシー通知

Effective date / 適用日: 2026-08-11

## English

### 1. Scope

This notice covers the free Migration Lantern Scan repository, command-line tool, and GitHub
Action published by `AtomuKOYANAGI`. It does not cover a paid Migration Lantern Pilot engagement,
a customer workspace, or another service governed by separate terms.

### 2. Local scanner behavior

The scanner statically reads eligible Python files at the path you select. It does not execute the
repository, call OpenAI or Anthropic, request API keys, upload source code, or send scan results to
the publisher. It writes reports only to the output path you select. Those reports can contain
relative paths, line and column positions, matched API or model identifiers, and rule evidence.

### 3. GitHub Action and third parties

When you run the Action, GitHub operates the runner and processes workflow logs and repository
data under GitHub's own terms and privacy statement. The Action downloads hash-locked Python
dependencies from the Python Package Index during setup. The scanner does not send source code to
those package providers. The example workflow includes a separate optional artifact-upload step;
remove it when GitHub artifact storage is not approved for your repository.

### 4. Information the maintainer receives

The publisher receives no scan telemetry or source code by default. The maintainer receives only
information you deliberately submit through a GitHub issue, a private Security Advisory, or email.
Public issues are public. Do not submit API keys, credentials, proprietary source, customer data,
or other sensitive material. GitHub controls storage and deletion of information hosted on GitHub.

### 5. Use and retention

Submitted information is used to answer questions, reproduce defects, maintain security, and
improve the public scanner. Public issue history may remain visible as part of the repository
record. Private reports and email are kept only as reasonably needed for triage, follow-up,
security records, and applicable obligations. No submitted customer code is used as demo data or
reused for another customer.

### 6. Contact

Publisher: `AtomuKOYANAGI`  
Email: [atom01090109@icloud.com](mailto:atom01090109@icloud.com)  
Security reports: [private GitHub Security Advisory](https://github.com/AtomuKOYANAGI/migration-lantern-scan/security/advisories/new)

## 日本語

### 1. 対象

この通知は、`AtomuKOYANAGI`が公開する無料のMigration Lantern Scanリポジトリ、CLI、
GitHub Actionを対象とします。有料のMigration Lantern Pilot、顧客用作業領域、別条件で
提供するサービスは対象外です。

### 2. ローカルScannerの動作

Scannerは、利用者が指定したパスにある対象Pythonファイルを静的に読み取ります。対象コード
の実行、OpenAI・Anthropic APIの呼出し、APIキーの要求、ソースコードのupload、発行者への
検出結果送信は行いません。レポートは利用者が指定した出力先だけへ書き込みます。レポートには
相対パス、行・列、検出したAPI・モデル識別子、ルールの根拠が含まれる場合があります。

### 3. GitHub Actionと第三者

Actionを実行すると、GitHubがrunnerを運用し、GitHub自身の規約・プライバシー声明に基づいて
workflow logとリポジトリ情報を処理します。Actionはsetup時にPython Package Indexからhash
固定済み依存関係を取得しますが、Scannerがパッケージ提供者へソースコードを送ることは
ありません。サンプルworkflowには独立した任意のartifact upload手順があります。GitHubの
artifact保存が承認されていないリポジトリでは、その手順を削除してください。

### 4. Maintainerが受け取る情報

既定では、発行者はscan telemetryやソースコードを受け取りません。GitHub Issue、非公開の
Security Advisory、メールを通じて利用者が意図的に送信した情報だけを受け取ります。公開Issue
は公開情報です。APIキー、認証情報、非公開ソース、顧客データ、その他の機密情報を送らないで
ください。GitHub上の情報の保存・削除はGitHubが管理します。

### 5. 利用目的と保存

送信された情報は、質問への回答、不具合再現、セキュリティ対応、公開Scannerの改善に使用
します。公開Issueの履歴はリポジトリ記録として表示され続ける場合があります。非公開報告と
メールは、調査、連絡、セキュリティ記録、適用される義務のため合理的に必要な期間だけ保存
します。送信された顧客コードをデモや他案件へ再利用しません。

### 6. 連絡先

発行者: `AtomuKOYANAGI`  
メール: [atom01090109@icloud.com](mailto:atom01090109@icloud.com)  
脆弱性報告: [GitHub Security Advisory非公開フォーム](https://github.com/AtomuKOYANAGI/migration-lantern-scan/security/advisories/new)
