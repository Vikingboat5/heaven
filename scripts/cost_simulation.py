"""Sprint 0 / T0.3 — LLM 成本实测与推演

两种模式:
1. 推演模式(默认): 基于交互模型 × 刊例价格, 推算单宠物日成本与规模化月成本
2. 实测模式(--live): 真实调用 LLM 测量一轮对话 + 一次日志润色的 token, 代入模型

用法:
    python scripts/cost_simulation.py
    python scripts/cost_simulation.py --live
    python scripts/cost_simulation.py --turns 20 --dau 10000

注意: 价格为撰写时公开刊例(元/百万tokens), 实际以火山引擎官网实时价格为准。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_KEY = os.environ["ARK_API_KEY"]  # 从环境变量/backend/.env 读取, 禁止硬编码 key
BASE_URL = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/plan/v1")
MODEL = os.environ.get("ARK_MODEL", "kimi-k3")

REPORT_PATH = Path(__file__).resolve().parents[1] / "docs" / "poc" / "cost-baseline-report.md"


@dataclass(frozen=True)
class ModelPricing:
    name: str
    input_per_m: float   # 元 / 百万 tokens (输入)
    output_per_m: float  # 元 / 百万 tokens (输出)


# 刊例价(需以官网实时为准): https://www.volcengine.com/docs/82379/1099320
PRICING = {
    "doubao-lite": ModelPricing("doubao-lite", 0.3, 0.6),
    "doubao-pro": ModelPricing("doubao-pro", 0.8, 2.0),
    "deepseek-v3": ModelPricing("deepseek-v3", 2.0, 8.0),
}


@dataclass
class InteractionProfile:
    """单宠物单日交互模型"""
    dialogue_turns: int = 10          # 用户对话轮次
    dialogue_input_tokens: int = 1000  # 每轮输入(system persona+记忆+历史+用户消息)
    dialogue_output_tokens: int = 120  # 每轮输出(简短回复)
    adventure_logs: int = 1            # 离线日志润色次数
    log_input_tokens: int = 600        # 事件序列
    log_output_tokens: int = 350       # 润色后叙事
    fact_extractions: int = 1          # 事实抽取次数
    fact_input_tokens: int = 1200      # 全天对话记录
    fact_output_tokens: int = 100      # 抽取的事实


def cost_of(tokens_in: int, tokens_out: int, pricing: ModelPricing) -> float:
    return tokens_in * pricing.input_per_m / 1_000_000 + tokens_out * pricing.output_per_m / 1_000_000


def daily_cost(p: InteractionProfile, dialogue_model: ModelPricing, aux_model: ModelPricing) -> dict:
    dialogue = p.dialogue_turns * cost_of(p.dialogue_input_tokens, p.dialogue_output_tokens, dialogue_model)
    logs = p.adventure_logs * cost_of(p.log_input_tokens, p.log_output_tokens, aux_model)
    facts = p.fact_extractions * cost_of(p.fact_input_tokens, p.fact_output_tokens, aux_model)
    return {
        "dialogue": round(dialogue, 5),
        "adventure_log": round(logs, 5),
        "fact_extraction": round(facts, 5),
        "total": round(dialogue + logs + facts, 5),
    }


def render_report(p: InteractionProfile, live_note: str = "") -> str:
    scenarios = {
        "方案A 全部lite档": ("doubao-lite", "doubao-lite"),
        "方案B 对话pro+其余lite (推荐)": ("doubao-pro", "doubao-lite"),
        "方案C 全部pro档": ("doubao-pro", "doubao-pro"),
        "方案D 对话deepseek+其余lite": ("deepseek-v3", "doubao-lite"),
    }
    lines = [
        "# 成本基线报告 (Sprint 0 / T0.3)",
        "",
        f"- 日期: {time.strftime('%Y-%m-%d')}",
        f"- 交互模型: 对话 {p.dialogue_turns} 轮/日 (输入~{p.dialogue_input_tokens}/输出~{p.dialogue_output_tokens} tokens), "
        f"日志润色 {p.adventure_logs} 次/日, 事实抽取 {p.fact_extractions} 次/日",
        f"- 价格: 火山引擎刊例价(元/百万tokens), 需以官网实时为准{live_note}",
        "",
        "## 单宠物单日成本 (元)",
        "",
        "| 方案 | 对话 | 日志润色 | 事实抽取 | 合计/日 | 合计/月(30天) |",
        "|------|------|---------|---------|--------|--------------|",
    ]
    monthly_of = {}
    for label, (dlg, aux) in scenarios.items():
        c = daily_cost(p, PRICING[dlg], PRICING[aux])
        monthly = round(c["total"] * 30, 3)
        monthly_of[label] = monthly
        lines.append(f"| {label} | {c['dialogue']} | {c['adventure_log']} | {c['fact_extraction']} | {c['total']} | {monthly} |")

    recommended = monthly_of["方案B 对话pro+其余lite (推荐)"]
    lines += [
        "",
        "## 规模化月成本 (方案B, 元/月)",
        "",
        "| 活跃宠物数 | 月成本 |",
        "|-----------|--------|",
    ]
    for dau in [1_000, 10_000, 100_000]:
        lines.append(f"| {dau:,} | {round(recommended * dau, 0):,.0f} |")

    lines += [
        "",
        "## 结论与配额建议",
        "",
        f"1. 推荐方案B: 单宠物日成本约 {daily_cost(p, PRICING['doubao-pro'], PRICING['doubao-lite'])['total']} 元, 月约 {recommended} 元",
        f"2. 免费用户对话轮次上限建议: {p.dialogue_turns} 轮/日 (超出走 lite 档或提示明日再来, 内购预留点)",
        "3. 单宠物每日 token 熔断配额建议: 20000 tokens (覆盖 10 轮对话 + 1 次日志 + 1 次抽取, 留 2x 余量)",
        "4. 离线行为决策零 LLM (规则引擎), 这是成本可控的前提, 架构上已保证",
        "5. 若成本敏感: 对话档降级为 lite (方案A), 成本再降约 60%, 需内测验证对话质量是否可接受",
    ]
    return "\n".join(lines)


async def measure_live(p: InteractionProfile) -> str:
    """实测一轮对话 + 一次日志润色的真实 token 消耗"""
    import httpx

    from backend.app.core.persona import Personality, PetState, build_system_prompt

    prompt = build_system_prompt("团子", "小狐狸", Personality(tags=["傲娇"]), PetState())
    log_events = json.dumps([
        {"time": "14:20", "event": "离开家, 前往萤火森林"},
        {"time": "15:05", "event": "遇到一只迷路的小刺猬, 分享了浆果"},
        {"time": "16:40", "event": "在溪边发现闪亮的鹅卵石×3"},
        {"time": "18:10", "event": "天黑前回家, 有点累但很开心"},
    ], ensure_ascii=False)

    calls = [
        ("dialogue", [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "我回来啦！今天好想你"},
        ], 300),
        ("log_polish", [
            {"role": "system", "content": "你是宠物冒险日志的润色助手。把事件列表改写成 150 字以内、温馨可爱的第一人称冒险小故事。只输出故事正文。"},
            {"role": "user", "content": f"事件列表:\n{log_events}"},
        ], 500),
    ]

    measured: dict[str, dict] = {}
    async with httpx.AsyncClient(base_url=BASE_URL, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=120) as client:
        for name, messages, max_tokens in calls:
            resp = await client.post("/chat/completions", json={"model": MODEL, "messages": messages, "max_tokens": max_tokens})
            resp.raise_for_status()
            data = resp.json()
            usage = data.get("usage") or {}
            measured[name] = {
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "sample": (data["choices"][0]["message"].get("content") or "")[:120],
            }

    # 用实测值更新交互模型
    if measured["dialogue"]["prompt_tokens"]:
        p.dialogue_input_tokens = measured["dialogue"]["prompt_tokens"]
        p.dialogue_output_tokens = measured["dialogue"]["completion_tokens"]
    if measured["log_polish"]["prompt_tokens"]:
        p.log_input_tokens = measured["log_polish"]["prompt_tokens"]
        p.log_output_tokens = measured["log_polish"]["completion_tokens"]

    return (
        f"\n- 实测(模型 {MODEL}): 单轮对话 {measured['dialogue']['prompt_tokens']}+{measured['dialogue']['completion_tokens']} tokens, "
        f"日志润色 {measured['log_polish']['prompt_tokens']}+{measured['log_polish']['completion_tokens']} tokens (已代入模型)"
        f"\n- 实测对话样例: {measured['dialogue']['sample']}"
        f"\n- 实测日志样例: {measured['log_polish']['sample']}"
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="真实调用 LLM 测量 token")
    parser.add_argument("--turns", type=int, default=10, help="每日对话轮次")
    parser.add_argument("--dau", type=int, default=None, help="额外推算指定活跃规模")
    args = parser.parse_args()

    profile = InteractionProfile(dialogue_turns=args.turns)
    live_note = ""
    if args.live:
        live_note = await measure_live(profile)

    report = render_report(profile, live_note)
    if args.dau:
        monthly = daily_cost(profile, PRICING["doubao-pro"], PRICING["doubao-lite"])["total"] * 30
        report += f"\n\n指定规模 {args.dau:,} 活跃宠物: 月成本约 {monthly * args.dau:,.0f} 元 (方案B)"

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n报告已写入: {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
