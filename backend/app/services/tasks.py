"""T2.1 任务系统: 播种 / 事件追踪 / 领取奖励

任务配置播种自 gamedata.TASK_CONFIG(幂等), 之后以 DB 为准(可改库配置)。
进度: daily 按 period(日期)重置; achievement 累计。
奖励: hatch_value→当前蛋 / exp→宠物(含升级) / item→宠物背包。
"""
from datetime import date, datetime

from sqlalchemy.orm import Session

from ..core.gamedata import HATCH_VALUE_TARGET, TASK_CONFIG
from ..models import Task, User, UserTaskProgress
from .state import add_item, gain_exp


class TaskError(Exception):
    """业务异常"""


def seed_tasks(db: Session) -> int:
    """启动时播种任务配置, 返回新增数量(已存在的 code 跳过)"""
    existing = {row.code for row in db.query(Task.code).all()}
    created = 0
    for cfg in TASK_CONFIG:
        if cfg["code"] in existing:
            continue
        db.add(Task(
            code=cfg["code"], name=cfg["name"], description=cfg["description"],
            type=cfg["type"], event=cfg["event"], target=cfg["target"], reward=cfg["reward"],
        ))
        created += 1
    db.commit()
    return created


def _get_or_create_progress(db: Session, user_id: int, task: Task) -> UserTaskProgress:
    prog = (
        db.query(UserTaskProgress)
        .filter(UserTaskProgress.user_id == user_id, UserTaskProgress.task_code == task.code)
        .first()
    )
    if prog is None:
        prog = UserTaskProgress(user_id=user_id, task_code=task.code)
        db.add(prog)
        db.flush()
    # 日常任务跨天重置
    today = date.today().isoformat()
    if task.type == "daily" and prog.period != today:
        prog.period = today
        prog.progress = 0
        prog.status = "active"
        prog.claimed_at = None
    return prog


def track_event(db: Session, user_id: int, event: str, amount: int = 1) -> None:
    """业务动作触发任务进度。调用方负责 commit。"""
    tasks = db.query(Task).filter(Task.event == event, Task.is_active.is_(True)).all()
    for task in tasks:
        prog = _get_or_create_progress(db, user_id, task)
        if prog.status != "active":
            continue
        prog.progress = min(task.target, prog.progress + amount)
        if prog.progress >= task.target:
            prog.status = "claimable"
    db.flush()


def list_tasks(db: Session, user_id: int) -> list[dict]:
    """任务列表(含进度); 列出时顺带完成日常重置"""
    tasks = db.query(Task).filter(Task.is_active.is_(True)).order_by(Task.type, Task.id).all()
    result = []
    for task in tasks:
        prog = _get_or_create_progress(db, user_id, task)
        result.append({
            "code": task.code,
            "name": task.name,
            "description": task.description,
            "type": task.type,
            "target": task.target,
            "progress": prog.progress,
            "status": prog.status,
            "reward": task.reward,
        })
    db.commit()
    return result


def claim(db: Session, user: User, code: str) -> dict:
    """领取任务奖励, 返回奖励描述"""
    task = db.query(Task).filter(Task.code == code, Task.is_active.is_(True)).first()
    if task is None:
        raise TaskError("任务不存在")
    prog = _get_or_create_progress(db, user.id, task)
    if prog.status == "claimed":
        raise TaskError("已经领过啦")
    if prog.status != "claimable":
        raise TaskError("任务还没完成, 继续加油")

    reward = task.reward
    rtype, rvalue = reward.get("type"), int(reward.get("value", 0))
    granted: dict = {"type": rtype}

    if rtype == "hatch_value":
        from .egg import get_current_egg

        egg = get_current_egg(db, user.id)
        if egg is None:
            raise TaskError("没有正在孵化的蛋, 奖励暂时无处安放")
        egg.hatch_value = min(HATCH_VALUE_TARGET, egg.hatch_value + rvalue)
        granted.update({"value": rvalue, "text": f"孵化值 +{rvalue}"})
    elif rtype == "exp":
        from ..models import Pet

        pet = db.query(Pet).filter(Pet.owner_id == user.id).order_by(Pet.id.desc()).first()
        if pet is None:
            raise TaskError("还没有宠物, 快去孵化吧")
        levels = gain_exp(pet, rvalue)
        granted.update({"value": rvalue, "text": f"经验 +{rvalue}" + (f", 升了 {levels} 级!" if levels else "")})
    elif rtype == "item":
        from ..models import Pet

        pet = db.query(Pet).filter(Pet.owner_id == user.id).order_by(Pet.id.desc()).first()
        if pet is None:
            raise TaskError("还没有宠物, 快去孵化吧")
        item_name = reward.get("item_name", "神秘道具")
        add_item(pet, item_name, rvalue or 1)
        granted.update({"value": item_name, "text": f"获得道具「{item_name}」"})
    else:
        raise TaskError("未知的奖励类型")

    prog.status = "claimed"
    prog.claimed_at = datetime.utcnow()
    db.commit()
    return granted
