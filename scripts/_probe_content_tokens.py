"""探 max_tokens 与 content 的关系 (deepseek-v4-pro)"""
import asyncio
import sys

sys.path.insert(0, "backend")

import httpx  # noqa: E402

from app.config import settings  # noqa: E402


async def t():
    for mt in (10, 700):
        payload = {
            "model": settings.llm_model_lite,
            "messages": [{"role": "user", "content": "说一句话: 今天天气很好"}],
            "max_tokens": mt,
        }
        if settings.llm_reasoning_effort:
            payload["reasoning_effort"] = settings.llm_reasoning_effort
        async with httpx.AsyncClient(base_url=settings.ark_base_url, timeout=120) as cli:
            r = await cli.post("/chat/completions", json=payload,
                               headers={"Authorization": f"Bearer {settings.ark_api_key}"})
            d = r.json()
            if r.status_code != 200:
                print(f"max_tokens={mt}: HTTP {r.status_code} {str(d)[:200]}")
                continue
            ch = d["choices"][0]
            content = ch["message"].get("content")
            print(f"max_tokens={mt}: content={repr((content or '')[:40])} finish={ch.get('finish_reason')}")


asyncio.run(t())
