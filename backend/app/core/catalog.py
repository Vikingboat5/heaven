"""内容目录: 物品定义(ItemDef) + 旅行种子(Seed) 的加载与校验

单一事实来源 = backend/app/content/*.json (配置即代码, 版本化+可单测)。
校验失败 = 内容事故, 响亮报错(抛 ContentError), 不允许带病运行。

校验项 (spec §3):
- 结构合法(必填字段/枚举值)
- 物品/角色引用存在, npc id 带 "npc:" 前缀
- 事件卡组基调标签合法; "{item}" 占位必须有 item/items/loot 来源
- loot 权重和=100; 品级×属性矩阵约束(R3: 传说不做口粮)
- 全部文本过敏感词
"""
from __future__ import annotations

import json
from pathlib import Path

from .gamedata import SENSITIVE_WORDS

_CONTENT_DIR = Path(__file__).resolve().parents[1] / "content"

RARITIES = ("common", "rare", "epic")
RARITY_LABELS = {"common": "常见", "rare": "稀有", "epic": "传说"}
ITEM_ATTRS = ("food", "gift", "charm", "antique")
# 品级×属性矩阵 (spec §5.2): epic 不允许 food (R3 传说不可消耗)
_ATTR_MAX_RARITY = {"food": "rare", "gift": "epic", "charm": "epic", "antique": "epic"}

FLAVORS = ("encounter", "social", "collect", "food", "learn",
           "help", "thrill", "treasure", "wander", "rest")
FLAVOR_LABELS = {"encounter": "际遇回", "social": "交友回", "collect": "收集回",
                 "food": "美食回", "learn": "学艺回", "help": "助人回",
                 "thrill": "惊险回", "treasure": "寻宝回", "wander": "闲逛回",
                 "rest": "留白回"}
# 基调基准权重 (spec §7.2)
FLAVOR_WEIGHTS = {"encounter": 12, "social": 12, "collect": 18, "food": 10, "learn": 8,
                  "help": 10, "thrill": 8, "treasure": 7, "wander": 10, "rest": 5}

EVENT_TYPES = ("meet_character", "exchange", "receive_gift", "taste", "learn", "help",
               "weather", "festival", "danger_safe", "rest_nothing", "find_item",
               "treasure", "lost_way", "homesick", "meet_creature", "scenery")

# 通用兜底卡组: 种子没有某基调的卡时使用 (旧 FORAGE/REST 事件升级)
GENERIC_FOOD_EVENTS = [
    {"text": "在路边找到了一些{item}, 正好垫垫肚子", "type": "taste", "items": ["berry", "vanilla_herb", "sweet_root"], "exp": 4},
    {"text": "凭着好鼻子刨出了埋着的{item}", "type": "taste", "items": ["acorn", "small_potato"], "exp": 4},
]
GENERIC_REST_EVENTS = [
    {"text": "在软软的草地上睡了一觉", "type": "rest_nothing", "exp": 2},
    {"text": "蜷成一团打了个长长的盹", "type": "rest_nothing", "exp": 2},
    {"text": "趴在树荫下休息了一会儿", "type": "rest_nothing", "exp": 2},
]
SOCIALIZE_ANIMALS = ["小猫咪", "小土狗", "垂耳兔", "小仓鼠"]


class ContentError(Exception):
    """内容文件校验失败"""


def _fail(errors: list[str]) -> None:
    if errors:
        raise ContentError("内容校验失败:\n" + "\n".join(f"- {e}" for e in errors))


def _check_text(text: str, where: str, errors: list[str]) -> None:
    for w in SENSITIVE_WORDS:
        if w in text:
            errors.append(f"{where}: 命中敏感词[{w}]")


