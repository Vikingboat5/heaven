"""LLM 网关: OpenAI 兼容客户端 + 分层路由 + 用量审计 + 预算熔断

设计约束(对应架构文档第 3 节):
- 业务代码只调 gateway, 不直接接触任何供应商 SDK
- tier="standard" 实时对话 / tier="lite" 日志润色与事实抽取
- 每次调用记录 token 用量到 logs/llm_usage.jsonl (成本审计基础)
- 预算熔断: Redis 日计数, 超额抛 BudgetExceeded, 由业务层降级
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import AsyncIterator

import httpx

from ..config import settings

USAGE_LOG = Path(__file__).resolve().parents[3] / "logs" / "llm_usage.jsonl"


class BudgetExceeded(Exception):
    """预算熔断: 单宠物或全局当日 token 超限"""


@dataclass
class ChatResult:
    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    model: str


class BudgetGuard:
    """单宠物 + 全局每日 token 配额。Redis 不可用时降级为进程内存(仅开发用)。"""

    def __init__(self) -> None:
        self._memory: dict[str, int] = {}
        self._redis = None
        try:
            import redis

            self._redis = redis.Redis.from_url(settings.redis_url, socket_timeout=1)
            self._redis.ping()
        except Exception:
            self._redis = None

    def _keys(self, pet_id: str) -> tuple[str, str]:
        today = date.today().isoformat()
        return f"llm:budget:pet:{pet_id}:{today}", f"llm:budget:global:{today}"

    def consume(self, pet_id: str, tokens: int) -> None:
        """消费配额, 超限抛 BudgetExceeded"""
        pet_key, global_key = self._keys(pet_id)
        if self._redis:
            pipe = self._redis.pipeline()
            pipe.incrby(pet_key, tokens)
            pipe.expire(pet_key, 172800)
            pipe.incrby(global_key, tokens)
            pipe.expire(global_key, 172800)
            pet_used, _, global_used, _ = pipe.execute()
        else:
            pet_used = self._memory[pet_key] = self._memory.get(pet_key, 0) + tokens
            global_used = self._memory[global_key] = self._memory.get(global_key, 0) + tokens

        if pet_used > settings.llm_daily_token_budget_per_pet:
            raise BudgetExceeded(f"pet {pet_id} daily budget exceeded: {pet_used}")
        if global_used > settings.llm_daily_token_budget_global:
            raise BudgetExceeded(f"global daily budget exceeded: {global_used}")


class LLMGateway:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.ark_base_url,
            headers={"Authorization": f"Bearer {settings.ark_api_key}"},
            timeout=settings.llm_timeout_seconds,
        )
        self.budget = BudgetGuard()

    def _model_for(self, tier: str) -> str:
        return settings.llm_model_standard if tier == "standard" else settings.llm_model_lite

    @staticmethod
    def _build_payload(model: str, messages: list[dict], max_tokens: int, temperature: float) -> dict:
        payload: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        # reasoning 模型(如 kimi-k3)压低推理强度, 显著降低首字延迟; 空字符串则不传
        if settings.llm_reasoning_effort:
            payload["reasoning_effort"] = settings.llm_reasoning_effort
        return payload

    @staticmethod
    def _log_usage(record: dict) -> None:
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def chat(
        self,
        messages: list[dict],
        tier: str = "standard",
        pet_id: str = "anonymous",
        max_tokens: int = 512,
        temperature: float = 0.8,
    ) -> ChatResult:
        """非流式对话, 返回完整结果与用量"""
        model = self._model_for(tier)
        started = time.perf_counter()
        resp = await self._client.post(
            "/chat/completions",
            json=self._build_payload(model, messages, max_tokens, temperature),
        )
        resp.raise_for_status()
        data = resp.json()
        latency_ms = int((time.perf_counter() - started) * 1000)

        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        self.budget.consume(pet_id, prompt_tokens + completion_tokens)
        self._log_usage({
            "ts": time.time(), "model": model, "tier": tier, "pet_id": pet_id,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "latency_ms": latency_ms, "stream": False,
        })
        return ChatResult(
            content=data["choices"][0]["message"].get("content") or "",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            model=model,
        )

    async def chat_stream(
        self,
        messages: list[dict],
        tier: str = "standard",
        pet_id: str = "anonymous",
        max_tokens: int = 512,
        temperature: float = 0.8,
    ) -> AsyncIterator[str]:
        """流式对话(SSE), 逐段产出 content delta; 结束后记录用量"""
        model = self._model_for(tier)
        started = time.perf_counter()
        usage: dict = {}
        payload = self._build_payload(model, messages, max_tokens, temperature)
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
        async with self._client.stream(
            "POST",
            "/chat/completions",
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if chunk.get("usage"):
                    usage = chunk["usage"]
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content

        latency_ms = int((time.perf_counter() - started) * 1000)
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        if prompt_tokens or completion_tokens:
            self.budget.consume(pet_id, prompt_tokens + completion_tokens)
        self._log_usage({
            "ts": time.time(), "model": model, "tier": tier, "pet_id": pet_id,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "latency_ms": latency_ms, "stream": True,
        })

    async def close(self) -> None:
        await self._client.aclose()


gateway = LLMGateway()
