"""冒险接口: 旅行状态机回端检测 / 手动送出门 / 旅行日志列表"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..services.adventure import check_and_simulate, leave_now, list_logs
from .deps import get_current_user

router = APIRouter(prefix="/api/adventure", tags=["adventure"])


@router.get("/check")
async def check(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """App 打开时调用: 推进旅行状态机。返回 event: returned/left/traveling/null"""
    return await check_and_simulate(db, user)


@router.post("/leave")
def leave(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """手动送宠物出门旅行"""
    from ..services.adventure import get_my_pet_row

    pet = get_my_pet_row(db, user.id)
    if pet is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="还没有宠物")
    return leave_now(db, pet)


@router.get("/logs")
def logs(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {"logs": list_logs(db, user.id, limit)}
