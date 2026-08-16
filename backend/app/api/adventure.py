"""冒险接口: 回端检测(触发离线模拟) / 日志列表"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..services.adventure import check_and_simulate, list_logs, log_to_out
from .deps import get_current_user

router = APIRouter(prefix="/api/adventure", tags=["adventure"])


@router.get("/check")
async def check(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """App 打开时调用: 离线超阈值则模拟冒险, 返回新日志(无则 null)"""
    log = await check_and_simulate(db, user)
    return {"new_log": log_to_out(log) if log else None}


@router.get("/logs")
def logs(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {"logs": list_logs(db, user.id, limit)}
