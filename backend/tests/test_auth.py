"""T1.1 认证服务测试"""
from backend.app.services.auth import (
    create_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    stored = hash_password("secret123")
    assert verify_password("secret123", stored)
    assert not verify_password("wrong", stored)


def test_hash_password_salted():
    assert hash_password("same") != hash_password("same")  # 盐不同, 哈希不同


def test_verify_password_malformed():
    assert not verify_password("x", "not-a-valid-hash")


def test_token_roundtrip():
    token = create_token(42)
    assert decode_token(token) == 42


def test_token_tampered():
    token = create_token(42)
    assert decode_token(token[:-2] + "xx") is None
    assert decode_token("garbage") is None
