"""W1 种子旅行全链路测试: 结算 / 行囊 / 首发现 / 图鉴 API / 背包迁移 (SQLite 隔离, LLM 置空)"""
from datetime import datetime, timedelta

import pytest

from backend.app import models
from backend.app.core import catalog
from backend.app.services import adventure, items as item_service


@pytest.fixture(autouse=True)
def _noop_polish(monkeypatch):
    """日记润色不触网: 直接降级模板 (LLM 措辞由 prompt 单测另行保证)"""
    async def fallback(pet, seed_def, flavor, events):
        return adventure._fallback_narrative(pet.name, events)

    monkeypatch.setattr(adventure, "_polish_narrative", fallback)


def _make_pet(db, username="traveler", level=3, talents=None, personality=None):
    u = models.User(username=username, password_hash="x")
    db.add(u)
    db.flush()
    pet = models.Pet(
        owner_id=u.id, name="团团", species="小狐狸", color="暖棕",
        personality=personality or {"openness": 80, "extraversion": 90},
        talents=talents or [], skills=[], level=level, exp=0,
        hatch_seed="seed-travel", sprite_status="pending",
    )
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return u, pet


# 固定时间窗: 保证"探测"与"真实结算"的入参逐字节一致 (rng 种子含 start.isoformat)
_FIXED_LEFT = datetime(2026, 8, 17, 8, 0, 0)
_FIXED_BACK = datetime(2026, 8, 17, 11, 0, 0)


def _force_due(pet, seed_id="myth:moon_palace"):
    """直接构造一个已到期的旅行状态 (固定时间窗, 可复现)"""
    pet.travel = {
        "left_at": _FIXED_LEFT.isoformat(),
        "back_at": _FIXED_BACK.isoformat(),
        "dest": catalog.SEEDS[seed_id]["name"],
        "seed": seed_id,
    }


def _hatch_seed_with_items(pet_id: int = 1) -> str:
    """探一个固定能产出物品的 hatch_seed (确定性: 测试内即席探测, 每次跑结果一致)"""
    from backend.app.core.behavior import simulate_trip

    for i in range(30):
        hs = f"probe-seed-{i}"
        r = simulate_trip(
            seed_def=catalog.SEEDS["myth:moon_palace"],
            personality={"openness": 80, "extraversion": 90}, talents=[], level=3,
            start=_FIXED_LEFT, end=_FIXED_BACK,
            seed=f"{hs}:{pet_id}", loadout={},
        )
        if r.rewards["items"]:
            return hs
    raise AssertionError("探测不到有收获的 hatch_seed")


@pytest.mark.asyncio
async def test_settle_trip_full_flow(db):
    """归来结算: 日记+经验+物品入包(is_new)+首发现回填+行囊清空+travel清空"""
    item_service.seed_item_states(db)
    u, pet = _make_pet(db)
    pet.hatch_seed = _hatch_seed_with_items(pet.id)
    pet.loadout = {"food": "berry"}
    from backend.app.services.state import add_item
    add_item(pet, "berry", zone="field:forest")  # 口粮用月宫 loot 外的物品, 保证收获全是 NEW
    _force_due(pet)
    db.commit()

    r = await adventure.check_and_simulate(db, u)
    assert r["event"] == "returned"
    log = r["log"]
    assert log["narrative"]
    assert log["dest"] == "月宫"
    assert log["rewards"]["exp"] > 0
    # 行囊结算: 口粮被消耗(除非留白回), 行囊清空
    db.refresh(pet)
    assert pet.loadout == {}
    assert pet.travel == {}
    # 物品入包带 is_new; 收获物品引用合法; 同物品多次获得时仅首次为 NEW
    assert len(log["rewards"]["items"]) >= 1
    seen: set[str] = set()
    for it in log["rewards"]["items"]:
        assert it["item_id"] in catalog.ITEMS
        assert it["name"] and it["rarity"] in ("common", "rare", "epic")
        assert it["is_new"] is (it["item_id"] not in seen)
        seen.add(it["item_id"])
    # 首发现回填
    for it in log["rewards"]["items"]:
        state = db.get(models.ItemState, it["item_id"])
        assert state is not None and state.first_discovered_by == u.id


def test_first_discovery_not_overwritten(db):
    """首发现只回填一次: 第二个用户发现同物品不覆盖"""
    item_service.seed_item_states(db)
    u1, _ = _make_pet(db, "first")
    u2, _ = _make_pet(db, "second")
    assert item_service.mark_first_discovery(db, "osmanthus_cake", u1.id) is True
    db.commit()
    assert item_service.mark_first_discovery(db, "osmanthus_cake", u2.id) is False
    st = db.get(models.ItemState, "osmanthus_cake")
    assert st.first_discovered_by == u1.id  # 不覆盖
    assert st.first_discovered_at is not None


