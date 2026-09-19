"""首尾帧生成: 待机动作"摇尾巴+眨眼"的首帧/尾帧 (i2i 参考 idle_0 保持角色一致)

动作设计: 尾巴从左摆到右 (首帧=尾巴垂左侧, 尾帧=尾巴垂右侧), 中间眨一次眼
播放时用 正放+倒放 (ping-pong) 形成无缝循环
产物: backend/static/pets/_video_probe/{frame_start.png, frame_end.png}
"""
import base64
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.petgen.pipeline import cutout_dominant_bg, download  # noqa: E402

OUT = ROOT / "backend" / "static" / "pets" / "_video_probe"
OUT.mkdir(parents=True, exist_ok=True)

# Plan 端点生图 (已验证可用, 支持 data URL i2i)
BASE = "https://ark.cn-beijing.volces.com/api/plan/v3"
KEY = [l.split("=", 1)[1].strip() for l in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines() if l.startswith("ARK_API_KEY=")][0]
MODEL = "doubao-seedream-5.0-lite"

IDLE_FRAME = ROOT / "backend" / "static" / "pets" / "28" / "frames" / "idle_0.png"
REF = "data:image/png;base64," + base64.b64encode(IDLE_FRAME.read_bytes()).decode()

FRAME_PROMPTS = {
    "frame_start": "参考图中的这只小狐狸, 保持完全相同的毛色长相画风, 坐姿, 睁大眼睛自然微笑, 蓬松的大尾巴垂在身体左侧贴地, 纯白色背景, 无阴影, 无文字",
    "frame_end": "参考图中的这只小狐狸, 保持完全相同的毛色长相画风, 坐姿, 睁大眼睛自然微笑, 蓬松的大尾巴垂在身体右侧贴地, 纯白色背景, 无阴影, 无文字",
}


def gen(name: str, prompt: str) -> None:
    payload = {"model": MODEL, "prompt": prompt, "size": "2048x2048", "response_format": "url", "image": REF}
    req = urllib.request.Request(
        f"{BASE}/images/generations",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        url = json.loads(r.read())["data"][0]["url"]
    raw = OUT / f"{name}_raw.jpg"
    download(url, raw)
    img = cutout_dominant_bg(__import__("PIL.Image", fromlist=["Image"]).open(raw))
    bbox = img.getchannel("A").getbbox()
    if bbox:
        img = img.crop(bbox)
    img.save(OUT / f"{name}.png")
    print(f"{name} 完成", flush=True)


for name, prompt in FRAME_PROMPTS.items():
    print(f"生成 {name}...", flush=True)
    gen(name, prompt)
print(f"产物: {OUT}")
