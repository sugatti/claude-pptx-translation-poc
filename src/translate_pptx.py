"""Claude API (Claude Platform on AWS) による pptx 自動翻訳 検証スクリプト。

Step 1: Files API で pptx をアップロード
Step 2: Code Execution + Agent Skills (pptx) で翻訳・再構成
Step 3: 生成された pptx を Files API でダウンロード

使い方:
    python src/translate_pptx.py samples/input_ja.pptx \
        --output output/output_en.pptx \
        --target-lang 英語

前提条件（docs/automatic-translation.md 参照）:
    - AWS_REGION / ANTHROPIC_AWS_WORKSPACE_ID が .env に設定済み
    - 認証情報（短期APIキー or AWS認証情報チェーン）が有効
    - ワークスペースで pptx スキルが有効（事前に check_skills.py で確認）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from client import build_client

MODEL = "claude-sonnet-5"
SKILL_ID = "pptx"
# pptxスキルはSKILL.md読込→unzip→スライドごとのXML確認→翻訳→再パッケージ、と
# 何ラウンドもコード実行を挟むため、既定の16000では応答途中で打ち切られやすい。
# ストリーミングでタイムアウトの心配はないため大きめに確保する。
MAX_TOKENS = 64000

# Files API・Code Execution・Agent Skills（container.skills）はいずれもGA済みのため
# client.beta.* / betas=[...] は不要（PHP SDKのみ現時点でbetaネームスペースが必要）。


def build_prompt(target_lang: str) -> str:
    return (
        f"添付の pptx ファイルを日本語から{target_lang}に翻訳してください。\n"
        "以下を厳守してください:\n"
        "- レイアウト・書式・フォントサイズ・画像・表・図形の位置はすべて元のまま保持する\n"
        "- スライド内のテキスト（本文・タイトル・図形内テキスト・表のセルを含む）のみを翻訳する\n"
        "- スライドマスター/レイアウト内の固定テキストがあれば同様に翻訳する\n"
        "- 翻訳後のファイルを新規の pptx として生成する"
    )


def upload_file(client, input_path: Path):
    print(f"[Step 1] アップロード中: {input_path}")
    uploaded = client.files.upload(file=input_path)
    print(f"[Step 1] file_id = {uploaded.id} ({uploaded.size_bytes} bytes)")

    meta = client.files.retrieve_metadata(uploaded.id)
    print(f"[Step 1] filename = {meta.filename}, mime_type = {meta.mime_type}")
    return uploaded


def translate(
    client, uploaded, target_lang: str, model: str, max_tokens: int = MAX_TOKENS
) -> str | None:
    print(f"[Step 2] 翻訳リクエスト送信中 (model={model}, skill={SKILL_ID}, max_tokens={max_tokens})")

    # code execution + skills はサーバ側で複数ラウンドのコード実行を行うため
    # レスポンスまでに数分かかることがある。非ストリーミングだと途中で
    # 中継プロキシ等にコネクションを切られる（Server disconnected without
    # sending a response）ことがあるため、ストリーミングで接続を維持する。
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        container={
            "skills": [
                {"type": "anthropic", "skill_id": SKILL_ID, "version": "latest"}
            ]
        },
        tools=[{"type": "code_execution_20260521", "name": "code_execution"}],
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": build_prompt(target_lang)},
                    {"type": "container_upload", "file_id": uploaded.id},
                ],
            }
        ],
    ) as stream:
        for event in stream:
            if event.type == "content_block_start" and event.content_block.type == "server_tool_use":
                print(f"[code_execution] 開始: input={getattr(event.content_block, 'input', {})}")
            elif event.type == "text":
                # テキストの増分。逐次表示したい場合はここで print(event.text, end="")
                pass
        response = stream.get_final_message()

    print(f"[Step 2] stop_reason = {response.stop_reason}")
    if response.stop_reason == "max_tokens":
        print(
            f"[Step 2][警告] max_tokens（{max_tokens}）に到達し、"
            "応答が途中で打ち切られました。--max-tokens で引き上げるか、"
            "スライド数を減らして再試行してください。",
            file=sys.stderr,
        )

    output_file_id = None
    for block in response.content:
        if block.type == "text":
            print(f"[Claude] {block.text}")
        elif block.type == "server_tool_use":
            print(f"[code_execution] input={block.input}")
        elif block.type == "bash_code_execution_tool_result":
            result = block.content
            return_code = getattr(result, "return_code", None)
            print(f"[Step 2] code_execution result: return_code={return_code}")
            stderr = getattr(result, "stderr", None)
            if stderr:
                print(f"[Step 2][stderr] {stderr}")
            content = getattr(result, "content", None) or []
            for item in content:
                if item.type == "bash_code_execution_output":
                    output_file_id = item.file_id
                    print(f"[Step 2] 生成ファイル file_id = {output_file_id}")

    if output_file_id is None:
        print(
            "[Step 2][警告] 生成ファイルの file_id が見つかりませんでした。"
            "response.content の内容を確認してください。",
            file=sys.stderr,
        )

    return output_file_id


def download(client, output_file_id: str, output_path: Path) -> None:
    print(f"[Step 3] ダウンロード中: file_id={output_file_id}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = client.files.download(output_file_id)
    content.write_to_file(str(output_path))
    print(f"[Step 3] 保存しました: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="翻訳対象の .pptx ファイルパス")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/output_en.pptx"),
        help="翻訳後ファイルの保存先（既定: output/output_en.pptx）",
    )
    parser.add_argument(
        "--target-lang",
        default="英語",
        help="翻訳先言語（既定: 英語）",
    )
    parser.add_argument(
        "--model",
        default=MODEL,
        help=f"使用モデル（既定: {MODEL}）",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=MAX_TOKENS,
        help=f"応答の最大トークン数（既定: {MAX_TOKENS}）。"
        "途中で打ち切られる場合は引き上げてください。",
    )
    args = parser.parse_args()

    if not args.input.exists():
        parser.error(f"入力ファイルが見つかりません: {args.input}")

    client = build_client()

    uploaded = upload_file(client, args.input)
    output_file_id = translate(
        client, uploaded, args.target_lang, args.model, args.max_tokens
    )

    if output_file_id is None:
        sys.exit(1)

    download(client, output_file_id, args.output)


if __name__ == "__main__":
    main()
