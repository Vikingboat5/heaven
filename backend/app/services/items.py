"""物品服务 (v1.2): 目录 join / 首发现回填 / 图鉴输出 / 存量迁移

两层存储 (spec §5.4): ItemDef 静态定义在 content/items.json (core/catalog.py 加载校验);
首发现状态在 DB item_states 表 (启动时幂等播种, 运行时仅回填一次)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..core import catalog
from ..models import ItemState, Pet, User


def seed_item_states(db: Session) -> int:
    """启动时幂等播种 item_states (只补缺, 不回写)。返回新播种数量。"""
    existing = {r.item_id for r in db.query(ItemState).all()}
    added = 0
    for item_id in catalog.ITEMS:
        if item_id not in existing:
            db.add(ItemState(item_id=item_id))
            added += 1
    if added:
        db.commit()
    return added


def migrate_inventory(pet: Pet) -> bool:
    """旧格式背包(名字字符串) → 新格式(item_id 引用)。幂等; 有改动返回 True。"""
    inv = pet.inventory or []
    if not inv:
        return False
    if all("acquired_via" in e for e in inv):
        return False  # 已是新格式
    migrated: list[dict] = []
    for entry in inv:
        if "acquired_via" in entry:
            migrated.append(entry)
            continue
        name = str(entry.get("item", ""))
        item_id = catalog.NAME_TO_ID.get(name, "lost_souvenir")
        count = int(entry.get("count", 1))
        for e in migrated:
            if e["item"] == item_id:
                e["count"] += count
                break
        else:
            migrated.append({"item": item_id, "count": count, "acquired_at": "",
                             "acquired_zone": "", "acquired_via": "forage", "is_new": False})
    pet.inventory = migrated
    return True


def migrate_all_inventories(db: Session) -> int:
    """对存量宠物执行背包迁移。返回迁移的宠物数。"""
    n = 0
    for pet in db.query(Pet).all():
        if migrate_inventory(pet):
            n += 1
    if n:
        db.commit()
    return n


def mark_first_discovery(db: Session, item_id: str, user_id: int) -> bool:
    """获得物品时调用: 若该物品尚无首发现者则回填。返回是否为全球首发现。"""
    state = db.get(ItemState, item_id)
    if state is None:
        state = ItemState(item_id=item_id)
        db.add(state)
        db.flush()
    if state.first_discovered_by is None:
        state.first_discovered_by = user_id
        state.first_discovered_at = datetime.utcnow()
        db.flush()
        return True
    return False


def enrich_entry(entry: dict) -> dict:
    """背包元素 join ItemDef 输出"""
    it = catalog.ITEMS.get(entry.get("item", ""), {})
    return {
        "item_id": entry.get("item", ""),
        "name": it.get("name", entry.get("item", "未知物品")),
        "rarity": it.get("rarity", "common"),
        "attr": it.get("attr", "antique"),
        "image": it.get("image", ""),
        "count": int(entry.get("count", 0)),
        "is_new": bool(entry.get("is_new", False)),
        "acquired_at": entry.get("acquired_at", ""),
        "acquired_zone": entry.get("acquired_zone", ""),
        "acquired_via": entry.get("acquired_via", "forage"),
    }


def reward_items_out(items: list) -> list[dict]:
    """日志 rewards.items (存 [{item, is_new}]) → 富化输出; 同物品合并计数 (信件展示用)"""
    merged: dict[str, dict] = {}
    order: list[str] = []
    for e in items:
        iid = e.get("item") if isinstance(e, dict) else str(e)
        if iid not in merged:
            it = catalog.ITEMS.get(iid, {})
            merged[iid] = {
                "item_id": iid,
                "name": it.get("name", iid),
                "rarity": it.get("rarity", "common"),
                "attr": it.get("attr", "antique"),
                "image": it.get("image", ""),
                "is_new": bool(e.get("is_new")) if isinstance(e, dict) else False,
                "count": 0,
            }
            order.append(iid)
        merged[iid]["count"] += 1
        if isinstance(e, dict) and e.get("is_new"):
            merged[iid]["is_new"] = True
    return [merged[iid] for iid in order]


def catalog_out(db: Session, pet: Pet | None) -> list[dict]:
    """图鉴目录: 全物品 × 图鉴解锁(collection, 曾经获得)/首发现状态
    2026-09-12: obtained 从'当前持有'改为'曾经获得过' —— 消耗/交换不再导致图鉴退回剪影"""
    owned: dict[str, dict] = {}
    for entry in (pet.inventory or []) if pet else []:
        owned[entry.get("item", "")] = entry
    unlocked = set(pet.collection or []) if pet else set()
    states = {s.item_id: s for s in db.query(ItemState).all()}
    users = {u.id: u for u in db.query(User).all()}
    out = []
    for iid, it in catalog.ITEMS.items():
        seed = catalog.SEEDS.get(it.get("source_seed") or "", {})
        state = states.get(iid)
        entry = owned.get(iid)
        first = None
        if state and state.first_discovered_by is not None:
            u = users.get(state.first_discovered_by)
            first = {"by_username": u.username if u else "?",
                     "at": state.first_discovered_at.isoformat(timespec="minutes")
                     if state.first_discovered_at else None}
        out.append({
            "item_id": iid,
            "name": it["name"],
            "desc": it["desc"],
            "rarity": it["rarity"],
            "attr": it["attr"],
            "image": it["image"],
            "pack": seed.get("pack", "misc"),
            "seed_name": seed.get("name", ""),
            "obtained": iid in unlocked,
            "count": int(entry.get("count", 0)) if entry else 0,
            "is_new": bool(entry.get("is_new", False)) if entry else False,
            "first_discovery": first,
        })
    return out


def mark_seen(pet: Pet, item_ids: list[str]) -> int:
    """清 is_new 标记, 返回清除数量"""
    n = 0
    inventory = [dict(e) for e in (pet.inventory or [])]
    for entry in inventory:
        if entry.get("item") in item_ids and entry.get("is_new"):
            entry["is_new"] = False
            n += 1
    if n:
        pet.inventory = inventory
    return n
