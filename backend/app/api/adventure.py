"""冒险接口: 旅行状态机回端检测 / 行囊 / 手动送出门 / 旅行日记列表"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..services.adventure import check_and_simulate, leave_now, list_logs
from .deps import get_current_user

router = APIRouter(prefix="/api/adventure", tags=["adventure"])


class LeaveIn(BaseModel):
    """行囊 (均可空, 空手出门合法): food=口粮 / gift=伴手礼 / charm=护身符, 值为 item_id"""
    food: str | None = None
    gift: str | None = None
    charm: str | None = None


@router.get("/check")
async def check(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """App 打开时调用: 推进旅行状态机。返回 event: returned/left/traveling/null"""
    return await check_and_simulate(db, user)


@router.get("/loadout")
def loadout(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """当前行囊 (旅行中只读展示用)"""
    pet = _must_pet(db, user)
    lo = pet.loadout or {}
    return {"food": lo.get("food"), "gift": lo.get("gift"), "charm": lo.get("charm")}


@router.post("/leave")
def leave(req: LeaveIn | None = None, db: Session = Depends(get_db),
          user: User = Depends(get_current_user)):
    """手动送宠物出门旅行 (可带行囊)"""
    pet = _must_pet(db, user)
    result = leave_now(db, pet, loadout=req.model_dump() if req else None)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("detail", "现在不能出门"))
    return result


@router.get("/logs")
def logs(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {"logs": list_logs(db, user.id, limit)}


def _must_pet(db: Session, user: User):
    from ..services.adventure import get_my_pet_row

    pet = get_my_pet_row(db, user.id)
    if pet is None:
        raise HTTPException(status_code=404, detail="还没有宠物")
    return pet
