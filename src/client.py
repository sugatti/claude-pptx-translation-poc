"""Claude Platform on AWS 用クライアントの初期化。

必須の環境変数（デフォルト値なし）:
    AWS_REGION                  例: ap-northeast-1
    ANTHROPIC_AWS_WORKSPACE_ID  Claude ワークスペースのID

認証は以下のいずれか:
    - ANTHROPIC_API_KEY が設定されていれば短期APIキー認証（最大12時間で失効）
    - 未設定なら標準のAWS認証情報チェーンでSigV4署名
"""

from __future__ import annotations

import os

from anthropic import AnthropicAWS
from dotenv import load_dotenv

load_dotenv()

REQUIRED_ENV_VARS = ("AWS_REGION", "ANTHROPIC_AWS_WORKSPACE_ID")


def build_client() -> AnthropicAWS:
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"必須の環境変数が未設定です: {', '.join(missing)}\n"
            f".env.sample を参考に .env を作成してください。"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return AnthropicAWS(api_key=api_key)
    return AnthropicAWS()
