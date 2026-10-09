"""LLM 404 排查: 打印真实错误体"""
import json
import sys
import urllib.request

sys.path.insert(0, "backend")
from app.config import settings  # noqa: E402

payload = json.dumps({
    "model": settings.llm_model_standard,
    "messages": [{"role": "user", "content": "说一个字: 好"}],
    "max_tokens": 10,
}).encode()
req = urllib.request.Request(
    f"{settings.ark_base_url}/chat/completions",
    data=payload,
    headers={"Authorization": f"Bearer {settings.ark_api_key}", "Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        print("OK:", json.loads(r.read())["choices"][0]["message"]["content"])
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode(errors='replace')[:400]}")
print("base_url:", settings.ark_base_url)
