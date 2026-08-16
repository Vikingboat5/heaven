"""宠物蛋接口: 查看当前蛋 / 照料 / 孵化 / 诞生问答"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.gamedata import HATCH_VALUE_TARGET
from ..database import get_db
from ..models import User
from ..services import egg as egg_service
from ..services import quiz as quiz_service
from ..services.egg import EggError
from ..services.tasks import track_event
from .deps import get_current_user

router = APIRouter(prefix="/api/eggs", tags=["eggs"])


class EggOut(BaseModel):
    id: int
    rarity: str
    hatch_value: int
    hatch_target: int
    care_remaining: int
    quiz_done: bool = False


class HatchIn(BaseModel):
    name: str | None = Field(default=None, max_length=16)


class QuizAnswersIn(BaseModel):
    answers: dict = Field(default_factory=dict)


def _to_out(egg) -> EggOut:
    return EggOut(
        id=egg.id,
        rarity=egg.rarity,
        hatch_value=egg.hatch_value,
        hatch_target=HATCH_VALUE_TARGET,
        care_remaining=egg_service.care_remaining(egg.id),
        quiz_done=bool(egg.quiz_answers),
    )


def _must_have_egg(db: Session, user: User):
    egg = egg_service.get_current_egg(db, user.id)
    if egg is None:
        raise HTTPException(status_code=404, detail="没有正在孵化的蛋")
    return egg


@router.get("/current", response_model=EggOut | None)
def current_egg(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    egg = egg_service.get_current_egg(db, user.id)
    return _to_out(egg) if egg else None


@router.post("/care", response_model=EggOut)
def care(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> EggOut:
    egg = _must_have_egg(db, user)
    try:
        egg = egg_service.care_egg(db, egg)
    except EggError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    track_event(db, user.id, "care")  # T2.1 任务钩子
    db.commit()
    return _to_out(egg)


@router.post("/quiz", response_model=EggOut)
def submit_quiz(req: QuizAnswersIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> EggOut:
    """提交诞生问答: 答案清洗后存到当前蛋上, 孵化时生效"""
    egg = _must_have_egg(db, user)
    egg.quiz_answers = quiz_service.validate_answers(req.answers)
    db.commit()
    db.refresh(egg)
    return _to_out(egg)


@router.post("/hatch")
def hatch(req: HatchIn, background: BackgroundTasks,
          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    egg = _must_have_egg(db, user)
    try:
        pet = egg_service.hatch_egg(db, egg, name=req.name)
    except EggError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    track_event(db, user.id, "hatch")  # T2.1 任务钩子
    # 诞生形象: 后台异步生成(S3.3), 接口立即返回, 前端轮询 sprite_status
    pet.sprite_status = "pending"
    db.commit()
    from ..services.petgen.birth import generate_sprite_task

    background.add_task(generate_sprite_task, pet.id)
    from .pets import pet_to_out

    return pet_to_out(pet)
