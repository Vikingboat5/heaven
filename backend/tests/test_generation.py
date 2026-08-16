"""T1.3 随机生成服务测试: 种子可复现 + 分布符合配置"""
from collections import Counter

from backend.app.core.gamedata import PERSONALITY_TAGS, TALENT_POOL
from backend.app.services.generation import generate_pet

DIMS = ("extraversion", "agreeableness", "conscientiousness", "stability", "openness")
LEGENDARY_TALENT_IDS = {t["id"] for t in TALENT_POOL["legendary"]}
RARE_TALENT_IDS = {t["id"] for t in TALENT_POOL["rare"]}


def test_same_seed_same_pet():
    a = generate_pet(seed="abc123", rarity="normal")
    b = generate_pet(seed="abc123", rarity="normal")
    assert a.to_dict() == b.to_dict()


def test_different_seed_different_pet():
    a = generate_pet(seed="seed-1", rarity="normal")
    b = generate_pet(seed="seed-2", rarity="normal")
    assert a.to_dict() != b.to_dict()


def test_personality_fields_valid():
    for i in range(200):
        pet = generate_pet(seed=f"s{i}", rarity="normal")
        for dim in DIMS:
            assert 0 <= pet.personality[dim] <= 100
        assert 1 <= len(pet.personality["tags"]) <= 2
        assert len(set(pet.personality["tags"])) == len(pet.personality["tags"])  # 标签不重复
        assert all(t in PERSONALITY_TAGS for t in pet.personality["tags"])


def test_legendary_egg_always_two_talents_incl_legendary():
    for i in range(200):
        pet = generate_pet(seed=f"l{i}", rarity="legendary")
        assert len(pet.talents) == 2
        assert any(t["id"] in LEGENDARY_TALENT_IDS for t in pet.talents)


def test_normal_egg_never_legendary_species_or_talent():
    for i in range(500):
        pet = generate_pet(seed=f"n{i}", rarity="normal")
        assert pet.species_id != "dragon"
        assert all(t["id"] not in LEGENDARY_TALENT_IDS for t in pet.talents)


def test_distribution_normal_rare_talent_rate():
    """普通蛋稀有天赋概率配置为 20%, 万次模拟偏差应 < 5%"""
    n = 10_000
    rare_count = sum(
        1
        for i in range(n)
        if any(t["id"] in RARE_TALENT_IDS for t in generate_pet(seed=f"d{i}", rarity="normal").talents)
    )
    rate = rare_count / n
    assert 0.15 < rate < 0.25, f"稀有天赋命中率 {rate:.3f} 超出容差"


def test_distribution_legendary_species():
    """传说蛋小龙(legendary物种层)概率配置 25%, 万次模拟偏差 < 5%"""
    n = 10_000
    dragon = sum(1 for i in range(n) if generate_pet(seed=f"g{i}", rarity="legendary").species_id == "dragon")
    rate = dragon / n
    assert 0.20 < rate < 0.30, f"传说物种命中率 {rate:.3f} 超出容差"


def test_skills_and_name_present():
    pet = generate_pet(seed="hello", rarity="rare")
    assert len(pet.skills) == 1
    assert pet.skills[0]["category"] in ("adventure", "dialogue", "social", "production")
    assert pet.suggested_name
    assert pet.color
