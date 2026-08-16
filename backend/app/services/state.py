"""T2.2 情绪/需求状态机: 惰性衰减 + 喂食/休息

惰性衰减: 不跑调度器, 在读取宠物时按 elapsed 时间一次性结算。
喂食/休息走每日限次(daily_limit), 并触发任务事件。
"""
from datetime import datetime

from sqlalchemy.orm import Session

from ..core.gamedata import (
    DECAY_PER_HOUR,
    EXP_PER_LEVEL,
    FEED_DAILY_LIMIT,
    FEED_MOOD,
    FEED_SATIETY,
    MOOD_DRIFT_PER_HOUR,
    REST_DAILY_LIMIT,
    REST_ENERGY,
    STATE_FLOOR,
)
from ..models import Pet
from .daily_limit import limiter


class StateError(Exception):
    """业务异常: detail 直接返回前端"""


def _clamp(value: float, low: float = 0, high: float = 100) -> int:
    return int(min(high, max(low, round(value))))


def apply_lazy_decay(db: Session, pet: Pet) -> bool:
    """按距上次结算的时长衰减状态。返回是否有变化。"""
    now = datetime.utcnow()
    last = pet.state_updated_at or pet.created_at or now
    hours = max(0.0, (now - last).total_seconds() / 3600)
    if hours < 1 / 60:  # 不足 1 分钟不结算, 避免频繁写库
        return False

    state = dict(pet.state or {})
    state["satiety"] = _clamp(state.get("satiety", 80) - DECAY_PER_HOUR["satiety"] * hours, STATE_FLOOR)
    state["energy"] = _clamp(state.get("energy", 90) - DECAY_PER_HOUR["energy"] * hours, STATE_FLOOR)
    mood = float(state.get("mood", 70))
    drift = min(abs(50 - mood), MOOD_DRIFT_PER_HOUR * hours)
    state["mood"] = _clamp(mood + (drift if mood < 50 else -drift))

    pet.state = state
    pet.state_updated_at = now
    db.commit()
    return True


def gain_exp(pet: Pet, amount: int) -> int:
    """加经验并处理升级, 返回升了几级。调用方负责 commit。"""
    if amount <= 0:
        return 0
    pet.exp += amount
    levels = 0
    while pet.exp >= pet.level * EXP_PER_LEVEL:
        pet.exp -= pet.level * EXP_PER_LEVEL
        pet.level += 1
        levels += 1
    return levels


def add_item(pet: Pet, item_name: str, count: int = 1) -> None:
    """往背包放道具。调用方负责 commit。"""
    inventory = [dict(entry) for entry in (pet.inventory or [])]
    for entry in inventory:
        if entry.get("item") == item_name:
            entry["count"] = int(entry.get("count", 0)) + count
            pet.inventory = inventory
            return
    inventory.append({"item": item_name, "count": count})
    pet.inventory = inventory


def feed(db: Session, pet: Pet) -> Pet:
    """喂食: 饱食+30 心情+5, 每日限次"""
    apply_lazy_decay(db, pet)
    allowed, _ = limiter.hit("feed", pet.id, FEED_DAILY_LIMIT)
    if not allowed:
        raise StateError("今天已经喂过啦, 小家伙吃不下了")
    state = dict(pet.state or {})
    state["satiety"] = _clamp(state.get("satiety", 80) + FEED_SATIETY)
    state["mood"] = _clamp(state.get("mood", 70) + FEED_MOOD)
    pet.state = state
    pet.state_updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pet)
    return pet


def rest(db: Session, pet: Pet) -> Pet:
    """休息: 精力+40, 每日限次"""
    apply_lazy_decay(db, pet)
    allowed, _ = limiter.hit("rest", pet.id, REST_DAILY_LIMIT)
    if not allowed:
        raise StateError("小家伙现在还不困")
    state = dict(pet.state or {})
    state["energy"] = _clamp(state.get("energy", 90) + REST_ENERGY)
    pet.state = state
    pet.state_updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pet)
    return pet