@pytest.mark.asyncio
async def test_exchange_r2_and_gift_slot(db):
    """行囊伴手礼: 交换不降级(R2) 或原样带回; 带出的礼物从背包扣减或保留"""
    item_service.seed_item_states(db)
    u, pet = _make_pet(db)
    from backend.app.services.state import add_item, count_item
    add_item(pet, "silver_fish_scale", zone="field:valley")
    pet.loadout = {"gift": "silver_fish_scale"}
    _force_due(pet)
    db.commit()

    r = await adventure.check_and_simulate(db, u)
    assert r["event"] == "returned"
    db.refresh(pet)
    ex = r["log"]["rewards"]["exchanged"]
    if ex:  # 换出去了: 不降级(R2) + 旧物扣减 + 新物入包
        gave_rank = catalog.rarity_rank(catalog.ITEMS[ex["gave"]]["rarity"])
        got_rank = catalog.rarity_rank(catalog.ITEMS[ex["got"]]["rarity"])
        assert got_rank >= gave_rank
        assert count_item(pet, ex["gave"]) == 0
        assert count_item(pet, ex["got"]) >= 1
    # 没换出去(留白回/掷骰未过): 礼物还在背包
    else:
        assert count_item(pet, "silver_fish_scale") >= 1


def test_validate_loadout_rules(db):
    """行囊槽位规则: 属性不匹配/未持有/未知槽位都拒绝"""
    u, pet = _make_pet(db)
    from backend.app.services.state import add_item
    add_item(pet, "osmanthus_cake")       # food
    add_item(pet, "silver_fish_scale")    # gift
    # 合法
    assert adventure.validate_loadout(pet, {"food": "osmanthus_cake"}) is None
    # 属性不匹配
    assert adventure.validate_loadout(pet, {"food": "silver_fish_scale"}) is not None
    # 未持有
    assert adventure.validate_loadout(pet, {"charm": "moonstone"}) is not None
    # 未知槽位
    assert adventure.validate_loadout(pet, {"weapon": "osmanthus_cake"}) is not None


def test_inventory_migration_idempotent(db):
    """旧格式背包迁移: 名字→id, 不可映射→失落的纪念品; 幂等"""
    u, pet = _make_pet(db)
    pet.inventory = [
        {"item": "发光蘑菇", "count": 2},
        {"item": "不存在的宝贝", "count": 1},
    ]
    db.commit()
    assert item_service.migrate_inventory(pet) is True
    inv = {e["item"]: e["count"] for e in pet.inventory}
    assert inv["glowing_mushroom"] == 2
    assert inv["lost_souvenir"] == 1
    assert item_service.migrate_inventory(pet) is False  # 幂等


def test_catalog_api_and_mark_seen(api_client, db):
    """图鉴 API: 全目录+持有状态+首发现; mark_seen 清 NEW!"""
    resp = api_client.post("/api/auth/register", json={"username": "collector", "password": "pass123"})
    token = resp.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}

    r = api_client.get("/api/items/catalog", headers=auth)
    assert r.status_code == 200
    items = {i["item_id"]: i for i in r.json()["items"]}
    assert "osmanthus_cake" in items
    assert items["osmanthus_cake"]["obtained"] is False

    # 直接给宠物塞物品 → catalog 显示持有+is_new
    pet = db.query(models.Pet).first()
    if pet is None:
        from backend.app.services.state import add_item
        u = db.query(models.User).first()
        pet = models.Pet(owner_id=u.id, name="团团", species="小狐狸", hatch_seed="s")
        db.add(pet)
        db.commit()
        add_item(pet, "osmanthus_cake", zone="myth:moon_palace")
        db.commit()
    r = api_client.get("/api/items/catalog", headers=auth)
    items = {i["item_id"]: i for i in r.json()["items"]}
    assert items["osmanthus_cake"]["obtained"] is True
    assert items["osmanthus_cake"]["is_new"] is True

    r = api_client.post("/api/items/mark_seen", json={"item_ids": ["osmanthus_cake"]}, headers=auth)
    assert r.json()["cleared"] == 1
    r = api_client.get("/api/items/catalog", headers=auth)
    items = {i["item_id"]: i for i in r.json()["items"]}
    assert items["osmanthus_cake"]["is_new"] is False


def test_leave_with_loadout_api(api_client, db, noop_sprite_task):
    """带行囊出门 API: 槽位校验 + 出门成功; 空手也合法"""
    resp = api_client.post("/api/auth/register", json={"username": "packer", "password": "pass123"})
    token = resp.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    # 没宠物 → 404
    assert api_client.post("/api/adventure/leave", json={}, headers=auth).status_code == 404
    # 造宠物 + 物品
    u = db.query(models.User).filter_by(username="packer").first()
    pet = models.Pet(owner_id=u.id, name="团团", species="小狐狸", hatch_seed="s2", level=3)
    db.add(pet)
    db.commit()
    from backend.app.services.state import add_item
    add_item(pet, "osmanthus_cake")
    add_item(pet, "silver_fish_scale")
    db.commit()

    # 槽位属性不匹配 → 400
    r = api_client.post("/api/adventure/leave", json={"food": "silver_fish_scale"}, headers=auth)
    assert r.status_code == 400
    # 合法行囊 → 出门成功, 行囊锁定
    r = api_client.post("/api/adventure/leave",
                        json={"food": "osmanthus_cake", "gift": "silver_fish_scale"}, headers=auth)
    assert r.status_code == 200 and r.json()["ok"] is True
    db.refresh(pet)
    assert pet.loadout == {"food": "osmanthus_cake", "gift": "silver_fish_scale"}
    assert (pet.travel or {}).get("back_at")
    # 旅行中不能再出门
    r = api_client.post("/api/adventure/leave", json={}, headers=auth)
    assert r.status_code == 400
    # loadout 查询
    r = api_client.get("/api/adventure/loadout", headers=auth)
    assert r.json()["food"] == "osmanthus_cake"
