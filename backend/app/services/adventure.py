"""冒险服务 (P4 旅行青蛙化): 宠物出门旅行 + 归来带回纪念品/照片

状态机 (惰性, 每次回端检测推进):
- 在家 + 离线超阈值 → 自动出门 (auto-leave), 或手动 leave_now 送出门
- 旅行中 → 回来时若已到 back_at 则结算: 生成冒险日志(照片)+道具(纪念品)+经验
- 旅行中未到 back_at → 保持"旅行中", 主页显示空房, 对话锁定

成本: 行为决策零 LLM(behavior.py), 每次归来仅 1 次 lite 润色日志, 失败降级模板。
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..core.behavior import simulate_offline
from ..core.gamedata import ADVENTURE_ZONES, MAX_SIMULATE_HOURS
from ..llm.gateway import gateway
from ..models import AdventureLog, Pet, User
from .state import add_item, gain_exp

AUTO_LEAVE_MINUTES = 45    # 离线超过此时长, 宠物自动出门
TRAVEL_MIN_HOURS = 2       # 旅行最短时长
TRAVEL_MAX_HOURS = 6       # 旅行最长时长

_POLISH_SYSTEM = "你是宠物冒险日志润色助手。把事件列表改写成150字以内、温馨可爱的第一人称小故事(宠物视角, 可带动作表情)。只输出故事正文。"


def _fallback_narrative(pet_name: str, events: list[dict]) -> str:
    if not events:
        return f"{pet_name}出了一趟门, 安安静静地回来了。"
    highlights = "；".join(e["text"] for e in events[:3])
    return f"{pet_name}这次旅行去了不少地方：{highlights}。一共经历了 {len(events)} 件事, 平平安安地回家了。"


def is_away(pet: Pet) -> bool:
    """是否正在旅行中"""
    back_at = (pet.travel or {}).get("back_at")
    if not back_at:
        return False
    back_dt = _parse(back_at)
    return back_dt > datetime.utcnow()


def _parse(v: str | datetime) -> datetime:
    dt = datetime.fromisoformat(v) if isinstance(v, str) else v
    # 归一化为无时区 UTC, 避免与 datetime.utcnow() 比较报错
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _depart(pet: Pet, now: datetime) -> None:
    """让宠物出门: 随机目的地 + 随机时长(种子化可复现)"""
    rng = random.Random(f"travel:{pet.hatch_seed}:{now.isoformat()}")
    zone = rng.choice(ADVENTURE_ZONES)
    hours = rng.uniform(TRAVEL_MIN_HOURS, TRAVEL_MAX_HOURS)
    pet.travel = {
        "left_at": now.isoformat(),
        "back_at": (now + timedelta(hours=hours)).isoformat(),
        "dest": zone["name"],
    }


def leave_now(db: Session, pet: Pet) -> dict:
    """手动送出门 (P4: 主页"让它出门走走")"""
    if is_away(pet):
        return {"ok": False, "detail": "它已经在外面旅行啦"}
    _depart(pet, datetime.utcnow())
    db.commit()
    return {"ok": True, "back_at": _parse(pet.travel["back_at"]).isoformat(timespec="minutes"), "dest": pet.travel["dest"]}


async def _polish_narrative(pet: Pet, events: list[dict]) -> str:
    if not events:
        return _fallback_narrative(pet.name, events)
    lines = "\n".join(f"{e['time'][11:16]} {e['text']}" for e in events[:8])
    try:
        result = await gateway.chat(
            [
                {"role": "system", "content": _POLISH_SYSTEM},
                {"role": "user", "content": f"宠物「{pet.name}」的旅行事件:\n{lines}"},
            ],
            tier="lite",
            pet_id=str(pet.id),
            max_tokens=400,
            temperature=0.7,
        )
        narrative = result.content.strip()
        return narrative if narrative else _fallback_narrative(pet.name, events)
    except Exception:
        return _fallback_narrative(pet.name, events)


async def _settle_trip(db: Session, pet: Pet, travel: dict) -> AdventureLog:
    """旅行归来结算: 模拟整段旅行 + 生成日志(照片) + 结算纪念品/经验"""
    start = _parse(travel.get("left_at"))
    end = min(_parse(travel.get("back_at")), start + timedelta(hours=MAX_SIMULATE_HOURS))

    result = simulate_offline(
        personality=pet.personality or {},
        talents=pet.talents or [],
        level=pet.level,
        start=start,
        end=end,
        seed=f"{pet.hatch_seed}:{pet.id}",
    )
    narrative = await _polish_narrative(pet, result.events)

    log = AdventureLog(
        pet_id=pet.id,
        events=result.events,
        narrative=narrative,
        rewards=result.rewards,
        started_at=start,
        ended_at=end,
    )
    db.add(log)
    gain_exp(pet, int(result.rewards.get("exp", 0)))
    for item in result.rewards.get("items", []):
        add_item(pet, item)
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
        _depart(pet, now)
        db.commit()
        return {"event": "left", "log": None, "back_at": _parse(pet.travel["back_at"]).isoformat(timespec="minutes")}
    db.commit()
    return {"event": None, "log": None, "back_at": None}


def log_to_out(log: AdventureLog) -> dict:
    return {
        "id": log.id,
        "events": log.events,
        "narrative": log.narrative,
        "rewards": log.rewards,
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
