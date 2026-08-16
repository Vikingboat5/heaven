"""T2.3 事实记忆: 异步从对话抽取关于主人的长期事实 → fact_memories

设计:
- 每积累 EXTRACT_EVERY 条消息触发一次(在对话接口里 fire-and-forget)
- lite tier + 紧凑 prompt(成本与延迟双控), 温度压低保证格式稳定
- 幂等去重(完全相同的文本不重复入库), 单宠物事实上限 30 条(先进先出)
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..llm.gateway import gateway
from ..models import ChatMessage, FactMemory

EXTRACT_EVERY = 4          # 每 4 条消息(约2轮对话)抽取一次
_RECENT_MESSAGES = 10
_MAX_FACTS = 30

_EXTRACT_SYSTEM = "从对话中提取关于主人的长期事实(称呼/喜好/习惯/重要事件)。每行一条简短陈述句, 以\"主人\"开头。没有值得记录的就只输出: 无。不要输出其他内容。"


def _recent_dialogue_text(db: Session, pet_id: int) -> str:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.pet_id == pet_id)
        .order_by(ChatMessage.id.desc())
        .limit(_RECENT_MESSAGES)
        .all()
    )
    rows.reverse()
    return "\n".join(f"{'主人' if r.role == 'user' else '宠物'}: {r.content}" for r in rows)


async def maybe_extract_facts(pet_id: int) -> None:
    """对话接口以 asyncio.create_task 调用; 任何失败静默(记忆是增强, 不是主链路)"""
    db = SessionLocal()
    try:
        count = db.query(func.count(ChatMessage.id)).filter(ChatMessage.pet_id == pet_id).scalar() or 0
        if count == 0 or count % EXTRACT_EVERY != 0:
            return

        dialogue_text = _recent_dialogue_text(db, pet_id)
        if not dialogue_text:
            return

        result = await gateway.chat(
            [
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": dialogue_text},
            ],
            tier="lite",
            pet_id=str(pet_id),
            max_tokens=200,
            temperature=0.2,
        )

        existing = {
            row.fact
            for row in db.query(FactMemory.fact).filter(FactMemory.pet_id == pet_id).all()
        }
        added = False
        for line in result.content.splitlines():
            fact = line.strip().strip("·-•*、。 ")
            if not fact or fact == "无" or len(fact) < 4 or len(fact) > 60:
                continue
            if fact in existing:
                continue
            db.add(FactMemory(pet_id=pet_id, fact=fact))
            existing.add(fact)
            added = True

        if added:
            # 上限控制: 删除最旧的
            ids = [
                row.id
                for row in db.query(FactMemory.id)
                .filter(FactMemory.pet_id == pet_id)
                .order_by(FactMemory.id.desc())
                .all()
            ]
            for old_id in ids[_MAX_FACTS:]:
                db.query(FactMemory).filter(FactMemory.id == old_id).delete()
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
