"""认证接口: 注册(赠送宠物蛋) / 登录 / 当前用户"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..services.auth import create_token, hash_password, verify_password
from ..services.egg import create_egg
from .deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class CredentialsIn(BaseModel):
    username: str = Field(min_length=2, max_length=16)
    password: str = Field(min_length=6, max_length=64)


class UserOut(BaseModel):
    id: int
    username: str


class TokenOut(BaseModel):
    token: str
    user: UserOut


@router.post("/register", response_model=TokenOut)
def register(req: CredentialsIn, db: Session = Depends(get_db)) -> TokenOut:
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已被使用")
    user = User(username=req.username, password_hash=hash_password(req.password))
    db.add(user)
    db.flush()
    create_egg(db, user.id)  # 注册赠送第一枚宠物蛋
    db.commit()
    return TokenOut(token=create_token(user.id), user=UserOut(id=user.id, username=user.username))


@router.post("/login", response_model=TokenOut)
def login(req: CredentialsIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.query(User).filter(User.username == req.username).first()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    return TokenOut(token=create_token(user.id), user=UserOut(id=user.id, username=user.username))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user.id, username=user.username)
