"""T2.4 行为引擎: 离线自主行为模拟 (纯规则 + 随机数 + 性格加权, 零 LLM)

成本架构核心: 离线期间宠物"活着"全靠本模块, 一个 token 都不花。
LLM 只在事后批量润色日志时介入(services/adventure.py, 每次离线 1 次 lite 调用)。

模拟方式: 把离线时长切成 tick(45分钟), 每个 tick 按状态+性格加权决定一个行为:
- 精力过低 → 强制休息
- 否则按权重随机: 探险(开放性) / 觅食(饥饿度) / 社交(外向性) / 玩耍 / 休息
- 夜行者天赋在夜间提升探险权重
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .gamedata import (
    ADVENTURE_EVENTS,
    ADVENTURE_MAX_TICKS,
    ADVENTURE_TICK_MINUTES,
    ADVENTURE_ZONES,
    FORAGE_EVENTS,
    PLAY_EVENTS,
    REST_EVENTS,
    SOCIALIZE_ANIMALS,
    SOCIALIZE_EVENTS,
)

_ZONE_EVENTS: dict[str, list[dict]] = {}
for _e in ADVENTURE_EVENTS:
    _ZONE_EVENTS.setdefault(_e["zone"], []).append(_e)


@dataclass
class SimulationResult:
    events: list[dict] = field(default_factory=list)
    final_state: dict = field(default_factory=dict)
    rewards: dict = field(default_factory=lambda: {"exp": 0, "items": []})


def _clamp(value: float) -> int:
    return int(min(100, max(0, round(value))))


def _fill(template: str, rng: random.Random, items: list[str] | None = None) -> str:
    text = template
    if "{item}" in text:
        text = text.replace("{item}", rng.choice(items or ["小东西"]))
    if "{animal}" in text:
        text = text.replace("{animal}", rng.choice(SOCIALIZE_ANIMALS))
    return text


def simulate_offline(
    *,
    personality: dict,
    talents: list[dict],
    level: int,
    state: dict,
    start: datetime,
    end: datetime,
    seed: str,
) -> SimulationResult:
    """模拟 start→end 的离线行为。同种子+同输入 → 同结果(可复现)。"""
    rng = random.Random(f"behavior:{seed}:{start.isoformat()}")
    result = SimulationResult()

    st = {
        "mood": int(state.get("mood", 70)),
        "satiety": int(state.get("satiety", 80)),
        "energy": int(state.get("energy", 90)),
    }
    talent_ids = {t.get("id") for t in (talents or [])}
    openness = int(personality.get("openness", 50))
    extraversion = int(personality.get("extraversion", 50))
    available_zones = [z for z in ADVENTURE_ZONES if z["min_level"] <= level] or ADVENTURE_ZONES[:1]

    tick = start
    ticks = 0
    while tick < end and ticks < ADVENTURE_MAX_TICKS:
        ticks += 1
        tick_end = tick + timedelta(minutes=ADVENTURE_TICK_MINUTES)
        night = tick.hour >= 20 or tick.hour < 6

        # ---- 行为决策 ----
        if st["energy"] < 25:
            action = "rest"
        else:
            weights = {
                "explore": 18 + openness * 0.45 + (12 if ("night_walker" in talent_ids and night) else 0) - (10 if (night and "night_walker" not in talent_ids) else 0),
                "forage": 6 + (100 - st["satiety"]) * 0.18,
                "socialize": 8 + extraversion * 0.35,
                "play": 10.0,
                "rest": 30.0 if st["energy"] < 45 else 6.0,
            }
            weights = {k: max(1.0, v) for k, v in weights.items()}
            action = rng.choices(list(weights.keys()), weights=list(weights.values()))[0]

        # ---- 行为结算 ----
        event: dict = {"time": tick.isoformat(timespec="minutes"), "type": action, "exp": 0}
        if action == "explore":
            zone = rng.choice(available_zones)
            template = rng.choice(_ZONE_EVENTS.get(zone["id"], []))
            text = _fill(template["text"], rng, template.get("items"))
            event.update({
                "zone": zone["name"],
                "text": f"在{zone['name']}, {text}",
                "exp": template.get("exp", 5),
                "event_type": template["type"],
            })
            if template["type"] in ("find_item", "treasure"):
                item = rng.choice(template.get("items", ["小东西"]))
                event["item"] = item
                result.rewards["items"].append(item)
                # 寻宝鼻: 额外物品概率
                if "treasure_nose" in talent_ids and rng.random() < 0.15 and len(template.get("items", [])) > 1:
                    extra = rng.choice(template["items"])
                    result.rewards["items"].append(extra)
            st["energy"] -= 14
            st["satiety"] -= 9
            st["mood"] += 2
        elif action == "forage":
            template = rng.choice(FORAGE_EVENTS)
            item = rng.choice(template["items"])
            event.update({"text": _fill(template["text"], rng, template["items"]), "item": item})
            result.rewards["items"].append(item)
            event["exp"] = 4
            st["satiety"] += 18
            st["energy"] -= 5
        elif action == "rest":
            event.update({"text": rng.choice(REST_EVENTS), "exp": 2})
            st["energy"] += 32
            st["mood"] += 1
        elif action == "socialize":
            event.update({"text": _fill(rng.choice(SOCIALIZE_EVENTS), rng), "exp": 6})
            st["mood"] += 6
            st["energy"] -= 8
        else:  # play
            event.update({"text": rng.choice(PLAY_EVENTS), "exp": 4})
            st["mood"] += 8
            st["energy"] -= 6

        for key in st:
            st[key] = _clamp(st[key])
        result.rewards["exp"] += int(event["exp"])
        result.events.append(event)
        tick = tick_end

    # 虹运: 随机收获 5% 翻倍
    if "rainbow_luck" in talent_ids and rng.random() < 0.05:
        result.rewards["exp"] *= 2

    result.final_state = st
    return result
