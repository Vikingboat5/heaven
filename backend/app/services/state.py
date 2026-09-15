"""经验与背包服务

- gain_exp: 加经验并处理升级
- add_item: 往背包放物品 (v1.2: item_id 引用 + 溯源 + is_new)
- remove_item: 消耗/交换扣减
"""
from datetime import datetime

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


def add_item(pet: Pet, item_id: str, count: int = 1, *,
             zone: str = "", via: str = "forage", is_new: bool = True) -> None:
    """往背包放物品。调用方负责 commit。via: forage(拾获)/exchange(交换)/gift(获赠)
    获得即记入图鉴解锁 (collection, 消耗不影响)"""
    coll = list(pet.collection or [])
    if item_id not in coll:
        coll.append(item_id)
        pet.collection = coll
    inventory = [dict(entry) for entry in (pet.inventory or [])]
    for entry in inventory:
        if entry.get("item") == item_id:
            entry["count"] = int(entry.get("count", 0)) + count
            if is_new:
                entry["is_new"] = True
            pet.inventory = inventory
            return
    inventory.append({"item": item_id, "count": count,
                      "acquired_at": datetime.utcnow().isoformat(timespec="minutes"),
                      "acquired_zone": zone, "acquired_via": via, "is_new": is_new})
    pet.inventory = inventory


def remove_item(pet: Pet, item_id: str, count: int = 1) -> bool:
    """从背包扣减物品 (口粮消耗/交换付出)。数量不足返回 False。"""
    inventory = [dict(entry) for entry in (pet.inventory or [])]
    for entry in inventory:
        if entry.get("item") == item_id:
            if int(entry.get("count", 0)) < count:
                return False
            entry["count"] = int(entry["count"]) - count
            pet.inventory = [e for e in inventory if int(e.get("count", 0)) > 0]
            return True
    return False


def count_item(pet: Pet, item_id: str) -> int:
    for entry in (pet.inventory or []):
        if entry.get("item") == item_id:
            return int(entry.get("count", 0))
    return 0
