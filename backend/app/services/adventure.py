"""T2.5/T2.6 冒险服务: 离线模拟编排 + 日志润色 + 收获结算

成本设计(架构文档第 3 节):
- 行为决策零 LLM(core/behavior.py 纯规则)
- 每次离线只调 1 次 lite 模型润色整段日志; 失败降级为模板拼接
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..core.behavior import simulate_offline
from ..core.gamedata import MAX_SIMULATE_HOURS, MIN_OFFLINE_MINUTES
from ..llm.gateway import gateway
from ..models import AdventureLog, Pet, User
from .state import add_item, gain_exp

_POLISH_SYSTEM = "你是宠物冒险日志润色助手。把事件列表改写成150字以内、温馨可爱的第一人称小故事(宠物视角, 可带动作表情)。只输出故事正文。"


def _fallback_narrative(pet_name: str, events: list[dict]) -> str:
    """LLM 不可用时的模板叙事(不丢内容)"""
    if not events:
        return f"{pet_name}在家安安静静地待了一阵子。"
    highlights = "；".join(e["text"] for e in events[:3])
    return f"{pet_name}趁你不在进行了一场小小的冒险：{highlights}。一共经历了 {len(events)} 件事, 平平安安地回家了。"


async def _polish_narrative(pet: Pet, events: list[dict]) -> str:
    """lite 模型批量润色; 任何失败都降级为模板"""
    if not events:
        return _fallback_narrative(pet.name, events)
    lines = "\n".join(f"{e['time'][11:16]} {e['text']}" for e in events[:8])
    try:
        result = await gateway.chat(
            [
                {"role": "system", "content": _POLISH_SYSTEM},
                {"role": "user", "content": f"宠物「{pet.name}」的冒险事件:\n{lines}"},
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


def get_my_pet_row(db: Session, user_id: int) -> Pet | None:
    return db.query(Pet).filter(Pet.owner_id == user_id).order_by(Pet.id.desc()).first()


async def check_and_simulate(db: Session, user: User) -> AdventureLog | None:
    """用户回端检测: 离线超阈值则模拟一次冒险并生成日志。

    每次调用都把 last_seen_at 推进到 now, 保证同一离线周期只模拟一次。
    """
    now = datetime.utcnow()
    last_seen = user.last_seen_at
    user.last_seen_at = now

    pet = get_my_pet_row(db, user.id)
    if pet is None or last_seen is None:
        db.commit()
        return None

    minutes = (now - last_seen).total_seconds() / 60
    if minutes < MIN_OFFLINE_MINUTES:
        db.commit()
        return None

    start = last_seen
    end = min(now, last_seen + timedelta(hours=MAX_SIMULATE_HOURS))

    result = simulate_offline(
        personality=pet.personality or {},
        talents=pet.talents or [],
        level=pet.level,
        state=pet.state or {},
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

    # 结算: 状态 / 经验(含升级) / 背包
    pet.state = result.final_state
    pet.state_updated_at = now
    gain_exp(pet, int(result.rewards.get("exp", 0)))
    for item in result.rewards.get("items", []):
        add_item(pet, item)

    db.commit()
    db.refresh(log)
    return log


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
