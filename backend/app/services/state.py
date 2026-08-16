"""经验与道具服务 (原情绪/需求状态机已随简化移除)

- gain_exp: 加经验并处理升级
- add_item: 往背包放道具
"""
from sqlalchemy.orm import Session

from ..core.gamedata import EXP_PER_LEVEL
from ..models import Pet


def gain_exp(pet: Pet, amount: int) -> int:
    """加经验并处理升级, 返回升了几级。调用方负责 commit。"""
    if amount <= 0:
        return 0
    pet.exp += amount
    levels = 0
    while pet.exp >= pet.level * EXP_PER_LEVEL:
        pet.exp -= pet.level * EXP_PER_LEVEL
        pet.level += 1
        levels += 1
    return levels


def add_item(pet: Pet, item_name: str, count: int = 1) -> None:
    """往背包放道具。调用方负责 commit。"""
    inventory = [dict(entry) for entry in (pet.inventory or [])]
    for entry in inventory:
        if entry.get("item") == item_name:
            entry["count"] = int(entry.get("count", 0)) + count
            pet.inventory = inventory
            return
    inventory.append({"item": item_name, "count": count})
    pet.inventory = inventory
