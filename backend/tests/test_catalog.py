"""内容目录校验测试 (v1.2): 真实内容通过 / 校验函数硬约束 / 基调权重"""
from backend.app.core import catalog


def test_real_content_loads():
    """import 即校验: 能加载就说明真实内容过了全部校验 (结构/引用/权重和/R3/敏感词)"""
    assert "myth:moon_palace" in catalog.SEEDS
    assert "osmanthus_cake" in catalog.ITEMS
    # 月宫物品归属
    moon = catalog.SEEDS["myth:moon_palace"]
    loot_ids = {e["item"] for e in moon["loot_table"]}
    assert loot_ids <= set(catalog.ITEMS.keys())


def test_flavor_weights_sum_100():
    assert sum(catalog.FLAVOR_WEIGHTS.values()) == 100
    assert set(catalog.FLAVOR_WEIGHTS) == set(catalog.FLAVORS)


def test_no_epic_food_in_content():
    """R3: 传说品级不做口粮"""
    for it in catalog.ITEMS.values():
        if it["attr"] == "food":
            assert it["rarity"] in ("common", "rare"), it["id"]


def test_every_item_image_path():
    for it in catalog.ITEMS.values():
        assert it["image"].startswith("/static/items/"), it["id"]


def test_name_to_id_covers_legacy_names():
    """旧背包迁移映射: 旧事件库出现过的物品名都能映射"""
    for legacy in ("发光蘑菇", "浆果", "橡果", "月光贝", "人鱼的歌谣贝壳"):
        assert legacy in catalog.NAME_TO_ID


def test_draw_loot_min_rarity():
    """寻宝回: min_rarity 限定时只出稀有/传说"""
    import random

    seed = catalog.SEEDS["myth:moon_palace"]
    rng = random.Random("loot-test")
    for _ in range(50):
        iid = catalog.draw_loot(seed, rng, min_rarity="rare")
        assert catalog.rarity_rank(catalog.ITEMS[iid]["rarity"]) >= 1
