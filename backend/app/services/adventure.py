"""冒险服务 (v1.2 种子锚定版): 宠物出门旅行 + 归来带回纪念品/日记

状态机 (惰性, 每次回端检测推进):
- 在家 + 离线超阈值 → 自动出门 (auto-leave), 或手动 leave_now 送出门(可带行囊)
- 旅行中 → 回来时若已到 back_at 则结算: 选种子→抽基调→抽卡组→结算(规则) → LLM带背景成文
- 旅行中未到 back_at → 保持"旅行中", 主页显示空房, 对话锁定

成本: 行为决策零 LLM(behavior.py), 每次归来仅 1 次 lite 润色, 失败降级模板不丢数据。
红线: R2 交换不降级 / R5 日记陌生化转述(不出现真实人名地名)。
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..core import catalog
from ..core.behavior import simulate_trip
from ..core.gamedata import MAX_SIMULATE_HOURS
from ..llm.gateway import gateway
from ..models import AdventureLog, Pet, User
from . import items as item_service
from .state import add_item, count_item, gain_exp, remove_item

AUTO_LEAVE_MINUTES = 45    # 离线超过此时长, 宠物自动出门
TRAVEL_MIN_HOURS = 2       # 旅行最短时长
TRAVEL_MAX_HOURS = 6       # 旅行最长时长

_POLISH_SYSTEM = (
    "你是宠物写给主人的旅行信。根据旅行背景、基调和事件列表, 改写成150字以内、温馨可爱的"
    "第一人称(宠物视角)的信。规则:\n"
    "1. 这是写给主人的信, 像孩子给家长讲今天的见闻; 不是动作日志——"
    "禁止逐字描述自己的细枝末节动作(如\"我舔舔嘴巴\"), 禁止\"动作+冒号+感叹\"的句式。\n"
    "2. 逻辑自洽: 食物才能说好吃, 地方只能说美/好玩。\n"
    "3. 宠物不认识人类世界的名人和地名, 只能用它看到的模样来描述(陌生化转述), "
    "绝不写出真实人名/地名/作品名。\n"
    "4. 如果带回了物品, 自然地提到是想着主人才带回来的(挑1件提, 不罗列清单)。\n"
    "5. 结尾落在对主人的想念或期待分享上。\n"
    "只输出信的正文。"
)


def _item_names(item_ids: list[str]) -> list[str]:
    """item_id → 玩家可见名 (写信/兜底模板用)"""
    return [catalog.ITEMS[i]["name"] for i in item_ids if i in catalog.ITEMS]


def _fallback_narrative(pet_name: str, events: list[dict], item_ids: list[str] | None = None) -> str:
    names = _item_names(item_ids or [])
    gift_clause = f"还给主人带了「{names[0]}」, 想和你一起分享。" if names else ""
    if not events:
        return f"{pet_name}出了一趟门, 安安静静地回来了。{gift_clause}"
    highlights = "；".join(e["text"] for e in events[:3])
    return (f"{pet_name}这次旅行去了不少地方：{highlights}。{gift_clause}"
            f"一共经历了 {len(events)} 件事, 平平安安地回家了。")


def is_away(pet: Pet) -> bool:
    """是否正在旅行中"""
    back_at = (pet.travel or {}).get("back_at")
    if not back_at:
        return False
    return _parse(back_at) > datetime.utcnow()


def _parse(v: str | datetime) -> datetime:
    dt = datetime.fromisoformat(v) if isinstance(v, str) else v
    # 归一化为无时区 UTC, 避免与 datetime.utcnow() 比较报错
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def available_seeds(level: int) -> list[dict]:
    seeds = [s for s in catalog.SEEDS.values() if s["min_level"] <= level]
    return seeds or list(catalog.SEEDS.values())[:1]


def _depart(pet: Pet, now: datetime) -> dict:
    """让宠物出门: 随机种子(等级门控) + 随机时长(种子化可复现)"""
    rng = random.Random(f"travel:{pet.hatch_seed}:{now.isoformat()}")
    seed_def = rng.choice(available_seeds(pet.level))
    hours = rng.uniform(TRAVEL_MIN_HOURS, TRAVEL_MAX_HOURS)
    pet.travel = {
        "left_at": now.isoformat(),
        "back_at": (now + timedelta(hours=hours)).isoformat(),
        "dest": seed_def["name"],
        "seed": seed_def["id"],
    }
    return seed_def


def leave_now(db: Session, pet: Pet, loadout: dict | None = None) -> dict:
    """手动送出门 (可带行囊: {food?, gift?, charm?}, 空=空手出门合法)"""
    if is_away(pet):
        return {"ok": False, "detail": "它已经在外面旅行啦"}
    if loadout:
        err = validate_loadout(pet, loadout)
        if err:
            return {"ok": False, "detail": err}
        pet.loadout = {k: v for k, v in loadout.items() if v}
    else:
        pet.loadout = {}
    seed_def = _depart(pet, datetime.utcnow())
    db.commit()
    return {"ok": True, "back_at": _parse(pet.travel["back_at"]).isoformat(timespec="minutes"),
            "dest": seed_def["name"]}


def validate_loadout(pet: Pet, loadout: dict) -> str | None:
    """行囊校验: 槽位/属性匹配 + 背包持有。合法返回 None, 否则返回错误文案"""
    for slot, item_id in loadout.items():
        if not item_id:
            continue
        if slot not in ("food", "gift", "charm"):
            return f"未知槽位 {slot}"
        it = catalog.ITEMS.get(item_id)
        if it is None:
            return "背包里没有这个物品"
        if it["attr"] != slot:
            return f"「{it['name']}」放不进这个槽位"
        if count_item(pet, item_id) < 1:
            return f"「{it['name']}」数量不足"
    return None


async def _polish_narrative(pet: Pet, seed_def: dict, flavor: str, events: list[dict],
                            item_ids: list[str] | None = None) -> str:
    if not events:
        return _fallback_narrative(pet.name, events, item_ids)
    lines = "\n".join(f"{e['time'][11:16]} {e['text']}" for e in events[:8])
    cast = "；".join(c["desc_words"] for c in seed_def.get("cast", [])) or "无"
    names = _item_names(item_ids or [])
    gifts = "、".join(names) if names else "无"
    user_prompt = (
        f"宠物「{pet.name}」的旅行:\n"
        f"背景: {seed_def.get('background', '')} (氛围: {seed_def.get('atmosphere', '')})\n"
        f"出场的角色: {cast}\n"
        f"本趟基调: {catalog.FLAVOR_LABELS.get(flavor, flavor)}\n"
        f"带回给主人的物品: {gifts}\n"
        f"事件:\n{lines}"
    )
    try:
        result = await gateway.chat(
            [{"role": "system", "content": _POLISH_SYSTEM},
             {"role": "user", "content": user_prompt}],
            tier="lite",
            pet_id=str(pet.id),
            max_tokens=400,
            temperature=0.7,
        )
        narrative = result.content.strip()
        return narrative if narrative else _fallback_narrative(pet.name, events, item_ids)
    except Exception as e:
        print(f"[adventure] 日记润色失败, 降级模板: {e}")  # 兜底留痕
        return _fallback_narrative(pet.name, events, item_ids)


async def _settle_trip(db: Session, pet: Pet, travel: dict) -> AdventureLog:
    """旅行归来结算: 模拟整段旅行 + 日记 + 物品/行囊/首发现结算"""
    start = _parse(travel.get("left_at"))
    end = min(_parse(travel.get("back_at")), start + timedelta(hours=MAX_SIMULATE_HOURS))
    seed_def = catalog.SEEDS.get(travel.get("seed") or "") or available_seeds(pet.level)[0]

    result = simulate_trip(
        seed_def=seed_def,
        personality=pet.personality or {},
        talents=pet.talents or [],
        level=pet.level,
        start=start,
        end=end,
        seed=f"{pet.hatch_seed}:{pet.id}",
        loadout=pet.loadout or {},
    )
    narrative = await _polish_narrative(pet, seed_def, result.flavor, result.events,
                                        item_ids=result.rewards["items"])

    # ---- 物品结算: 收获入包(is_new) + 首发现回填 + 行囊消耗/交换扣减 ----
    gained: list[dict] = []
    for item_id in result.rewards["items"]:
        already = count_item(pet, item_id) > 0
        via = "exchange" if result.exchanged and item_id == result.exchanged.get("got") else "forage"
        add_item(pet, item_id, zone=seed_def["id"], via=via, is_new=True)
        item_service.mark_first_discovery(db, item_id, pet.owner_id)
        gained.append({"item": item_id, "is_new": not already})
    for item_id in result.consumed:
        remove_item(pet, item_id)
    if result.exchanged:
        remove_item(pet, result.exchanged["gave"])

    log = AdventureLog(
        pet_id=pet.id,
        events=result.events,
        narrative=narrative,
        rewards={
            "exp": int(result.rewards.get("exp", 0)),
            "items": gained,
            "consumed": result.consumed,
            "exchanged": result.exchanged,
            "gift_returned": result.gift_returned,
            "seed": seed_def["id"],
            "dest": seed_def["name"],
            "flavor": result.flavor,
        },
        started_at=start,
        ended_at=end,
    )
    db.add(log)
    gain_exp(pet, int(result.rewards.get("exp", 0)))
    pet.loadout = {}
    db.flush()
    return log


def get_my_pet_row(db: Session, user_id: int) -> Pet | None:
    return db.query(Pet).filter(Pet.owner_id == user_id).order_by(Pet.id.desc()).first()


async def check_and_simulate(db: Session, user: User) -> dict:
    """App 打开时调用: 推进旅行状态机。

    返回 {"event": "returned"|"left"|"traveling"|None, "log": dict|None, "back_at": str|None}
    """
    now = datetime.utcnow()
    pet = get_my_pet_row(db, user.id)
    if pet is None:
        user.last_seen_at = now
        db.commit()
        return {"event": None, "log": None, "back_at": None}

    travel = pet.travel or {}
    back_at = travel.get("back_at")
    if back_at:
        back_dt = _parse(back_at)
        if back_dt <= now:
            # 归来: 结算旅行
            log = await _settle_trip(db, pet, travel)
            pet.travel = {}
            user.last_seen_at = now
            db.commit()
            db.refresh(log)
            return {"event": "returned", "log": log_to_out(log), "back_at": None}
        # 仍在旅行中
        user.last_seen_at = now
        db.commit()
        return {"event": "traveling", "log": None, "back_at": back_dt.isoformat(timespec="minutes")}

    # 在家: 离线超阈值 → 自动出门
    last_seen = user.last_seen_at
    user.last_seen_at = now
    if last_seen is not None and (now - last_seen).total_seconds() / 60 >= AUTO_LEAVE_MINUTES:
        seed_def = _depart(pet, now)
        db.commit()
        return {"event": "left", "log": None,
                "back_at": _parse(pet.travel["back_at"]).isoformat(timespec="minutes"),
                "dest": seed_def["name"]}
    db.commit()
    return {"event": None, "log": None, "back_at": None}


def log_to_out(log: AdventureLog) -> dict:
    rewards = log.rewards or {}
    return {
        "id": log.id,
        "events": log.events,
        "narrative": log.narrative,
        "rewards": {
            "exp": int(rewards.get("exp", 0)),
            "items": item_service.reward_items_out(rewards.get("items", [])),
            "consumed": rewards.get("consumed", []),
            "exchanged": rewards.get("exchanged"),
            "gift_returned": bool(rewards.get("gift_returned", False)),
        },
        "dest": rewards.get("dest", ""),
        "flavor": rewards.get("flavor", ""),
        "started_at": log.started_at.isoformat(timespec="minutes") if log.started_at else None,
        "ended_at": log.ended_at.isoformat(timespec="minutes") if log.ended_at else None,
    }


def list_logs(db: Session, user_id: int, limit: int = 20) -> list[dict]:
    pet = get_my_pet_row(db, user_id)
    if pet is None:
        return []
    rows = (
        db.query(AdventureLog)
        .filter(AdventureLog.pet_id == pet.id)
        .order_by(AdventureLog.id.desc())
        .limit(limit)
        .all()
    )
    return [log_to_out(row) for row in rows]
