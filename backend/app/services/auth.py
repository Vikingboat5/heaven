"""认证服务: 密码哈希(pbkdf2 标准库) + JWT

从简设计(单人开发): 用户名+密码, 无邮箱验证; token 7 天有效。
"""
import hashlib
import hmac
import secrets
import time

import jwt

from ..config import settings

_ALGORITHM = "HS256"
_TOKEN_TTL_SECONDS = 7 * 24 * 3600
_PBKDF2_ROUNDS = 100_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, hex_digest = stored.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return hmac.compare_digest(digest.hex(), hex_digest)


def create_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": int(time.time()) + _TOKEN_TTL_SECONDS}
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_token(token: str) -> int | None:
    """解析 token 返回 user_id, 无效/过期返回 None"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
