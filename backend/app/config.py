"""应用配置: 从 .env 读取, 全项目唯一配置入口"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 以本文件位置为锚点定位 backend/.env, 避免依赖启动时的工作目录
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_PATH), env_file_encoding="utf-8", extra="ignore")

    # LLM (OpenAI 兼容协议, 默认指向火山 Ark)
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    llm_model_standard: str = "doubao-pro-32k"
    llm_model_lite: str = "doubao-lite-32k"
    llm_timeout_seconds: int = 60
    # 推理强度: low 可显著降低 reasoning 模型的首字延迟 (实测 kimi-k3 16s -> 5s)
    # 设为空字符串则不传该参数 (用于不支持此参数的模型)
    llm_reasoning_effort: str = "low"

    # 生图 (Agent Plan 视觉端点; 注意与对话的 /api/plan/v1 不同)
    ark_image_base_url: str = "https://ark.cn-beijing.volces.com/api/plan/v3"
    ark_image_model: str = "doubao-seedream-5.0-lite"
    # 生图模式: live=调用 Ark 生图管线; reuse=复用素材库已有形象(生图套餐不可用时的临时方案)
    petgen_mode: str = "live"

    # 生视频 (2026-09-12: AtlasCloud seedance-2.0-mini, 首尾帧 i2v; key 仅本地 .env, gitignore 覆盖)
    atlascloud_api_key: str = ""

    # 成本熔断
    llm_daily_token_budget_per_pet: int = 20000
    llm_daily_token_budget_global: int = 10_000_000

    # 数据层
    database_url: str = "postgresql+psycopg://petparadise:petparadise_dev@localhost:5432/pet_paradise"
    redis_url: str = "redis://localhost:6379/0"

    # 应用
    app_env: str = "dev"
    jwt_secret: str = "dev-only-secret"


settings = Settings()
