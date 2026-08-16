"""宠物乐园后端入口"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import adventure, auth, dialogue, eggs, health, pets, quiz, tasks
from .database import SessionLocal
from .llm.gateway import gateway
from .services.tasks import seed_tasks

# 宠物生成素材目录 (以本文件位置锚定, 不依赖启动目录)
_STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
_STATIC_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时播种任务配置(幂等); DB 不可用时跳过, 不阻塞服务启动
    try:
        db = SessionLocal()
        seed_tasks(db)
        db.close()
    except Exception:
        pass
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
app.include_router(tasks.router)
app.include_router(adventure.router)
app.include_router(quiz.router)
