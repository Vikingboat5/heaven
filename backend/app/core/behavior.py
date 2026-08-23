"""行为引擎 (v1.2 种子锚定版): 纯规则 + 随机数 + 性格加权, 零 LLM

一趟旅行 = 选基调(flavor) → 围绕基调从种子事件卡组抽事件 → 结算行囊/收获。
LLM 只在事后润色日记时介入(services/adventure.py, 每次归来 1 次 lite 调用)。

确定性边界: 同种子+同输入 → 同结果(可复现); 收获/品级/消耗全部规则定, 措辞才归 LLM。
红线: R1 惊险事件安全解决零损失; R2 交换不降级; R4 时长不可加速。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import catalog
from .gamedata import ADVENTURE_MAX_TICKS, ADVENTURE_TICK_MINUTES


@dataclass
class SimulationResult:
    flavor: str = "wander"
    events: list[dict] = field(default_factory=list)
    rewards: dict = field(default_factory=lambda: {"exp": 0, "items": []})
    consumed: list[str] = field(default_factory=list)          # 行囊口粮(被吃掉)
    exchanged: dict | None = None                               # {"gave": id, "got": id, "with": npc_id}
    gift_returned: bool = False                                 # 伴手礼没换出去, 原样带回


def _fill(template: str, rng: random.Random, item_name: str | None = None) -> str:
    text = template
    if "{item}" in text:
        text = text.replace("{item}", item_name or "小东西")
    if "{animal}" in text:
        text = text.replace("{animal}", rng.choice(catalog.SOCIALIZE_ANIMALS))
    return text


def _flavor_weights(personality: dict, talents: list[dict]) -> dict[str, float]:
    """十基调基准权重 × 性格/天赋修正 (spec §7.2)"""
    w = {k: float(v) for k, v in catalog.FLAVOR_WEIGHTS.items()}
    tags = set(personality.get("tags", []))
    ext = int(personality.get("extraversion", 50))
    ope = int(personality.get("openness", 50))
    con = int(personality.get("conscientiousness", 50))
    agr = int(personality.get("agreeableness", 50))
    sta = int(personality.get("stability", 50))
    talent_ids = {t.get("id") for t in (talents or [])}

    if ext > 66:
        w["encounter"] *= 1.5; w["social"] *= 1.5
    if ext < 33:
        w["social"] *= 0.5
    if ope > 66:
        w["collect"] *= 1.5
    if con > 66:
        w["learn"] *= 1.5
    if agr > 66:
        w["help"] *= 1.5
    if sta > 66:
        w["rest"] *= 1.5
    if "吃货" in tags:
        w["food"] *= 2.0
    if "胆小" in tags:
        w["thrill"] *= 0.3; w["social"] *= 0.5
    if "good_appetite" in talent_ids:
        w["food"] *= 1.5
    if "treasure_nose" in talent_ids:
        w["treasure"] *= 1.5
    return w


def _pick_deck(seed_def: dict, flavor: str) -> list[dict]:
    """种子卡组 → 缺卡兜底: food→通用觅食, rest→通用休息, 其他→闲逛"""
    deck = seed_def.get("event_deck", {}).get(flavor) or []
    if deck:
        return deck
    if flavor == "food":
        return catalog.GENERIC_FOOD_EVENTS
    if flavor == "rest":
        return catalog.GENERIC_REST_EVENTS
    return seed_def.get("event_deck", {}).get("wander") or catalog.GENERIC_REST_EVENTS


def _event_item(ev: dict, seed_def: dict, rng: random.Random) -> str | None:
    """决定本事件产出的物品 id (无产出返回 None)"""
    if ev.get("item"):
        return ev["item"]
    if ev.get("items"):
        return rng.choice(ev["items"])
    if ev.get("loot_rare"):
        return catalog.draw_loot(seed_def, rng, min_rarity="rare")
    if ev.get("loot"):
        return catalog.draw_loot(seed_def, rng)
    if ev.get("receive"):  # help/receive_gift: 谢礼
        return catalog.draw_loot(seed_def, rng)
    return None


def simulate_trip(
    *,
    seed_def: dict,
    personality: dict,
    talents: list[dict],
    level: int,
    start: datetime,
    end: datetime,
    seed: str,
    loadout: dict | None = None,
) -> SimulationResult:
    """模拟 start→end 的一趟种子旅行。同种子+同输入 → 同结果(可复现)。"""
    rng = random.Random(f"trip:{seed}:{start.isoformat()}")
    result = SimulationResult()
    loadout = loadout or {}
    talent_ids = {t.get("id") for t in (talents or [])}
    ext = int(personality.get("extraversion", 50))

    # ---- 抽基调 ----
    weights = _flavor_weights(personality, talents)
    flavor = rng.choices(list(weights.keys()), weights=list(weights.values()))[0]
    result.flavor = flavor

    # ---- 留白回特例: 什么都没干, 睡一觉回来, 保底小物 (Q4) ----
    if flavor == "rest":
        ev = rng.choice(_pick_deck(seed_def, "rest"))
        exp = 5 if "nap_master" in talent_ids else int(ev.get("exp", 2))
        result.events.append({"time": start.isoformat(timespec="minutes"), "type": "rest_nothing",
                              "text": _fill(ev["text"], rng), "exp": exp})
        result.rewards["exp"] += exp
        fallback = seed_def["fallback_item"]
        result.rewards["items"].append(fallback)
        result.events.append({"time": start.isoformat(timespec="minutes"), "type": "find_item",
                              "text": f"回家路上顺手带回了{catalog.ITEMS[fallback]['name']}",
                              "exp": 0, "item": fallback})
        return result

    # ---- 普通旅行: 按 tick 抽事件 ----
    deck = _pick_deck(seed_def, flavor)
    tick = start
    ticks = 0
    mid_tick = max(1, min(ADVENTURE_MAX_TICKS, int((end - start).total_seconds() // 60 // ADVENTURE_TICK_MINUTES)) // 2)

    while tick < end and ticks < ADVENTURE_MAX_TICKS:
        ticks += 1
        tick_end = tick + timedelta(minutes=ADVENTURE_TICK_MINUTES)

        # 行囊结算点: 旅途中段
        if ticks == mid_tick:
            _settle_loadout(result, seed_def, loadout, rng, ext, tick)

        ev = rng.choice(deck)
        item_id = _event_item(ev, seed_def, rng)
        item_name = catalog.ITEMS[item_id]["name"] if item_id else None
        exp = int(ev.get("exp", 5))
        if ev["type"] == "rest_nothing" and "nap_master" in talent_ids:
            exp = 5  # 打盹高手: 休息也能攒灵感
        event = {"time": tick.isoformat(timespec="minutes"), "type": ev["type"],
                 "text": _fill(ev["text"], rng, item_name), "exp": exp}
        if ev.get("npc"):
            event["npc"] = ev["npc"]
        if item_id:
            event["item"] = item_id
            result.rewards["items"].append(item_id)
        result.rewards["exp"] += exp
        result.events.append(event)
        tick = tick_end

    # ---- 护身符: 旅途末尾追加一次寻宝机会 ----
    if loadout.get("charm") and rng.random() < 0.25:
        tdeck = seed_def.get("event_deck", {}).get("treasure") or []
        if tdeck:
            ev = rng.choice(tdeck)
            item_id = _event_item(ev, seed_def, rng)
            if item_id:
                result.rewards["items"].append(item_id)
                result.events.append({
                    "time": min(tick, end).isoformat(timespec="minutes"), "type": "treasure",
                    "text": _fill(ev["text"], rng, catalog.ITEMS[item_id]["name"]),
                    "exp": int(ev.get("exp", 15)), "item": item_id})
                result.rewards["exp"] += int(ev.get("exp", 15))

    # 虹运: 随机收获 5% 翻倍
    if "rainbow_luck" in talent_ids and rng.random() < 0.05:
        result.rewards["exp"] *= 2

    return result


def _settle_loadout(result: SimulationResult, seed_def: dict, loadout: dict,
                    rng: random.Random, extraversion: int, tick: datetime) -> None:
    """行囊中段结算: 口粮吃掉 / 伴手礼交换(R2) / 事件留痕"""
    ts = tick.isoformat(timespec="minutes")

    food = loadout.get("food")
    if food:
        result.consumed.append(food)
        name = catalog.ITEMS[food]["name"]
        result.events.append({"time": ts, "type": "taste",
                              "text": f"路上打开小包袱, 把{name}吃得干干净净, 元气满满", "exp": 5})
        result.rewards["exp"] += 5

    gift = loadout.get("gift")
    if gift:
        exchangers = [c for c in seed_def.get("cast", []) if "exchange" in c.get("interactions", [])]
        # 性格决定是否发起交换: 外向的宠物更爱主动换
        if exchangers and rng.random() < 0.3 + extraversion / 200:
            npc = rng.choice(exchangers)
            got = catalog.draw_exchange_result(seed_def, rng, gift)
            if got is not None:  # R2: 只存在不降级交换; 无法达成=没换成
                result.exchanged = {"gave": gift, "got": got, "with": npc["id"]}
                result.rewards["items"].append(got)
                result.events.append({
                    "time": ts, "type": "exchange", "npc": npc["id"],
                    "text": f"把{catalog.ITEMS[gift]['name']}送给了{npc['desc_words']}, "
                            f"换回{catalog.ITEMS[got]['name']}", "exp": 8})
                result.rewards["exp"] += 8
                return
        # 没换成: 原样带回 (性格表达, 文案兜底成萌点)
        result.gift_returned = True
        result.events.append({"time": ts, "type": "gift_returned",
                              "text": f"把{catalog.ITEMS[gift]['name']}揣在怀里出了门, "
                                      f"有点害羞, 又原样抱了回来", "exp": 2})
        result.rewards["exp"] += 2
