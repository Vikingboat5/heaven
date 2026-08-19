"""T2.4 行为引擎测试: 可复现性 / 事件结构 / 收获结算"""
from datetime import datetime, timedelta

from backend.app.core.behavior import simulate_offline

_START = datetime(2026, 7, 20, 10, 0, 0)
_END = _START + timedelta(hours=4)

_KW = dict(
    personality={"openness": 80, "extraversion": 60},
    talents=[],
    level=3,
    start=_START,
    end=_END,
)


def test_same_seed_reproducible():
    """同种子+同输入 → 完全相同的模拟结果"""
    r1 = simulate_offline(**_KW, seed="pet-1")
    r2 = simulate_offline(**_KW, seed="pet-1")
    assert [e["text"] for e in r1.events] == [e["text"] for e in r2.events]
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


def test_rewards_exp_accumulate():
    r = simulate_offline(**_KW, seed="clamp")
    assert r.rewards["exp"] == sum(e["exp"] for e in r.events)


def test_nap_master_rest_exp():
    """打盹高手(v1.1 重定义): 休息事件经验 2→5"""
    found = False
    for i in range(20):
        r = simulate_offline(**{**_KW, "talents": [{"id": "nap_master"}]}, seed=f"nap-{i}")
        for e in r.events:
            if e["type"] == "rest":
                found = True
                assert e["exp"] == 5
    assert found, "20 个种子里应至少出现一次休息事件"


def test_good_appetite_forage_weight():
    """好胃口(v1.1 重定义): 觅食权重提升 → 固定种子集下觅食事件更多"""
    def forage_count(talents):
        return sum(
            1
            for i in range(20)
            for e in simulate_offline(**{**_KW, "talents": talents}, seed=f"app-{i}").events
            if e["type"] == "forage"
        )
    assert forage_count([{"id": "good_appetite"}]) > forage_count([])
