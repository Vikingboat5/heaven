"""用官方 SDK 跑用户的示例 (排除手写 HTTP 差异)"""
import sys
from pathlib import Path

from volcenginesdkarkruntime import Ark

KEY = [l.split("=", 1)[1].strip() for l in (Path(__file__).resolve().parents[1] / "backend" / ".env").read_text(encoding="utf-8").splitlines() if l.startswith("ARK_VIDEO_API_KEY=")][0]

client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=KEY)

print("----- create request -----")
try:
    create_result = client.content_generation.tasks.create(
        model="doubao-seedance-1-5-pro-251215",
        content=[
            {"type": "text", "text": "无人机以极快速度穿越复杂障碍或自然奇观，带来沉浸式飞行体验  --duration 5 --camerafixed false --watermark true"},
            {"type": "image_url", "image_url": {"url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/seepro_i2v.png"}},
        ],
    )
    print("创建成功, id =", create_result.id)
except Exception as e:
    print("SDK 也失败:", type(e).__name__, str(e)[:500])
