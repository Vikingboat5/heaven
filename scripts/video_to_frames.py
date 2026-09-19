"""视频 → 帧序列 → 接入游戏 (帧动画管线跑通版, 2026-09-12)

视频=动作素材中间件, 帧序列=运行时格式。
用法: python scripts/video_to_frames.py [pet_id] [动作名] [视频路径]
默认: python scripts/video_to_frames.py 28 video_idle .../_video_probe/video.mp4

产物: backend/static/pets/{id}/frames/{action}_{i}.png + manifest 写入该动作 + contact.png + preview.gif
"""
import sys
from pathlib import Path

import imageio.v3 as iio
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.petgen.pipeline import cutout_dominant_bg  # noqa: E402

PET_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 28
ACTION = sys.argv[2] if len(sys.argv) > 2 else "video_idle"
SRC = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "backend" / "static" / "pets" / "_video_probe" / "video.mp4"

PET_DIR = ROOT / "backend" / "static" / "pets" / str(PET_ID)
SAMPLE_N = 24          # 采 24 帧 (121 帧 5s 视频 → 等距采样)
FRAME_MS = 90
CANVAS = 512


def main() -> None:
    print(f"读取 {SRC.name}...", flush=True)
    vid = iio.imread(SRC)
    total = vid.shape[0]
    idxs = [round(i * (total - 1) / (SAMPLE_N - 1)) for i in range(SAMPLE_N)]
    print(f"总 {total} 帧, 采 {SAMPLE_N} 帧", flush=True)

    frames_dir = PET_DIR / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for out_i, fi in enumerate(idxs):
        img = cutout_dominant_bg(Image.fromarray(vid[fi]))
        bbox = img.getchannel("A").getbbox()
        if bbox:
            img = img.crop(bbox)
        ratio = min(CANVAS * 0.80 / img.height, CANVAS * 0.86 / img.width)
        img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.LANCZOS)
        canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        canvas.paste(img, ((CANVAS - img.width) // 2, CANVAS - img.height - 30), img)
        canvas.save(frames_dir / f"{ACTION}_{out_i}.png")
        frames.append(canvas)

    # manifest 写入该动作 (幂等: 读现有 manifest 合并)
    import json
    mpath = PET_DIR / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {
        "pet_id": PET_ID, "style": "video", "actions": {}, "qc": {}}
    manifest["actions"][ACTION] = {
        "frames": SAMPLE_N,
        "sequence": list(range(SAMPLE_N)),
        "frame_ms": FRAME_MS,
    }
    manifest.setdefault("qc", {})[ACTION] = {"source": str(SRC.name), "sampled": SAMPLE_N}
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 目检: 拼图 + GIF
    BG = (21, 12, 46)
    cols, rows = 6, 4
    grid = Image.new("RGB", (cols * 170, rows * 170), BG)
    for i, f in enumerate(frames):
        t = f.resize((170, 170), Image.LANCZOS)
        cell = Image.new("RGB", (170, 170), BG)
        cell.paste(t, (0, 0), t)
        grid.paste(cell, ((i % cols) * 170, (i // cols) * 170))
    grid.save(PET_DIR / f"contact_{ACTION}.png")
    rgb = []
    for f in frames:
        bg = Image.new("RGB", f.size, BG)
        bg.paste(f, (0, 0), f)
        rgb.append(bg.resize((256, 256), Image.LANCZOS))
    rgb[0].save(PET_DIR / f"preview_{ACTION}.gif", save_all=True, append_images=rgb[1:], duration=FRAME_MS, loop=0)
    print(f"完成: {SAMPLE_N} 帧写入 {frames_dir}, manifest 已更新")
    print(f"目检: {PET_DIR / f'contact_{ACTION}.png'} / preview_{ACTION}.gif")


if __name__ == "__main__":
    main()
