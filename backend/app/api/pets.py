"""宠物接口: 查看/改名/重生成形象"""
import threading

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Pet, User
from ..services import items as item_service
from ..services.adventure import is_away
from .deps import get_current_user

router = APIRouter(prefix="/api/pets", tags=["pets"])


def pet_to_out(pet: Pet) -> dict:
    return {
        "id": pet.id,
        "name": pet.name,
        "species": pet.species,
        "color": pet.color,
        "rarity": pet.rarity,
        "personality": pet.personality,
        "talents": pet.talents,
        "skills": pet.skills,
        "level": pet.level,
        "exp": pet.exp,
        "inventory": [item_service.enrich_entry(e) for e in (pet.inventory or [])],
        "loadout": pet.loadout or {},
        "sprite_status": pet.sprite_status,
        "sprite_style": pet.sprite_style,
        "away": is_away(pet),
        "travel": pet.travel or {},
    }


def get_my_pet(db: Session, user: User) -> Pet | None:
    return db.query(Pet).filter(Pet.owner_id == user.id).order_by(Pet.id.desc()).first()


@router.get("/me")
def my_pet(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pet = get_my_pet(db, user)
    if pet is None:
        return None
    return pet_to_out(pet)


class RenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=16)


@router.post("/rename")
def rename_pet(body: RenameIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """改名 (宠物详情页 H7)"""
    pet = get_my_pet(db, user)
    if pet is None:
        raise HTTPException(status_code=404, detail="还没有宠物")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="名字不能为空")
    pet.name = name
    db.commit()
    return {"ok": True, "name": pet.name}


@router.post("/regen_sprite")
def regen_sprite(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """重新生成形象 (H7): 异步后台任务, 期间旧形象继续用; 完成后前端轮询 sprite_status 自然刷新"""
    pet = get_my_pet(db, user)
    if pet is None:
        raise HTTPException(status_code=404, detail="还没有宠物")
    if pet.sprite_status == "pending":
        return {"ok": False, "detail": "正在生成中，稍等一下"}
    from ..services.petgen.birth import generate_sprite_task
    pet.sprite_status = "pending"
    db.commit()
    threading.Thread(target=generate_sprite_task, args=(pet.id,), daemon=True).start()
    return {"ok": True}
