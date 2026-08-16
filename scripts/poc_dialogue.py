"""Sprint 0 / T0.2 — 性格化对话 POC

验证目标: 同一套问题下, 两种性格(傲娇 vs 粘人话痨)的回复风格是否可区分。

用法:
    python scripts/poc_dialogue.py            # 真实调用 LLM (默认 plan 代理 kimi-k3)
    python scripts/poc_dialogue.py --mock     # 离线 mock, 仅验证流程

产出: docs/poc/poc-dialogue-results.md (供人工盲测)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.core.persona import Personality, PetState, build_system_prompt  # noqa: E402

# ---- POC 配置 (默认走环境已有 plan 代理; 可用环境变量覆盖) ----
API_KEY = os.environ["ARK_API_KEY"]  # 从环境变量读取, 禁止硬编码 key
BASE_URL = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/plan/v1")
MODEL = os.environ.get("ARK_MODEL", "kimi-k3")

RESULTS_PATH = Path(__file__).resolve().parents[1] / "docs" / "poc" / "poc-dialogue-results.md"

PETS = [
    {
        "name": "团子", "species": "小狐狸",
        "persona": Personality(extraversion=45, agreeableness=30, conscientiousness=60, stability=50, openness=55, tags=["傲娇"]),
        "desc": "傲娇(低亲和+傲娇标签)",
    },
    {
        "name": "糯米", "species": "垂耳兔",
        "persona": Personality(extraversion=88, agreeableness=92, conscientiousness=40, stability=60, openness=70, tags=["话痨"]),
        "desc": "粘人话痨(高外向+高亲和+话痨标签)",
    },
]

QUESTIONS = [
    "我回来啦！",
    "今天工作好累啊……",
    "你觉得我是个什么样的主人？",
]

# 风格标记词(用于客观佐证风格差异, 人工盲测为主)
TSUNDERE_MARKERS = ["哼", "才不是", "才没", "别误会", "笨蛋", "谁让"]
SWEET_MARKERS = ["主人", "想你", "抱抱", "最喜欢", "开心", "陪你"]


async def call_llm(system_prompt: str, question: str) -> dict:
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=120,
    ) as client:
        resp = await client.post(
            "/chat/completions",
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                "max_tokens": 300,
                "temperature": 0.8,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "content": data["choices"][0]["message"].get("content") or "",
            "usage": data.get("usage") or {},
        }


def mock_reply(pet_desc: str, question: str) -> str:
    if "傲娇" in pet_desc:
        return "哼, 才、才不是特意等你回来呢……(尾巴却摇个不停)"
    return "主人主人！你终于回来啦！我好想你！今天我给你讲哦, 我发现了好多好玩的事情……"


def count_markers(text: str, markers: list[str]) -> int:
    return sum(text.count(m) for m in markers)


async def run(mock: bool) -> None:
    lines: list[str] = [
        "# 性格化对话 POC 结果",
        "",
        f"- 日期: {time.strftime('%Y-%m-%d %H:%M')}",
        f"- 模型: {MODEL} ({'mock' if mock else BASE_URL})",
        f"- 宠物A: {PETS[0]['name']} — {PETS[0]['desc']}",
        f"- 宠物B: {PETS[1]['name']} — {PETS[1]['desc']}",
        "",
        "---",
        "",
    ]
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    for q in QUESTIONS:
        lines.append(f"## 问题: 「{q}」\n")
        for pet in PETS:
            prompt = build_system_prompt(pet["name"], pet["species"], pet["persona"], PetState())
            if mock:
                content, usage = mock_reply(pet["desc"], q), {}
            else:
                result = await call_llm(prompt, q)
                content, usage = result["content"], result["usage"]
                total_usage["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
                total_usage["completion_tokens"] += int(usage.get("completion_tokens", 0))

            tsun = count_markers(content, TSUNDERE_MARKERS)
            sweet = count_markers(content, SWEET_MARKERS)
            lines.append(f"**{pet['name']}** ({pet['desc']}):\n")
            lines.append(f"> {content}\n")
            lines.append(f"- 风格标记: 傲娇系×{tsun} / 甜系×{sweet} | tokens: {usage.get('prompt_tokens', '-')}+{usage.get('completion_tokens', '-')}\n")
        lines.append("---\n")

    lines += [
        "## 结论判定",
        "",
        "- [ ] 人工盲测: 不看标签的情况下, 能否区分两只宠物的性格? (目标: 可区分)",
        "- [ ] 傲娇系标记集中在宠物A, 甜系标记集中在宠物B",
        "",
        f"本次 POC 总 token 消耗: prompt={total_usage['prompt_tokens']}, completion={total_usage['completion_tokens']}",
    ]

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"结果已写入: {RESULTS_PATH}")
    print("\n".join(lines[:80]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="离线 mock 模式")
    args = parser.parse_args()
    asyncio.run(run(mock=args.mock))
