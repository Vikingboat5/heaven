"""性格系统单元测试"""
from backend.app.core.persona import (
    Personality,
    build_system_prompt,
    build_system_prompt_compact,
)


def test_personality_dict_roundtrip():
    p = Personality(extraversion=88, agreeableness=12, tags=["傲娇", "吃货"])
    restored = Personality.from_dict(p.to_dict())
    assert restored == p


def test_personality_from_dict_defaults():
    p = Personality.from_dict({})
    assert p == Personality()


def test_compact_prompt_shorter_and_keeps_tags():
    p = Personality(extraversion=90, agreeableness=20, tags=["傲娇"])
    full = build_system_prompt("团子", "小狐狸", p)
    compact = build_system_prompt_compact("团子", "小狐狸", p)
    assert len(compact) < len(full) * 0.5  # 压缩版显著更短
    assert "傲娇" in compact
    assert "团子" in compact


def test_prompt_contains_personality_descriptions():
    p = Personality(extraversion=90, agreeableness=20, tags=["傲娇"])
    prompt = build_system_prompt("团子", "小狐狸", p)
    assert "活泼外向" in prompt
    assert "嘴上不饶人" in prompt
    assert "傲娇" in prompt
    assert "团子" in prompt


def test_prompt_includes_owner_facts():
    prompt = build_system_prompt("团子", "小狐狸", Personality(), owner_facts=["主人叫小明"])
    assert "主人叫小明" in prompt


def test_prompt_has_safety_rules():
    prompt = build_system_prompt("团子", "小狐狸", Personality())
    assert "绝不承认自己是 AI" in prompt
