"""T2.4 行为引擎测试: 可复现性 / 事件结构 / 状态边界 / 强制休息"""
from datetime import datetime, timedelta

from backend.app.core.behavior import simulate_offline

_START = datetime(2026, 7, 20, 10, 0, 0)
_END = _START + timedelta(hours=4)

_KW = dict(
    personality={"openness": 80, "extraversion": 60},
    talents=[],
    level=3,
    state={"mood": 70, "satiety": 80, "energy": 90},
    start=_START,
    end=_END,
)


def test_same_seed_reproducible():
    """同种子+同输入 → 完全相同的模拟结果"""
    r1 = simulate_offline(**_KW, seed="pet-1")
    r2 = simulate_offline(**_KW, seed="pet-1")
    assert [e["text"] for e in r1.events] == [e["text"] for e in r2.events]
    assert r1.final_state == r2.final_state
    assert r1.rewards == r2.rewards


def test_different_seed_diverges():
    texts = {
        tuple(e["text"] for e in simulate_offline(**_KW, seed=f"pet-{i}").events)
        for i in range(5)
    }
    assert len(texts) > 1


def test_event_structure_and_time_order():
    r = simulate_offline(**_KW, seed="struct")
    assert len(r.events) >= 1
    for e in r.events:
        assert e["time"] and e["text"] and e["exp"] >= 0
    times = [e["time"] for e in r.events]
    assert times == sorted(times)


def test_state_clamped_and_rewards_accumulate():
    r = simulate_offline(**_KW, seed="clamp")
    for v in r.final_state.values():
        assert 0 <= v <= 100
    assert r.rewards["exp"] == sum(e["exp"] for e in r.events)


def test_low_energy_forces_rest():
    kw = dict(_KW, state={"mood": 70, "satiety": 80, "energy": 10})
    r = simulate_offline(**kw, seed="tired")
    assert r.events[0]["type"] == "rest"
    assert r.final_state["energy"] > 10  # 休息后精力回升
