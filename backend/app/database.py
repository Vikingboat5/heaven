"""数据库连接: SQLAlchemy 2.0 引擎与会话"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


# connect_timeout: psycopg3 默认无连接超时, PG 不在时 connect 会无限挂起
# (曾导致 TestClient  lifespan 里的 seed_tasks 挂死整个测试套件)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI 依赖注入用"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
