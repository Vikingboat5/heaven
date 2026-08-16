"""任务接口: 列表 / 领取奖励"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..services.tasks import TaskError, claim, list_tasks
from .deps import get_current_user

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
def get_tasks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"tasks": list_tasks(db, user.id)}


@router.post("/{code}/claim")
def claim_task(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        granted = claim(db, user, code)
    except TaskError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "granted": granted}
