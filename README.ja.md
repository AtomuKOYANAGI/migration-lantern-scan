# Migration Lantern Scan

[English](README.md)

Migration Lantern Scanは、Pythonリポジトリ内にあるOpenAI・Anthropicの非推奨箇所を、コードを実行せずローカルで検出する無料ツールです。影響ファイル・行、深刻度、提供元の公式根拠、公開済み期限、推奨移行先を表示し、CI向けJSON・Markdownを生成します。

対象コードの実行、プロバイダーAPIへの通信、ソースコードの外部送信、走査対象ソースの変更は行いません。
書き込むのは、利用者が明示したJSON・Markdownレポートの出力先だけです。

## v0.1の検出対象

- Responses / Chat Completions内のOpenAI `gpt-5.2-chat-latest`;
- Messages API内のAnthropic Claude Opus 4.1;
- OpenAI Python v1以前の `openai.ChatCompletion.create` 記法;
- Anthropicの旧Text Completions `completions.create` エンドポイント。

ルールは2026-08-10に提供元公式資料で再確認しています。期限が公表されていない場合は「公表なし」と表示し、推測では補いません。

## インストールと実行

Python 3.11以上が必要です。

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install .
migration-lantern-scan scan /path/to/repository --locale ja
```

`migration-lantern-scan-reports/` にJSONとMarkdownを出力します。
レポートにはリポジトリ内のパス、呼び出し箇所、モデル名、移行時期が含まれます。サンプルworkflowのartifact保存は7日間です。機密性の高いリポジトリでは、任意のupload手順を削除するか、承認済みのより短い保存期間を指定してください。

終了コード:

- `0`: 検査完了。CI失敗を指定していない状態;
- `2`: 設定不正、または安全に検査を完了できなかった状態;
- `3`: `--fail-on-findings` 指定時に検出あり;
- `4`: `--fail-on-issues` 指定時に要確認事項あり。

読取り、構文解析、ファイル上限の問題は検査が不完全なため常に `2` です。動的モデル値は `--fail-on-issues` 指定時だけ `4` になります。Actionは両方のfail設定を既定で有効にします。

日本語のコマンド説明:

```bash
migration-lantern-scan help-ja
```

## GitHub Action

`v0.1.0` は、最初のversion付きGitHub Actionリリースです。安定した公開版としてこのtagに
固定するか、サプライチェーンをより厳格に管理する場合は、内容を確認した完全なcommit SHAに
固定してください。`main` は開発先端であり、本番利用の推奨参照先ではありません。

```yaml
name: Migration Lantern Scan
on: [pull_request, workflow_dispatch]
permissions:
  contents: read
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
        with:
          persist-credentials: false
      - uses: AtomuKOYANAGI/migration-lantern-scan@v0.1.0
        with:
          path: .
          locale: ja
          fail-on-findings: "true"
          fail-on-issues: "true"
```

高保証環境では、Migration Lantern Scanを含む第三者Actionを確認済みコミットSHAで固定してください。

## デモ

`demo/before` は意図的に古くした架空コードです。記載された旧パッケージをインストールしないでください。

```bash
migration-lantern-scan scan demo/before --locale ja --no-fail-on-findings
```

`demo/after` は、人がレビューする有料パイロットの結果例です。無料版はコードを書き換えません。

## セキュリティとプライバシー

Migration Lantern Scanはローカルで静的解析し、シークレットを必要としません。Actionの権限は `contents: read` のみで、`pull_request_target` や対象テストの実行は行いません。詳細は [SECURITY.ja.md](SECURITY.ja.md) を参照してください。脆弱性は公開Issueではなく、[GitHub Security Advisoryの非公開フォーム](https://github.com/AtomuKOYANAGI/migration-lantern-scan/security/advisories/new)から報告してください。

静的解析には限界があります。受信オブジェクト名は型の証明ではなく、ラッパー、別名、動的設定、生成コード、クラウド固有IDを見逃す可能性があります。検出ゼロは安全性の保証ではありません。

各検出には `confidence` が付きます。`high` は、LibCSTが呼出し元を曖昧さのない
`openai` / `anthropic` モジュールimport、または承認済みSDK client constructorからの
単一代入として解決し、かつ同名のローカルmoduleによるshadowがリポジトリ内にない場合
だけです。provider module aliasと承認済みconstructorのimport aliasは解決します。その証明が
ない構文一致は `review` として残し、受信オブジェクトの綴りだけで `high` にはしません。
constructor、provider module、clientに明示されたendpoint、header、query、HTTP transportの
上書きがある場合も `review` に降格します。再代入、その他のimport object alias、wrapper、
`self.client` のようなattribute、bound method alias、factoryが返すclient、動的importは
`review` に留まるか検出範囲外になる場合があります。環境変数だけで指定されたendpointの
上書き、別ファイルからの変更、runtime変更は静的には解決できません。`confidence` はprovider
bindingの信頼度であり、移行後の挙動が安全であることの証明ではありません。

## 無料版と有料パイロット

| | 無料Migration Lantern Scan | 有料Migration Lantern Pilot |
| --- | --- | --- |
| 登録済み非推奨の検出 | 対応 | 対応＋合意範囲の手動調査 |
| 公式根拠・期限 | 対応 | 対応 |
| JSON / Markdown | 対応 | 対応 |
| コード修正 | なし | 人がレビューする移行差分 |
| 既存・回帰テスト | なし | 合意したリポジトリで実施 |
| 品質・費用・速度 | なし | 計測可能な範囲で報告 |
| Pull Request | なし | リポジトリ承認後にdraft PR |
| サポート | 公開Issue | 納品後7日間の不具合修正 |

最初の3件は、対象を確認したPythonリポジトリ1件につき **49,800円** です。APIキーをチャットやメールで送らないでください。

## 発行者・ライセンス・連絡先

- 発行者: `AtomuKOYANAGI`
- 著作権表示: `Copyright 2026 4tomStudio`
- ライセンス: [Apache License 2.0](LICENSE)
- 公開サポート: [GitHub Issue選択画面](https://github.com/AtomuKOYANAGI/migration-lantern-scan/issues/new/choose)
- 公開連絡先: [atom01090109@icloud.com](mailto:atom01090109@icloud.com)
- プライバシー: [Privacy Notice / プライバシー通知](https://github.com/AtomuKOYANAGI/migration-lantern-scan/blob/main/PRIVACY.md)
- 利用条件: [Terms of Use / 利用条件](https://github.com/AtomuKOYANAGI/migration-lantern-scan/blob/main/TERMS.md)

Apache-2.0の対象は、この公開Scanリポジトリで配布するファイルだけです。非公開のMigration
Pilot実装や顧客用作業領域には適用しません。`v0.1.0` GitHub ActionリリースとMarketplace掲載
で配布するのも、この無料Scanだけです。パッケージ配布、Webサイト、決済、有料サービスの
公開には、別途の判断が必要です。
