"""宠物接口: 查看我的宠物 / 喂食 / 休息"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Pet, User
from ..services import state as state_service
from ..services.state import StateError
from ..services.tasks import track_event
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


def _must_have_pet(db: Session, user: User) -> Pet:
    pet = get_my_pet(db, user)
    if pet is None:
        raise HTTPException(status_code=404, detail="你还没有宠物, 先去孵化宠物蛋吧")
    return pet


@router.get("/me")
def my_pet(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pet = get_my_pet(db, user)
    if pet is None:
        return None
    state_service.apply_lazy_decay(db, pet)  # T2.2 读取时惰性结算衰减
    db.refresh(pet)
    return pet_to_out(pet)


@router.post("/feed")
def feed_pet(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pet = _must_have_pet(db, user)
    try:
        pet = state_service.feed(db, pet)
    except StateError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    track_event(db, user.id, "feed")
    db.commit()
    return pet_to_out(pet)


@router.post("/rest")
def rest_pet(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pet = _must_have_pet(db, user)
    try:
        pet = state_service.rest(db, pet)
    except StateError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    return pet_to_out(pet)
