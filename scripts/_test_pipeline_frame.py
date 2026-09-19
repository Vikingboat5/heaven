"""对照实验: 用当前 video_to_frames.py 的完整逻辑处理第 12 帧, 对比磁盘上的版本"""
import sys
from pathlib import Path

import imageio.v3 as iio
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.services.petgen.pipeline import cutout_dominant_bg, _decontaminate  # noqa: E402
from video_to_frames import remove_ground_shadow  # noqa: E402

vid = iio.imread(ROOT / "backend" / "static" / "pets" / "_video_probe" / "video.mp4")
total = vid.shape[0]
fi = round(12 * (total - 1) / 23)
print("视频源帧:", fi)

img = cutout_dominant_bg(Image.fromarray(vid[fi]))
img = Image.fromarray(_decontaminate(np.array(img)), "RGBA")
img = remove_ground_shadow(img)
bbox = img.getchannel("A").getbbox()
img = img.crop(bbox)
ratio = min(512 * 0.8 / img.height, 512 * 0.86 / img.width)
img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.LANCZOS)
canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
canvas.paste(img, ((512 - img.width) // 2, 512 - img.height - 30), img)

# 底部还有没有发丝线
a = np.asarray(canvas)
alpha = a[..., 3]
ys, xs = np.where(alpha > 0)
bottom = ys.min() + (ys.max() - ys.min()) * 0.88
band = np.zeros_like(alpha, dtype=bool)
band[int(bottom):, :] = alpha[int(bottom):, :] > 0
lbl, n = ndimage.label(band)
print("管线重跑后底部组件:")
for i in range(1, n + 1):
    ys2, xs2 = np.where(lbl == i)
    print(f"  组件{i}: w={xs2.max()-xs2.min()+1} h={ys2.max()-ys2.min()+1} 像素={len(ys2)}")

canvas.save(ROOT / "backend" / "static" / "pets" / "_video_probe" / "frame12_repipelined.png")
print("已存 _video_probe/frame12_repipelined.png")
