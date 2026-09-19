"""探测视频 key 的可用模型 + 打印真实错误体"""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = None
for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("ARK_VIDEO_API_KEY="):
        KEY = line.split("=", 1)[1].strip()

BASE = "https://ark.cn-beijing.volces.com/api/v3"


def api(method, path, payload=None):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:400]


# 1. 模型列表
code, body = api("GET", "/models")
print("GET /models:", code, str(body)[:200])

# 2. 视频任务(带错误体)
code, body = api("POST", "/contents/generations/tasks", {
    "model": "doubao-seedance-1-5-pro-251215",
    "content": [{"type": "text", "text": "test"}],
})
print("POST video task:", code, str(body)[:400])
