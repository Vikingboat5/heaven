"""测试公共夹具

- db: SQLite 内存库(StaticPool 共享连接), 与 PG 解耦, 服务层函数直接可测
- api_client: FastAPI TestClient + get_db 依赖覆盖, 测 API 流程
- 自动将 DailyLimiter 切到内存模式, 避免测试依赖 Redis/跨天残留
"""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 保证 `backend.app` 包可导入(项目根目录为 rootdir)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.database import Base, get_db  # noqa: E402
from backend.app import models  # noqa: F401, E402  必须先导入模型, Base.metadata 才有表结构
from backend.app.config import settings  # noqa: E402
from backend.app.services.daily_limit import limiter  # noqa: E402


@pytest.fixture(autouse=True)
def live_petgen_mode():
    """测试默认走 live 生图路径(.env 里可能配了 reuse); 用例内可显式改写"""
    original = settings.petgen_mode
    settings.petgen_mode = "live"
    yield
    settings.petgen_mode = original


def _make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db():
    Session = _make_session()
    session = Session()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def memory_limiter():
    """每个测试用例使用干净的内存限流器"""
    original = limiter._r
    limiter._r = None
    limiter._mem.clear()
    yield
    limiter._r = original


@pytest.fixture()
def api_client(db):
    from fastapi.testclient import TestClient

    from backend.app.main import app

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def noop_sprite_task(monkeypatch):
    """孵化接口的 BackgroundTasks 生图任务置空: API 测试不触发真实生图/素材复制"""
    from backend.app.services.petgen import birth

    monkeypatch.setattr(birth, "generate_sprite_task", lambda pet_id, session_factory=None: None)
