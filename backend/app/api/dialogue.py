"""对话接口: SSE 流式输出 (Sprint 2: 内容安全 + 事实记忆 + 状态衰减)

- 输入侧安全: 命中敏感词不调用 LLM(省 token), 性格化兜底话术直接下发
- 输出侧安全: 滚动截留检测(截留窗口 >= 最长敏感词), 命中则整段替换为兜底话术
- 事实记忆: 每次对话后异步抽取(asyncio fire-and-forget, 不阻塞流式)
- 状态: 读取宠物时惰性衰减(T2.2); 对话 +心情
- 验收(开发环境 plan/kimi-k3): 首 token < 15s 且有等待动画; 切豆包后回归 < 2s
"""
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core import safety
from ..core.persona import Personality, PetState, build_system_prompt_compact
from ..database import get_db
from ..llm.gateway import BudgetExceeded, gateway
from ..models import ChatMessage, FactMemory, User
from ..services import memory, state as state_service
from .deps import get_current_user
from .pets import get_my_pet

router = APIRouter(prefix="/api/dialogue", tags=["dialogue"])

_HISTORY_LIMIT = 10      # 短期记忆轮次
_MOOD_PER_CHAT = 2       # 每次对话心情提升
_FACTS_LIMIT = 10
_DISPLAY_LIMIT = 50      # 历史回显条数(前端拉取, 切页不丢)
# 输出侧滚动截留窗口: 必须 >= 最长敏感词, 保证任何敏感词在放行前被完整看到
_HOLD_BACK = max(20, safety.MAX_WORD_LEN + 1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/history")
def history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """对话历史(页面回显): 最近 N 条, 旧→新; assistant 映射为 pet 角色"""
    pet = get_my_pet(db, user)
    if pet is None:
        raise HTTPException(status_code=400, detail="你还没有宠物, 先去孵化宠物蛋吧")
    rows = list(
        reversed(
            db.query(ChatMessage)
            .filter(ChatMessage.pet_id == pet.id)
            .order_by(ChatMessage.id.desc())
            .limit(_DISPLAY_LIMIT)
            .all()
        )
    )
    return {
        "messages": [
            {"role": "pet" if r.role == "assistant" else "user", "content": r.content}
            for r in rows
        ]
    }


@router.post("/chat")
async def chat(req: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pet = get_my_pet(db, user)
    if pet is None:
        raise HTTPException(status_code=400, detail="你还没有宠物, 先去孵化宠物蛋吧")

    state_service.apply_lazy_decay(db, pet)
    db.refresh(pet)
    persona = Personality.from_dict(pet.personality or {})

    # ---- 输入侧安全: 命中则不调用 LLM, 直接下发性格化兜底 ----
    if safety.contains_sensitive(req.message):
        fallback = safety.fallback_for(persona.tags)

        async def refusal_stream():
            db.add(ChatMessage(pet_id=pet.id, role="assistant", content=fallback))
            db.commit()
            yield _sse({"delta": fallback})
            yield "data: [DONE]\n\n"

        return StreamingResponse(refusal_stream(), media_type="text/event-stream")

    state = PetState.from_dict(pet.state or {})
    facts = [
        row.fact
        for row in db.query(FactMemory)
        .filter(FactMemory.pet_id == pet.id)
        .order_by(FactMemory.id.desc())
        .limit(_FACTS_LIMIT)
    ]
    history_rows = list(
        reversed(
            db.query(ChatMessage)
            .filter(ChatMessage.pet_id == pet.id)
            .order_by(ChatMessage.id.desc())
            .limit(_HISTORY_LIMIT)
            .all()
        )
    )

    system_prompt = build_system_prompt_compact(
        name=pet.name,
        species=pet.species,
        personality=persona,
        state=state,
        owner_facts=facts or None,
    )
    messages = [{"role": "system", "content": system_prompt}]
    messages += [{"role": r.role, "content": r.content} for r in history_rows]
    messages.append({"role": "user", "content": req.message})

    # 持久化用户消息 + 互动提升心情
    db.add(ChatMessage(pet_id=pet.id, role="user", content=req.message))
    new_state = dict(pet.state or {})
    new_state["mood"] = min(100, int(new_state.get("mood", 70)) + _MOOD_PER_CHAT)
    pet.state = new_state
    db.commit()

    fallback = safety.fallback_for(persona.tags)

    async def event_stream():
        full: list[str] = []
        held = ""          # 滚动截留: 未通过安全检查的尾部
        blocked = False
        try:
            async for delta in gateway.chat_stream(messages, tier="standard", pet_id=str(pet.id)):
                held += delta
                if safety.contains_sensitive(held):
                    blocked = True
                    yield _sse({"replace": fallback})  # 前端整段替换
                    break
                if len(held) > _HOLD_BACK:
                    release, held = held[:-_HOLD_BACK], held[-_HOLD_BACK:]
                    full.append(release)
                    yield _sse({"delta": release})
            else:
                # 正常结束: 放行截留尾部(放行前做最终检查)
                if held:
                    if safety.contains_sensitive(held):
                        blocked = True
                        yield _sse({"replace": fallback})
                    else:
                        full.append(held)
                        yield _sse({"delta": held})

            reply = fallback if blocked else "".join(full).strip()
            if reply:  # 持久化宠物回复(短期记忆); 被拦截的存兜底话术
                db.add(ChatMessage(pet_id=pet.id, role="assistant", content=reply))
                db.commit()
            # T2.3 异步事实抽取(不阻塞流式)
            asyncio.get_running_loop().create_task(memory.maybe_extract_facts(pet.id))
        except BudgetExceeded as e:
            yield _sse({"error": "budget_exceeded", "detail": str(e)})
        except Exception as e:  # noqa: BLE001 - 流式接口兜底, 错误也要以 SSE 形式下发
            yield _sse({"error": "llm_error", "detail": str(e)})
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