def load_items() -> dict[str, dict]:
    raw = json.loads((_CONTENT_DIR / "items.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    items: dict[str, dict] = {}
    for it in raw:
        iid = it.get("id", "?")
        for field in ("id", "name", "desc", "rarity", "attr", "appearance", "image"):
            if field not in it:
                errors.append(f"物品[{iid}]: 缺字段 {field}")
        if it.get("rarity") not in RARITIES:
            errors.append(f"物品[{iid}]: 非法品级 {it.get('rarity')}")
        if it.get("attr") not in ITEM_ATTRS:
            errors.append(f"物品[{iid}]: 非法属性 {it.get('attr')}")
        # R3: 传说不可消耗 → food 最高 rare
        if it.get("attr") == "food" and it.get("rarity") not in ("common", "rare"):
            errors.append(f"物品[{iid}]: 违反 R3, 口粮品级最高为稀有(当前 {it.get('rarity')})")
        if _ATTR_MAX_RARITY.get(it.get("attr", "")) and it.get("rarity") in RARITIES:
            if RARITIES.index(it["rarity"]) > RARITIES.index(_ATTR_MAX_RARITY[it["attr"]]):
                errors.append(f"物品[{iid}]: 品级超出属性上限")
        if iid in items:
            errors.append(f"物品[{iid}]: id 重复")
        _check_text(it.get("name", "") + it.get("desc", ""), f"物品[{iid}]", errors)
        items[iid] = it
    _fail(errors)
    return items


def load_seeds(items: dict[str, dict]) -> dict[str, dict]:
    raw = json.loads((_CONTENT_DIR / "seeds.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    seeds: dict[str, dict] = {}
    for s in raw:
        sid = s.get("id", "?")
        for field in ("id", "pack", "name", "min_level", "background", "atmosphere",
                      "fallback_item", "loot_table", "event_deck"):
            if field not in s:
                errors.append(f"种子[{sid}]: 缺字段 {field}")
        if sid in seeds:
            errors.append(f"种子[{sid}]: id 重复")
        # 角色卡
        for c in s.get("cast", []):
            if not str(c.get("id", "")).startswith("npc:"):
                errors.append(f"种子[{sid}]: 角色 {c.get('id')} 缺 npc: 前缀")
            _check_text(c.get("desc_words", ""), f"种子[{sid}]角色", errors)
        # loot 表
        total = sum(e.get("weight", 0) for e in s.get("loot_table", []))
        if total != 100:
            errors.append(f"种子[{sid}]: loot 权重和={total}, 应为 100")
        for e in s.get("loot_table", []):
            if e.get("item") not in items:
                errors.append(f"种子[{sid}]: loot 引用不存在的物品 {e.get('item')}")
        if s.get("fallback_item") not in items:
            errors.append(f"种子[{sid}]: fallback_item 不存在")
        # 事件卡组
        for flavor, events in s.get("event_deck", {}).items():
            if flavor not in FLAVORS:
                errors.append(f"种子[{sid}]: 非法基调 {flavor}")
            for ev in events:
                if ev.get("type") not in EVENT_TYPES:
                    errors.append(f"种子[{sid}]: 非法事件类型 {ev.get('type')}")
                if "{item}" in ev.get("text", "") and not (
                    ev.get("item") or ev.get("items") or ev.get("loot") or ev.get("loot_rare")
                ):
                    errors.append(f"种子[{sid}]: 事件含{{item}}但无物品来源: {ev.get('text')}")
                for ref in ([ev["item"]] if ev.get("item") else []) + list(ev.get("items", [])):
                    if ref not in items:
                        errors.append(f"种子[{sid}]: 事件引用不存在的物品 {ref}")
                if ev.get("npc") and ev["npc"] not in {c["id"] for c in s.get("cast", [])}:
                    errors.append(f"种子[{sid}]: 事件引用 cast 外的角色 {ev.get('npc')}")
                _check_text(ev.get("text", ""), f"种子[{sid}]事件", errors)
        _check_text(s.get("background", "") + s.get("name", ""), f"种子[{sid}]", errors)
        seeds[sid] = s
    _fail(errors)
    return seeds


ITEMS: dict[str, dict] = load_items()
SEEDS: dict[str, dict] = load_seeds(ITEMS)

# 旧名字 → item_id (存量 inventory 迁移用)
NAME_TO_ID: dict[str, str] = {it["name"]: it["id"] for it in ITEMS.values()}


def rarity_rank(rarity: str) -> int:
    return RARITIES.index(rarity)


def draw_loot(seed: dict, rng, *, min_rarity: str | None = None) -> str:
    """按 loot_table 加权抽物品; min_rarity 限定最低品级(寻宝回用)。"""
    table = seed["loot_table"]
    if min_rarity:
        floor = rarity_rank(min_rarity)
        table = [e for e in table if rarity_rank(ITEMS[e["item"]]["rarity"]) >= floor] or seed["loot_table"]
    weights = [e["weight"] for e in table]
    return rng.choices([e["item"] for e in table], weights=weights)[0]


def draw_exchange_result(seed: dict, rng, gave_item_id: str) -> str | None:
    """交换所得: 品级 >= 带出品级 (R2 硬约束)。无法满足时返回 None(=没换成, 原样带回)。"""
    gave_rank = rarity_rank(ITEMS[gave_item_id]["rarity"])
    candidates = [e["item"] for e in seed["loot_table"]
                  if rarity_rank(ITEMS[e["item"]]["rarity"]) >= gave_rank]
    if not candidates:
        return None
    return rng.choice(candidates)
