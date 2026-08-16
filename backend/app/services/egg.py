"""宠物蛋服务: 获取/照料/孵化"""
from __future__ import annotations

import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from ..core.gamedata import (
    CARE_DAILY_LIMIT,
    CARE_VALUE,
    HATCH_VALUE_TARGET,
    REGISTRATION_EGG_RARITY,
)
from ..models import Egg, Pet
from .daily_limit import limiter
from .generation import generate_pet
from .quiz import build_bias


class EggError(Exception):
    """业务异常: detail 直接返回给前端"""


def create_egg(db: Session, owner_id: int, rarity: str = REGISTRATION_EGG_RARITY) -> Egg:
    egg = Egg(owner_id=owner_id, rarity=rarity, hatch_seed=secrets.token_hex(16))
    db.add(egg)
    db.flush()
    return egg


def get_current_egg(db: Session, owner_id: int) -> Egg | None:
    return (
        db.query(Egg)
        .filter(Egg.owner_id == owner_id, Egg.status == "incubating")
        .order_by(Egg.id.desc())
        .first()
    )


def care_remaining(egg_id: int) -> int:
    return max(0, CARE_DAILY_LIMIT - limiter.used("egg_care", egg_id))


def care_egg(db: Session, egg: Egg) -> Egg:
    """照料宠物蛋: +孵化值, 每日限次"""
    if egg.status != "incubating":
        raise EggError("这颗蛋已经孵化了")
    allowed, _ = limiter.hit("egg_care", egg.id, CARE_DAILY_LIMIT)
    if not allowed:
        raise EggError("今天的照料次数用完啦, 明天再来吧")
    egg.hatch_value = min(HATCH_VALUE_TARGET, egg.hatch_value + CARE_VALUE)
    db.commit()
    db.refresh(egg)
    return egg


def hatch_egg(db: Session, egg: Egg, name: str | None = None) -> Pet:
    """孵化: 种子化随机生成宠物"""
    if egg.status != "incubating":
        raise EggError("这颗蛋已经孵化了")
    if egg.hatch_value < HATCH_VALUE_TARGET:
        raise EggError(f"孵化值还不够 ({egg.hatch_value}/{HATCH_VALUE_TARGET}), 继续照料吧")

    # 诞生问答倾向注入(Sprint 3): 问答定基调, 种子随机保留惊喜
    bias = build_bias(egg.quiz_answers or {})
    generated = generate_pet(seed=egg.hatch_seed, rarity=egg.rarity, bias=bias)
    pet = Pet(
        owner_id=egg.owner_id,
        name=(name or "").strip() or generated.suggested_name,
        species=generated.species_name,
        color=generated.color,
        rarity=egg.rarity,
        personality=generated.personality,
        talents=generated.talents,
        skills=generated.skills,
        state={"mood": 70, "satiety": 80, "energy": 90},
        hatch_seed=egg.hatch_seed,
    )
    db.add(pet)
    egg.status = "hatched"
    egg.hatched_at = datetime.utcnow()
    db.commit()
    db.refresh(pet)
    return pet
