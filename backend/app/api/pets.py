"""宠物接口: 查看我的宠物"""
from fastapi import APIRouter, Depends, HTTPException
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
