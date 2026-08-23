"""行为引擎测试 (v1.2 种子锚定版): 可复现性 / 基调 / 事件结构 / 收获结算 / 天赋"""
from datetime import datetime, timedelta

from backend.app.core import catalog
from backend.app.core.behavior import simulate_trip

_START = datetime(2026, 7, 20, 10, 0, 0)
_END = _START + timedelta(hours=4)
_SEED_DEF = catalog.SEEDS["myth:moon_palace"]

_KW = dict(
    seed_def=_SEED_DEF,
    personality={"openness": 80, "extraversion": 60},
    talents=[],
    level=3,
    start=_START,
    end=_END,
)


def test_same_seed_reproducible():
    """同种子+同输入 → 完全相同的模拟结果"""
    r1 = simulate_trip(**_KW, seed="pet-1")
    r2 = simulate_trip(**_KW, seed="pet-1")
    assert [e["text"] for e in r1.events] == [e["text"] for e in r2.events]
    assert r1.rewards == r2.rewards
    assert r1.flavor == r2.flavor


def test_different_seed_diverges():
    texts = {
        tuple(e["text"] for e in simulate_trip(**_KW, seed=f"pet-{i}").events)
        for i in range(5)
    }
    assert len(texts) > 1


def test_event_structure_and_time_order():
    r = simulate_trip(**_KW, seed="struct")
    assert len(r.events) >= 1
    assert r.flavor in catalog.FLAVORS
    for e in r.events:
        assert e["time"] and e["text"] and e["exp"] >= 0
    times = [e["time"] for e in r.events]
    assert times == sorted(times)


def test_rewards_exp_accumulate():
    r = simulate_trip(**_KW, seed="clamp")
    assert r.rewards["exp"] == sum(e["exp"] for e in r.events)


def test_items_reference_valid_defs():
    """产出的物品必须都有 ItemDef (图鉴可展示)"""
    for i in range(10):
        r = simulate_trip(**_KW, seed=f"items-{i}")
        for item_id in r.rewards["items"]:
            assert item_id in catalog.ITEMS


def test_rest_flavor_fallback_item():
    """留白回: 什么都没干也有保底小物 (Q4)"""
    found = False
    for i in range(200):
        r = simulate_trip(**_KW, seed=f"rest-{i}")
        if r.flavor == "rest":
            found = True
            assert _SEED_DEF["fallback_item"] in r.rewards["items"]
            assert any(e["type"] == "rest_nothing" for e in r.events)
    assert found, "200 个种子里应至少出现一次留白回"


def test_nap_master_rest_exp():
    """打盹高手(v1.1 重定义): 休息事件经验提升至 5"""
    found = False
    for i in range(200):
        r = simulate_trip(**{**_KW, "talents": [{"id": "nap_master"}]}, seed=f"nap-{i}")
        for e in r.events:
            if e["type"] == "rest_nothing":
                found = True
                assert e["exp"] == 5
    assert found, "200 个种子里应至少出现一次休息事件"


def test_good_appetite_food_flavor():
    """好胃口(v1.1 重定义): 美食回权重提升 → 固定种子集下美食回更多"""
    def food_trips(talents):
        return sum(
            1
            for i in range(200)
            if simulate_trip(**{**_KW, "talents": talents}, seed=f"flav-{i}").flavor == "food"
        )
    assert food_trips([{"id": "good_appetite"}]) > food_trips([])


def test_food_loadout_consumed():
    """行囊口粮: 旅途中段被吃掉, 产生 taste 事件且不进收获"""
    for i in range(50):
        r = simulate_trip(**{**_KW, "loadout": {"food": "osmanthus_cake"}}, seed=f"food-{i}")
        if r.flavor == "rest":
            continue  # 留白回不结算行囊
        assert "osmanthus_cake" in r.consumed
        assert "osmanthus_cake" not in r.rewards["items"]
        return
    raise AssertionError("50 个种子里应至少出现一次非留白回")


def test_exchange_never_downgrades():
    """R2 红线: 交换所得品级 >= 带出品级; 无法达成=没换成果断带回"""
    gave = "silver_fish_scale"  # common gift
    gave_rank = catalog.rarity_rank("common")
    for i in range(200):
        r = simulate_trip(**{**_KW, "personality": {"extraversion": 100},
                             "loadout": {"gift": gave}}, seed=f"ex-{i}")
        if r.exchanged:
            got_rank = catalog.rarity_rank(catalog.ITEMS[r.exchanged["got"]]["rarity"])
            assert got_rank >= gave_rank
        else:
            assert r.gift_returned or r.flavor == "rest"  # 没换成必须留痕
    # 直接测 draw 函数: epic 在候选不足时返回 None 而非降级
    import random
    for i in range(30):
        got = catalog.draw_exchange_result(_SEED_DEF, random.Random(f"x-{i}"), "moon_jade")
        assert got is None or catalog.rarity_rank(catalog.ITEMS[got]["rarity"]) >= 2
