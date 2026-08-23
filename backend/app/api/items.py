"""物品接口: 图鉴目录 / 清除 NEW! 标记"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..services import items as item_service
from .deps import get_current_user
from .pets import get_my_pet

router = APIRouter(prefix="/api/items", tags=["items"])


class MarkSeenIn(BaseModel):
    item_ids: list[str]


@router.get("/catalog")
def catalog(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """图鉴全目录: 物品定义 × 持有状态 × 首发现者"""
    pet = get_my_pet(db, user)
    return {"items": item_service.catalog_out(db, pet)}


@router.post("/mark_seen")
def mark_seen(req: MarkSeenIn, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    """图鉴点开物品后清 NEW! 角标"""
    pet = get_my_pet(db, user)
    if pet is None:
        return {"cleared": 0}
    n = item_service.mark_seen(pet, req.item_ids)
    db.commit()
    return {"cleared": n}
