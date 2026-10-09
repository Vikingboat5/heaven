"""续费后模型可用性全探针: LLM 各候选模型 + 生图"""
import json
import sys
import urllib.request

sys.path.insert(0, "backend")
from app.config import settings  # noqa: E402

KEY = settings.ark_api_key
BASE = settings.ark_base_url

for model in ["kimi-k3", "kimi-k2.5", "doubao-seed-2.0-pro", "deepseek-v4-pro"]:
    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "好"}], "max_tokens": 5}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=payload,
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"[OK] LLM {model}")
    except urllib.error.HTTPError as e:
        print(f"[{e.code}] LLM {model}: {e.read().decode(errors='replace')[:100]}")

payload = json.dumps({"model": "doubao-seedream-5.0-lite", "prompt": "一朵小花", "size": "2048x2048", "response_format": "url"}).encode()
req = urllib.request.Request("https://ark.cn-beijing.volces.com/api/plan/v3/images/generations", data=payload,
                             headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=180) as r:
        print("[OK] 生图 seedream-5.0-lite")
except urllib.error.HTTPError as e:
    print(f"[{e.code}] 生图: {e.read().decode(errors='replace')[:150]}")
