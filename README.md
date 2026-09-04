# claude-pptx-translation-poc

Claude API（Claude Platform on AWS 経由）による pptx 自動翻訳の技術検証用プロジェクト。
背景・比較検討の経緯は [docs/automatic-translation.md](../docs/automatic-translation.md) を参照。

検証内容:

1. Files API で pptx をアップロードできるか
2. Code Execution + Agent Skills（`pptx` スキル）で、レイアウトを保ったまま翻訳・再構成できるか
3. 生成された pptx を Files API でダウンロードできるか

## 前提条件

「Claude APIキー」「ワークスペースID」に加えて、以下が必要です。

| 項目 | 内容 |
|---|---|
| `AWS_REGION` | Claude Platform on AWS はデフォルト値なし。明示的に指定が必須 |
| AWS認証情報 | SigV4署名用の認証情報（アクセスキー/シークレット/セッショントークン、またはIAMロール）。短期APIキーを使う場合も、その発行元となるAWS認証情報が別途必要 |
| IAM権限 | 呼び出し元のIAMプリンシパルに `aws-external-anthropic` サービスへのアクセスを許可するIAMアクションが付与されていること |
| AWS Marketplaceサブスクリプション | Claude Platform on AWS 製品のサブスクリプション（課金アカウント側での契約） |
| ネットワーク到達性 | `https://aws-external-anthropic.{region}.api.aws` へのアウトバウンドHTTPS許可（社内プロキシ/FWで穴あけが必要な場合あり） |
| pptx スキルの有効化確認 | ワークスペースで Agent Skills / Code Execution のベータ機能が有効か。`python src/check_skills.py` で確認 |
| Python実行環境 | 3.9+ 推奨。`pip install -r requirements.txt`（`anthropic[aws]` に boto3 等の依存を含む） |
| 検証用サンプルファイル | 日本語の `.pptx`。社外秘でない/匿名化済みのもの（Anthropic基盤を経由するため） |

## セットアップ

```bash
python -m venv .venv
.venv\Scripts\activate.bat        # Windows
pip install -r requirements.txt

copy .env.sample .env
# .env を編集して AWS_REGION / ANTHROPIC_AWS_WORKSPACE_ID / 認証情報を設定
```

## 実行手順

```bash
cd src

# Step 0: pptx スキルが利用可能か確認
python check_skills.py

# Step 1〜3: アップロード → 翻訳・再構成 → ダウンロード を通しで実行
python translate_pptx.py ../samples/input_ja.pptx --output ../output/output_en.pptx
```

成功すると `output/output_en.pptx` に翻訳済みファイルが生成されます。
PowerPoint（または LibreOffice Impress）で開き、レイアウト保持と翻訳品質を目視確認してください。

## 想定される失敗パターン

- `AttributeError` (client.beta.skills / files 等が見つからない) → `anthropic` SDK のバージョンが古い可能性。`pip install -U "anthropic[aws]"` でアップグレード
- `RuntimeError: 必須の環境変数が未設定です` → `.env` の設定漏れ
- `403` → `ANTHROPIC_AWS_WORKSPACE_ID` の誤り、またはIAMプリンシパルに必要なアクション権限が付与されていない
- `bash_code_execution_tool_result` の `return_code` が非0 → `stderr` を確認（スキルが無効、依存ライブラリ不足、入力ファイル形式の問題など）
- タイムアウト（スライド数が多い場合）→ `client.beta.messages.stream(...)` への切り替えを検討（未実装、要拡張）
