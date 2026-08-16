"""宠物接口: 查看我的宠物"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Pet, User
from ..services import state as state_service
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
        "state": pet.state,
        "level": pet.level,
        "exp": pet.exp,
        "inventory": pet.inventory,
        "sprite_status": pet.sprite_status,
        "sprite_style": pet.sprite_style,
    }


def get_my_pet(db: Session, user: User) -> Pet | None:
    return db.query(Pet).filter(Pet.owner_id == user.id).order_by(Pet.id.desc()).first()


@router.get("/me")
def my_pet(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pet = get_my_pet(db, user)
    if pet is None:
        return None
    state_service.apply_lazy_decay(db, pet)  # T2.2 读取时惰性结算衰减
    db.refresh(pet)
    return pet_to_out(pet)
