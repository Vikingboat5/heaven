"""宠物乐园后端入口"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import adventure, auth, dialogue, eggs, health, items, pets, quiz
from .llm.gateway import gateway

# 宠物生成素材目录 (以本文件位置锚定, 不依赖启动目录)
_STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
_STATIC_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时: 轻量 schema 补齐(幂等, 开发期代替 alembic; 上线前接正式迁移) →
    # 播种物品发现状态(幂等) → 迁移旧格式背包; DB 不可用时留痕跳过, 不阻塞启动
    from sqlalchemy import text

    from .database import SessionLocal
    from .services import items as item_service

    try:
        db = SessionLocal()
        db.execute(text("ALTER TABLE pets ADD COLUMN IF NOT EXISTS loadout JSONB DEFAULT '{}'::jsonb"))
        db.execute(text("ALTER TABLE pets ADD COLUMN IF NOT EXISTS collection JSONB DEFAULT '[]'::jsonb"))
        # 简化版(v1.1)已从模型删除的旧列, 同步从库中移除
        db.execute(text("ALTER TABLE pets DROP COLUMN IF EXISTS state"))
        db.execute(text("ALTER TABLE pets DROP COLUMN IF EXISTS state_updated_at"))
        db.execute(text(
            "CREATE TABLE IF NOT EXISTS item_states ("
            "item_id VARCHAR(64) PRIMARY KEY, "
            "first_discovered_by INTEGER REFERENCES users(id), "
            "first_discovered_at TIMESTAMP)"
        ))
        db.commit()
        added = item_service.seed_item_states(db)
        migrated = item_service.migrate_all_inventories(db)
        db.close()
        print(f"[startup] schema 补齐完成; item_states 播种 +{added}, 背包迁移 {migrated} 只宠物")
    except Exception as e:
        print(f"[startup] schema/播种/迁移跳过(DB 不可用?): {e}")
    yield
    await gateway.close()


app = FastAPI(title="Pet Paradise", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(eggs.router)
app.include_router(pets.router)
app.include_router(dialogue.router)
app.include_router(adventure.router)
app.include_router(items.router)
app.include_router(quiz.router)
