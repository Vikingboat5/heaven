"""逐个探测视频模型哪个已开通 (裸模型名直连)"""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = [l.split("=", 1)[1].strip() for l in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines() if l.startswith("ARK_VIDEO_API_KEY=")][0]

MODELS = [
    "doubao-seedance-1-5-pro-251215",
    "doubao-seedance-2-5-260628",
    "doubao-seedance-2-0-260128",
    "doubao-seedance-1-0-pro-250528",
    "doubao-seedance-1-0-pro-fast-251015",
    "doubao-seedance-1-0-lite-i2v-250428",
]

for m in MODELS:
    req = urllib.request.Request(
        "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
        data=json.dumps({"model": m, "content": [{"type": "text", "text": "一只小猫坐着眨眼"}]}).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
            print(f"[OK] {m}: task id={resp.get('id')}", flush=True)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:150]
        print(f"[{e.code}] {m}: {body}", flush=True)
