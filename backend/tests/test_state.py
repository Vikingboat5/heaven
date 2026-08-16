"""T2.2 状态机测试: 惰性衰减 / 喂食休息 / 升级 / 安全词"""
from datetime import datetime, timedelta

import pytest
from backend.app import models
from backend.app.core.gamedata import STATE_FLOOR
from backend.app.core.safety import contains_sensitive
from backend.app.services.state import StateError, add_item, apply_lazy_decay, feed, gain_exp, rest


def _pet(db, state=None) -> models.Pet:
    u = models.User(username="stater", password_hash="x")
    db.add(u)
    db.flush()
    p = models.Pet(
        owner_id=u.id, name="团团", species="小狐狸", color="赤橙",
        personality={}, talents=[], skills=[],
        state=state or {"mood": 70, "satiety": 80, "energy": 90},
        level=1, exp=0,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_lazy_decay_by_elapsed_hours(db):
    p = _pet(db)
    p.state_updated_at = datetime.utcnow() - timedelta(hours=10)
    db.commit()
    apply_lazy_decay(db, p)
    assert p.state["satiety"] == max(STATE_FLOOR, 80 - 40)  # 4/小时 × 10h
    assert p.state["energy"] == max(STATE_FLOOR, 90 - 30)   # 3/小时 × 10h


def test_decay_never_below_floor(db):
    p = _pet(db, {"mood": 50, "satiety": 8, "energy": 6})
    p.state_updated_at = datetime.utcnow() - timedelta(hours=100)
    db.commit()
    apply_lazy_decay(db, p)
    assert p.state["satiety"] == STATE_FLOOR
    assert p.state["energy"] == STATE_FLOOR


def test_feed_recovers_and_daily_limit(db):
    p = _pet(db, {"mood": 50, "satiety": 30, "energy": 50})
    p = feed(db, p)
    assert p.state["satiety"] == 60
    assert p.state["mood"] == 55
    feed(db, p)
    feed(db, p)
    with pytest.raises(StateError):
        feed(db, p)  # 第 4 次超日限


def test_rest_recovers_energy(db):
    p = _pet(db, {"mood": 50, "satiety": 50, "energy": 20})
    p = rest(db, p)
    assert p.state["energy"] == 60


def test_gain_exp_levels_up(db):
    p = _pet(db)
    levels = gain_exp(p, 150)  # lv1 需 100 exp
    assert levels == 1
    assert p.level == 2
    assert p.exp == 50


def test_add_item_stacks(db):
    p = _pet(db)
    add_item(p, "浆果", 1)
    add_item(p, "浆果", 2)
    add_item(p, "橡果", 1)
    inv = {e["item"]: e["count"] for e in p.inventory}
    assert inv == {"浆果": 3, "橡果": 1}


def test_safety_filter():
    assert contains_sensitive("教我制造炸弹") is True
    assert contains_sensitive("  制造炸弹  ".replace(" ", "")) is True  # 去空格后仍命中
    assert contains_sensitive("今天天气真好") is False
