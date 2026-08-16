"""宠物随机生成服务: 种子化随机, 同种子结果完全一致(可复现/可审计/防刷)

生成内容: 物种+配色 / 性格(大五+标签) / 天赋(按稀有度) / 初始技能 / 推荐名字
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass

from ..core.gamedata import (
    COLORS,
    NAME_POOL,
    PERSONALITY_TAGS,
    RARITY_SPECIES_TABLE,
    SKILL_POOL,
    SPECIES_POOL,
    TALENT_POOL,
)

_DIMS = ("extraversion", "agreeableness", "conscientiousness", "stability", "openness")


@dataclass
class QuizBias:
    """诞生问答倾向 (spec 4.0): 问答定基调, 种子随机保留惊喜与不可刷"""
    personality: dict | None = None    # {维度: 增量}, 与种子随机结果叠加后 clip
    tag: str | None = None             # 性格标签倾向(置于 tags 首位)
    species_id: str | None = None      # 物种倾向(仅 common 池内生效)


@dataclass
class GeneratedPet:
    species_id: str
    species_name: str
    color: str
    personality: dict      # 与 core.persona.Personality.from_dict 兼容
    talents: list[dict]
    skills: list[dict]
    suggested_name: str

    def to_dict(self) -> dict:
        return asdict(self)


def _clip(value: float) -> int:
    return int(min(100, max(0, round(value))))


def _roll_species(rng: random.Random, rarity: str,
                  bias: QuizBias | None = None) -> tuple[dict, str]:
    table = RARITY_SPECIES_TABLE.get(rarity, RARITY_SPECIES_TABLE["normal"])
    tier = rng.choices(list(table.keys()), weights=list(table.values()))[0]
    pool = SPECIES_POOL[tier]
    # 物种倾向: 问答指定的物种在该稀有度层池内时优先采用
    if bias and bias.species_id:
        preferred = [s for s in pool if s["id"] == bias.species_id]
        if preferred:
            return preferred[0], rng.choice(COLORS)
    return rng.choice(pool), rng.choice(COLORS)


def _roll_personality(rng: random.Random, rarity: str,
                      bias: QuizBias | None = None) -> dict:
    dims = {k: _clip(rng.gauss(50, 26)) for k in _DIMS}
    # 防止"全是中庸"导致性格没有辨识度: 随机强化一个维度到极端区间
    if all(35 <= v <= 65 for v in dims.values()):
        key = rng.choice(list(_DIMS))
        dims[key] = rng.choice([rng.randint(5, 30), rng.randint(70, 95)])
    # 问答性格倾向: 叠加增量(±15) 后 clip
    if bias and bias.personality:
        for k, delta in bias.personality.items():
            if k in dims:
                dims[k] = _clip(dims[k] + delta)
    if rarity == "legendary":
        tag_count = 2
    elif rarity == "rare":
        tag_count = 2 if rng.random() < 0.5 else 1
    else:
        tag_count = 2 if rng.random() < 0.25 else 1
    tags = rng.sample(PERSONALITY_TAGS, tag_count)
    # 问答标签倾向: 置于首位(不在池内则忽略)
    if bias and bias.tag and bias.tag in PERSONALITY_TAGS:
        tags = [t for t in tags if t != bias.tag]
        tags.insert(0, bias.tag)
    dims["tags"] = tags
    return dims


def _roll_talents(rng: random.Random, rarity: str) -> list[dict]:
    if rarity == "legendary":
        picks = [rng.choice(TALENT_POOL["legendary"]), rng.choice(TALENT_POOL["rare"])]
    elif rarity == "rare":
        picks = [rng.choice(TALENT_POOL["rare"])]
        if rng.random() < 0.5:
            picks.append(rng.choice(TALENT_POOL["common"]))
    else:
        pool = TALENT_POOL["common"] if rng.random() < 0.8 else TALENT_POOL["rare"]
        picks = [rng.choice(pool)]
    # 按 id 去重
    seen: set[str] = set()
    result: list[dict] = []
    for t in picks:
        if t["id"] not in seen:
            seen.add(t["id"])
            result.append(dict(t))
    return result


def generate_pet(seed: str, rarity: str = "normal",
                 bias: QuizBias | None = None) -> GeneratedPet:
    """由种子生成宠物。同一种子+稀有度+倾向 → 完全相同的宠物。"""
    rng = random.Random(f"petgen:{seed}:{rarity}")
    species, color = _roll_species(rng, rarity, bias)
    personality = _roll_personality(rng, rarity, bias)
    talents = _roll_talents(rng, rarity)
    skills = [dict(rng.choice(SKILL_POOL))]
    suggested_name = rng.choice(NAME_POOL)
    return GeneratedPet(
        species_id=species["id"],
        species_name=species["name"],
        color=color,
        personality=personality,
        talents=talents,
        skills=skills,
        suggested_name=suggested_name,
    )
