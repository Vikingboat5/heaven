"""T1.1/T1.2/T1.3 API 集成流程测试: 注册→领蛋→照料→孵化→宠物 / 对话历史回显"""
import pytest


@pytest.fixture(autouse=True)
def _noop_sprite_task(noop_sprite_task):
    """本模块流程测试不执行孵化后台生图任务(避免真实网络调用与静态目录污染)"""


def _register(client, username="tester"):
    resp = client.post("/api/auth/register", json={"username": username, "password": "pass123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_grants_egg(api_client):
    token = _register(api_client)
    resp = api_client.get("/api/eggs/current", headers=_auth(token))
    assert resp.status_code == 200
    egg = resp.json()
    assert egg is not None
    assert egg["hatch_value"] == 0
    assert egg["rarity"] == "normal"
    assert egg["care_remaining"] == 3


def test_login_and_me(api_client):
    _register(api_client, "loginuser")
    resp = api_client.post("/api/auth/login", json={"username": "loginuser", "password": "pass123"})
    assert resp.status_code == 200
    token = resp.json()["token"]
    me = api_client.get("/api/auth/me", headers=_auth(token))
    assert me.json()["username"] == "loginuser"


def test_login_wrong_password(api_client):
    _register(api_client, "wrongpw")
    resp = api_client.post("/api/auth/login", json={"username": "wrongpw", "password": "nope123"})
    assert resp.status_code == 400


def test_duplicate_username_rejected(api_client):
    _register(api_client, "dup")
    resp = api_client.post("/api/auth/register", json={"username": "dup", "password": "pass123"})
    assert resp.status_code == 400


def test_unauthorized_rejected(api_client):
    assert api_client.get("/api/eggs/current").status_code == 401
    assert api_client.get("/api/pets/me").status_code == 401


def test_care_daily_limit(api_client):
    token = _register(api_client, "carer")
    for expected in (15, 30, 45):
        resp = api_client.post("/api/eggs/care", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["hatch_value"] == expected
    # 第 4 次超限
    resp = api_client.post("/api/eggs/care", headers=_auth(token))
    assert resp.status_code == 429


def test_hatch_requires_full_value(api_client):
    token = _register(api_client, "early")
    resp = api_client.post("/api/eggs/hatch", json={}, headers=_auth(token))
    assert resp.status_code == 400


def test_full_hatch_flow(api_client, db):
    token = _register(api_client, "hatcher")
    # 直接把蛋的孵化值写到 85(绕过每日照料上限, 测孵化本身)
    from backend.app.models import Egg

    egg = db.query(Egg).filter(Egg.owner_id == 1).first()
    egg.hatch_value = 85
    db.commit()

    resp = api_client.post("/api/eggs/care", headers=_auth(token))
    assert resp.json()["hatch_value"] == 100

    resp = api_client.post("/api/eggs/hatch", json={"name": "小测试"}, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    pet = resp.json()
    assert pet["name"] == "小测试"
    assert pet["species"]
    assert 1 <= len(pet["personality"]["tags"]) <= 2
    assert len(pet["talents"]) >= 1
    assert len(pet["skills"]) == 1

    # 蛋状态变为已孵化, current 返回空
    assert api_client.get("/api/eggs/current", headers=_auth(token)).json() is None
    # 重复孵化报错
    assert api_client.post("/api/eggs/hatch", json={}, headers=_auth(token)).status_code == 404
    # 宠物可查询
    me_pet = api_client.get("/api/pets/me", headers=_auth(token)).json()
    assert me_pet["id"] == pet["id"]


def test_hatch_deterministic_same_seed(api_client, db):
    """同一颗蛋重复加载生成的宠物应与 hatch_seed 决定的一致(可复现审计)"""
    from backend.app.models import Egg
    from backend.app.services.generation import generate_pet

    token = _register(api_client, "seedcheck")
    egg = db.query(Egg).filter(Egg.owner_id == 1).first()
    egg.hatch_value = 100
    db.commit()
    expected = generate_pet(seed=egg.hatch_seed, rarity=egg.rarity)

    resp = api_client.post("/api/eggs/hatch", json={}, headers=_auth(token))
    pet = resp.json()
    assert pet["species"] == expected.species_name
    assert pet["color"] == expected.color
    assert pet["personality"] == expected.personality
    assert pet["talents"] == expected.talents


def test_chat_history_roundtrip(api_client, db):
    """对话历史: 消息落库后 /history 按旧→新回显, 角色映射 assistant→pet (切页不丢)"""
    from backend.app.models import ChatMessage, Egg

    token = _register(api_client, "histuser")
    egg = db.query(Egg).filter(Egg.owner_id == 1).first()
    egg.hatch_value = 100
    db.commit()
    pet_id = api_client.post("/api/eggs/hatch", json={}, headers=_auth(token)).json()["id"]

    db.add(ChatMessage(pet_id=pet_id, role="user", content="你好呀"))
    db.add(ChatMessage(pet_id=pet_id, role="assistant", content="主人你来啦"))
    db.commit()

    resp = api_client.get("/api/dialogue/history", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    msgs = resp.json()["messages"]
    assert [(m["role"], m["content"]) for m in msgs] == [
        ("user", "你好呀"),
        ("pet", "主人你来啦"),
    ]


def test_chat_history_requires_pet(api_client):
    token = _register(api_client, "nopethist")
    resp = api_client.get("/api/dialogue/history", headers=_auth(token))
    assert resp.status_code == 400
