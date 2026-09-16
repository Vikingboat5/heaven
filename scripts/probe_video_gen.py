"""探测 Plan 端点的视频生成能力 (seedance i2v): 宠物帧 → 几秒视频 → 切帧
probe 目标:
1. 端点是否接受 content_generation 任务 (模型名探测)
2. data URL 参考图是否可用
3. 产出视频质量 + 切帧可行性
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402

OUT = ROOT / "backend" / "static" / "pets" / "_video_probe"
OUT.mkdir(parents=True, exist_ok=True)

frame = ROOT / "backend" / "static" / "pets" / "28" / "frames" / "idle_0.png"
ref = "data:image/png;base64," + base64.b64encode(frame.read_bytes()).decode()

BASE = settings.ark_image_base_url.rstrip("/")
KEY = settings.ark_api_key

# seedance 任务式 API (Ark 视频生成惯例): POST {base}/contents/generations/tasks
payload = {
    "model": sys.argv[1] if len(sys.argv) > 1 else "doubao-seedance-1-5-pro",
    "content": [
        {"type": "text", "text": "这只小狐狸安静地坐着, 蓬松的大尾巴轻轻左右摆动, 偶尔眨一下眼睛, 镜头固定不动, 循环感"},
        {"type": "image_url", "image_url": {"url": ref}},
    ],
}

req = urllib.request.Request(
    f"{BASE}/contents/generations/tasks",
    data=json.dumps(payload).encode(),
    headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())
        print("任务创建成功:", json.dumps(resp, ensure_ascii=False)[:300])
        task_id = resp.get("id")
        (OUT / "task.json").write_text(json.dumps(resp, ensure_ascii=False, indent=2))
        print("task_id =", task_id)
except urllib.error.HTTPError as e:
    body = e.read().decode(errors="replace")[:500]
    print(f"HTTP {e.code}: {body}")
except Exception as e:
    print(f"失败: {e}")
