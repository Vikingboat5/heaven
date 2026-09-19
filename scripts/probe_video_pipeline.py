"""视频生动画探针 (2026-09-12): seedance i2v → 切帧 → 抠图 → 预览 GIF

链路: 宠物 idle 帧(data URL 参考图) → seedance-1.5-pro 生成 5s 白底动画
     → 等距抽 12 帧 → 主色抠图 → 512 画布 → preview.gif
产物: backend/static/pets/_video_probe/{video.mp4, frames/, contact.png, preview.gif}
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

import imageio.v3 as iio
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.petgen.pipeline import cutout_dominant_bg, download  # noqa: E402

OUT = ROOT / "backend" / "static" / "pets" / "_video_probe"
OUT.mkdir(parents=True, exist_ok=True)

BASE = "https://ark.cn-beijing.volces.com/api/v3"
KEY = None
for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("ARK_VIDEO_API_KEY="):
        KEY = line.split("=", 1)[1].strip()
assert KEY, "backend/.env 缺 ARK_VIDEO_API_KEY"

PET_FRAME = ROOT / "backend" / "static" / "pets" / "28" / "frames" / "idle_0.png"
FRAMES_N = 12


def api(method: str, path: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def main() -> None:
    ref = "data:image/png;base64," + base64.b64encode(PET_FRAME.read_bytes()).decode()
    prompt = (
        "纯白背景, 参考图中的小狐狸安静地坐着, 蓬松的大尾巴轻轻左右摆动, 偶尔眨一下眼睛, "
        "镜头固定不动, 动作循环流畅, 无其他元素 --ratio 1:1 --duration 3"  # 3s 精简档 (spec §6)
    )
    print("创建视频任务...", flush=True)
    task = api("POST", "/contents/generations/tasks", {
        "model": "doubao-seedance-1-5-pro-251215",  # 实测: 需带日期后缀, 裸名 404
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": ref}},
        ],
    })
    task_id = task["id"]
    print(f"task_id={task_id}, 轮询中...", flush=True)

    video_url = None
    deadline = time.time() + 420
    while time.time() < deadline:
        time.sleep(10)
        st = api("GET", f"/contents/generations/tasks/{task_id}")
        status = st.get("status")
        print(f"  状态: {status}", flush=True)
        if status == "succeeded":
            video_url = st["content"]["video_url"]
            break
        if status in ("failed", "cancelled"):
            raise SystemExit(f"任务失败: {json.dumps(st, ensure_ascii=False)[:400]}")
    if not video_url:
        raise SystemExit("超时未出片")

    mp4 = OUT / "video.mp4"
    download(video_url, mp4)
    print(f"视频已下载: {mp4.stat().st_size // 1024}KB", flush=True)

    # 等距抽帧
    vid = iio.imread(mp4)  # (T, H, W, C)
    total = vid.shape[0]
    print(f"视频共 {total} 帧, 等距抽 {FRAMES_N} 帧", flush=True)
    idxs = [round(i * (total - 1) / (FRAMES_N - 1)) for i in range(FRAMES_N)]
    frames_dir = OUT / "frames"
    frames_dir.mkdir(exist_ok=True)
    frames = []
    for out_i, fi in enumerate(idxs):
        img = cutout_dominant_bg(Image.fromarray(vid[fi]))
        bbox = img.getchannel("A").getbbox()
        if bbox:
            img = img.crop(bbox)
        # 居中进 512 画布
        ratio = min(512 * 0.8 / img.height, 512 * 0.86 / img.width)
        img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.LANCZOS)
        canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        canvas.paste(img, ((512 - img.width) // 2, 512 - img.height - 30), canvas)
        canvas.save(frames_dir / f"f_{out_i:02d}.png")
        frames.append(canvas)

    # 拼图 + 预览 GIF (夜空底色)
    BG = (21, 12, 46)
    cols = 4
    rows = (FRAMES_N + cols - 1) // cols
    grid = Image.new("RGB", (cols * 256, rows * 256), BG)
    for i, f in enumerate(frames):
        t = f.resize((256, 256), Image.LANCZOS)
        cell = Image.new("RGB", (256, 256), BG)
        cell.paste(t, (0, 0), t)
        grid.paste(cell, ((i % cols) * 256, (i // cols) * 256))
    grid.save(OUT / "contact.png")
    rgb = []
    for f in frames:
        bg = Image.new("RGB", f.size, BG)
        bg.paste(f, (0, 0), f)
        rgb.append(bg)
    rgb[0].save(OUT / "preview.gif", save_all=True, append_images=rgb[1:], duration=90, loop=0)
    print(f"产物齐: {OUT}")


if __name__ == "__main__":
    main()
