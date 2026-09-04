"""Step 0: ワークスペースで pptx スキル（Agent Skills）が利用可能か確認する。

使い方:
    python src/check_skills.py
"""

from __future__ import annotations

from client import build_client


def main() -> None:
    client = build_client()

    try:
        skills = list(client.skills.list())
    except AttributeError:
        print(
            "client.skills.list() が見つかりません。"
            "SDKのバージョンが古い可能性があります。"
            "`pip install -U \"anthropic[aws]\"` でアップグレードするか、"
            "GET /v1/skills をraw HTTPで叩いて確認してください"
            "（Skills APIはGA済みでbetaヘッダーは不要）。"
        )
        raise

    if not skills:
        print("利用可能なスキルが1件も見つかりませんでした。")
        return

    print(f"利用可能なスキル: {len(skills)} 件")
    for skill in skills:
        print(f"- id={skill.id} name={getattr(skill, 'name', '?')}")

    pptx_available = any(s.id == "pptx" for s in skills)
    print()
    print(f"pptx スキル: {'利用可能' if pptx_available else '利用不可（要確認）'}")


if __name__ == "__main__":
    main()
