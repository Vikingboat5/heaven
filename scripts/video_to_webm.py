"""视频 → 透明 WebM: 逐帧抠白底 → VP9 alpha 视频 (浏览器可直接 <video> 播放合成)

用法: python scripts/video_to_webm.py [视频路径]
默认: backend/static/pets/_video_probe/video.mp4 → idle.webm
产物: {out_dir}/idle.webm (透明通道) + contact.png (抽帧目检)
"""
import sys
from pathlib import Path

import imageio.v3 as iio
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.petgen.pipeline import cutout_dominant_bg  # noqa: E402

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "backend" / "static" / "pets" / "_video_probe" / "video.mp4"
OUT_DIR = SRC.parent
FPS = 24


def main() -> None:
    print(f"读取视频 {SRC.name}...", flush=True)
    vid = iio.imread(SRC)  # (T, H, W, 3)
    total, h, w, _ = vid.shape
    print(f"{total} 帧 {w}x{h}, 逐帧抠图中...", flush=True)

    out_frames = np.empty((total, h, w, 4), dtype=np.uint8)
    for i in range(total):
        rgba = np.asarray(cutout_dominant_bg(Image.fromarray(vid[i])))
        out_frames[i] = rgba
        if i % 20 == 0:
            print(f"  {i}/{total}", flush=True)

    webm = OUT_DIR / "idle.webm"
    print("编码 WebM (VP9 + alpha)...", flush=True)
    iio.imwrite(
        webm, out_frames,
        fps=FPS, codec="libvpx-vp9",
        output_params=["-pix_fmt", "yuva420p", "-crf", "32"],
    )
    print(f"WebM: {webm.stat().st_size // 1024}KB", flush=True)

    # 抽帧目检拼图 (夜空底)
    BG = (21, 12, 46)
    n = 12
    idxs = [round(i * (total - 1) / (n - 1)) for i in range(n)]
    cols, rows = 4, 3
    grid = Image.new("RGB", (cols * 256, rows * 256), BG)
    for out_i, fi in enumerate(idxs):
        f = Image.fromarray(out_frames[fi]).resize((256, 256), Image.LANCZOS)
        cell = Image.new("RGB", (256, 256), BG)
        cell.paste(f, (0, 0), f)
        grid.paste(cell, ((out_i % cols) * 256, (out_i // cols) * 256))
    grid.save(OUT_DIR / "contact.png")
    print(f"目检拼图: {OUT_DIR / 'contact.png'}")


if __name__ == "__main__":
    main()
