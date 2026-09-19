"""关键判别实验: 用视频 key 在标准端点(api/v3)试生图
- 生图也 404 → 这个 key/账号根本没有标准端点权限 (开通在了别处)
- 生图成功 → 标准端点通, 只是视频模型没开通
"""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = [l.split("=", 1)[1].strip() for l in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines() if l.startswith("ARK_VIDEO_API_KEY=")][0]

# 先看这个 key 的模型列表里 seedream 的完整 id
req = urllib.request.Request("https://ark.cn-beijing.volces.com/api/v3/models",
                             headers={"Authorization": f"Bearer {KEY}"})
data = json.loads(urllib.request.urlopen(req, timeout=60).read())
seedreams = [m["id"] for m in data.get("data", []) if "seedream" in m["id"]]
print("该 key 可见的 seedream:", seedreams)

if seedreams:
    body = json.dumps({"model": seedreams[0], "prompt": "一只小猫", "size": "2048x2048", "response_format": "url"}).encode()
    req = urllib.request.Request("https://ark.cn-beijing.volces.com/api/v3/images/generations",
                                 data=body, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            print("生图结果: 成功!", json.loads(r.read())["data"][0]["url"][:80])
    except urllib.error.HTTPError as e:
        print(f"生图结果: {e.code} {e.read().decode(errors='replace')[:250]}")
