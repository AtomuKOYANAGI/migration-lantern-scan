# セキュリティ

Migration Lantern Scanは静的解析だけを行い、対象となるPythonソースファイルを全文解析します。対象モジュールをimportせず、リポジトリのテストも実行しません。認証情報を取得する目的で、環境変数、Python以外の設定ファイル、シークレットストアへ独自にアクセスすることも、認証情報の入力を求めることもありません。ただし、解析対象のPythonソースへ秘密情報が埋め込まれていれば、その値もファイル内容の一部として読み取られます。秘密情報をソースへ保存しないでください。プロバイダーAPIへの通信、ソースコードのアップロード、対象ファイルの変更は行いません。

GitHub Actionの権限は `contents: read` のみで、シークレットは不要です。`pull_request_target` も使用しません。Python 3.11で動作し、`requirements-action.lock` に固定した依存バージョンを `--only-binary=:all:`、`--require-hashes`、`--target` によりrunner固有の一時領域へ導入します。呼出元のPython環境へは導入しません。ソース配布物や未登録ハッシュは拒否します。ただし、第三者の解析・実行ライブラリはScanner専用のmodule pathからimportするため信頼境界に含まれます。高保証環境ではMigration Lantern Scan Action自体もコミットSHAで固定してください。

Scanner本体はレポートをuploadしません。サンプルworkflowには、保存期間7日の独立した任意の`upload-artifact`手順があります。レポートには、ソースから得た相対パス、行・列、呼び出し・モデルの識別子、ルールと根拠のmetadataが含まれますが、ソースコードの抜粋は含みません。これらも機密になり得るリポジトリmetadataとして扱い、GitHub artifact保存が承認されていない場合はupload手順を削除してください。CLIはartifact作成または検出詳細の標準出力前に、出力先とソース由来のレポートmetadataを対応済みの認証情報・危険な制御文字パターンと照合し、一致した値を表示せずに停止します。JSONでは非ASCII文字と制御文字をASCII escapeで保存し、decode後の値は維持します。このパターン検査は偶発的な漏えいリスクを下げるためのもので、汎用的なsecret scannerでも、レポートに秘密情報が一切ないことの証明でもありません。

ローカル資源の消費を制限するため、除外対象を除くファイルシステム項目50,000件、
対象Pythonファイル5,000件、Pythonファイル1件あたり1,000,000バイト、または対象Python
ソース合計50,000,000バイトで探索を停止します。除外ディレクトリは項目数へ算入する前に
枝刈りします。いずれかの上限へ達した結果は見逃しを含み得るため、blocking
`limit_exceeded`として報告します。対象パスを狭めるか、大規模リポジトリを分割して再実行してください。

既知の制約:

- `confidence: high` は、曖昧さのないprovider module importまたは承認済みSDK
  constructorからの単一代入を確認でき、かつscan対象全体に同名のローカルprovider moduleが
  ない場合だけです。provider module aliasと承認済みconstructorのimport aliasには対応しますが、
  受信オブジェクト名だけの一致は `review` です。
- constructor、provider module、clientに明示されたendpoint、header、query、HTTP transportの
  上書きは `review` に降格します。環境変数だけによるendpoint上書きは静的に解決しません。
- 別ファイルからの変更やruntime変更も静的に解決しません。
- 再代入、wrapper、object attribute、bound method alias、factoryが返すclient、動的import・
  設定、生成コード、クラウド固有モデルIDは `review` に留まるか、見逃す可能性があります。
- confidenceはprovider bindingの信頼度であり、移行の安全性やruntime挙動の保証ではありません。
- 検出ゼロは非推奨箇所が存在しないことの保証ではありません。
- ルールの根拠は日付付きスナップショットであり、古くなる可能性があります。

脆弱性の疑いは、リポジトリの[GitHub Security Advisory非公開フォーム](https://github.com/AtomuKOYANAGI/migration-lantern-scan/security/advisories/new)から報告してください。認証情報、顧客コード、顧客データを含めないでください。機密性のない質問は公開Issueテンプレート、または atom01090109@icloud.com を利用できます。
