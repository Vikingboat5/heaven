"""T2.1 任务系统测试: 播种 / 进度追踪 / 领取 / 防重复"""
import pytest
from backend.app import models
from backend.app.services.tasks import TaskError, claim, list_tasks, seed_tasks, track_event


def _user(db, name="tasker") -> models.User:
    u = models.User(username=name, password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _pet(db, user) -> models.Pet:
    p = models.Pet(
        owner_id=user.id, name="测试兽", species="柴犬", color="暖棕",
        personality={}, talents=[], skills=[],
        state={"mood": 70, "satiety": 80, "energy": 90}, level=1, exp=0,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_seed_tasks_idempotent(db):
    n1 = seed_tasks(db)
    n2 = seed_tasks(db)
    assert n1 > 0 and n2 == 0  # 幂等


def test_track_event_progress_and_claimable(db):
    seed_tasks(db)
    u = _user(db)
    daily_chat = db.query(models.Task).filter_by(code="daily_chat").one()

    for _ in range(daily_chat.target):
        track_event(db, u.id, daily_chat.event)
    db.commit()

    tasks = {t["code"]: t for t in list_tasks(db, u.id)}
    assert tasks["daily_chat"]["progress"] == daily_chat.target
    assert tasks["daily_chat"]["status"] == "claimable"


def test_claim_exp_reward_and_no_double_claim(db):
    seed_tasks(db)
    u = _user(db)
    pet = _pet(db, u)
    task = db.query(models.Task).filter_by(code="daily_chat").one()

    for _ in range(task.target):
        track_event(db, u.id, task.event)
    db.commit()

    granted = claim(db, u, "daily_chat")
    assert granted["type"] == "exp"
    db.refresh(pet)
    assert pet.exp > 0

    with pytest.raises(TaskError, match="领过"):
        claim(db, u, "daily_chat")


def test_claim_before_complete_rejected(db):
    seed_tasks(db)
    u = _user(db)
    _pet(db, u)
    with pytest.raises(TaskError, match="还没完成"):
        claim(db, u, "daily_chat")
