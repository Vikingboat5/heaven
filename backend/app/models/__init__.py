"""数据模型

- User.last_seen_at: 最近活跃(旅行状态机锚点, 离线超阈值自动出门)
- Pet.exp / inventory(背包/纪念品收藏) / travel(旅行状态)
- v1.1 简化: 移除 Pet.state(心情/饱食/精力)与 state_updated_at; 移除 Task/UserTaskProgress
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(nullable=True)  # 最近活跃(冒险模拟锚点)

    pets: Mapped[list["Pet"]] = relationship(back_populates="owner")
    eggs: Mapped[list["Egg"]] = relationship(back_populates="owner")


class Egg(Base):
    """宠物蛋: 孵化值满 100 后可孵化"""
    __tablename__ = "eggs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rarity: Mapped[str] = mapped_column(String(16), default="normal")  # normal/rare/legendary
    hatch_value: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(16), default="incubating")  # incubating/hatched
    hatch_seed: Mapped[str] = mapped_column(String(64), default="")
    # 诞生问答答案(Sprint 3): {"weekend":"social","color":"薄荷绿","ip":"皮卡丘",...}
    quiz_answers: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    hatched_at: Mapped[datetime | None] = mapped_column(nullable=True)

    owner: Mapped[User] = relationship(back_populates="eggs")


class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(32))
    species: Mapped[str] = mapped_column(String(32))
    color: Mapped[str] = mapped_column(String(16), default="")
    rarity: Mapped[str] = mapped_column(String(16), default="normal")
    # 性格: {"extraversion":45,...,"tags":["傲娇"]}
    personality: Mapped[dict] = mapped_column(JSON, default=dict)
    talents: Mapped[list] = mapped_column(JSON, default=list)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    level: Mapped[int] = mapped_column(default=1)
    exp: Mapped[int] = mapped_column(default=0)
    # 背包 (v1.2): [{"item": item_id, "count": n, "acquired_at": iso, "acquired_zone": seed_id,
    #               "acquired_via": "forage|exchange|gift", "is_new": bool}]
    inventory: Mapped[list] = mapped_column(JSON, default=list)
    # 行囊 (v1.2): {"food": item_id|null, "gift": ..., "charm": ...} 出门时锁定, 归来结算后清空
    loadout: Mapped[dict] = mapped_column(JSON, default=dict)
    # 图鉴解锁记录 (2026-09-12): 曾经获得过的 item_id 列表, 消耗/交换不影响 (obtained=曾经拥有, 非当前持有)
    collection: Mapped[list] = mapped_column(JSON, default=list)
    # 旅行状态: {} 在家; {"left_at":iso,"back_at":iso,"dest":名,"seed":seed_id,"flavor":基调} 旅行中
    travel: Mapped[dict] = mapped_column(JSON, default=dict)
    hatch_seed: Mapped[str] = mapped_column(String(64), default="")
    # 生成形象 (Sprint 3): pending/ready/failed; style 为画风路由键; appearance 为外观描述词
    sprite_status: Mapped[str] = mapped_column(String(16), default="")
    sprite_style: Mapped[str] = mapped_column(String(16), default="")
    appearance: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    owner: Mapped[User] = relationship(back_populates="pets")


class ChatMessage(Base):
    """对话消息: 短期记忆来源, 也是事实抽取的原始素材"""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user / assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class FactMemory(Base):
    """结构化事实记忆: 从对话中抽取的关于主人的事实"""
    __tablename__ = "fact_memories"

    id: Mapped[int] = mapped_column(primary_key=True)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), index=True)
    fact: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), default="general")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class PetSeedMemory(Base):
    """H10 地点记忆卡 (2026-09-19): 宠物×地点的滚动记忆, 重访时进润色 prompt (token O(1))"""
    __tablename__ = "pet_seed_memories"

    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), primary_key=True)
    seed_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    memory: Mapped[str] = mapped_column(Text, default="")
    visit_count: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ItemState(Base):
    """物品发现状态 (v1.2): 静态定义在 content/items.json, 本表只存运行时回填的首发现状态"""
    __tablename__ = "item_states"

    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_discovered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    first_discovered_at: Mapped[datetime | None] = mapped_column(nullable=True)


class AdventureLog(Base):
    """冒险日志: 离线探险的事件序列 + LLM 润色后的叙事"""
    __tablename__ = "adventure_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), index=True)
    events: Mapped[list] = mapped_column(JSON, default=list)
    narrative: Mapped[str] = mapped_column(Text, default="")
    rewards: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
