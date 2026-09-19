"""在 640 原始帧上插桩 remove_ground_shadow 的判定过程"""
import sys
from pathlib import Path

import imageio.v3 as iio
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.petgen.pipeline import cutout_dominant_bg, _decontaminate  # noqa: E402

vid = iio.imread(ROOT / "backend" / "static" / "pets" / "_video_probe" / "video.mp4")
fi = round(12 * (vid.shape[0] - 1) / 23)
img = cutout_dominant_bg(Image.fromarray(vid[fi]))
img = Image.fromarray(_decontaminate(np.array(img)), "RGBA")

a = np.array(img)
alpha = a[..., 3]
ys, xs = np.where(alpha > 0)
y0, y1 = int(ys.min()), int(ys.max())
h = y1 - y0
w_content = int(xs.max()) - int(xs.min()) + 1
print(f"640帧: 内容 y0={y0} y1={y1} h={h} w={w_content}")

# 浅色影子规则后, 看浅色组件
bottom = y0 + h * 0.88
light = (a[..., :3].min(axis=2) > 150) & (alpha > 0)
light[: int(bottom), :] = False
lbl, n = ndimage.label(light)
print(f"浅色组件 {n} 个:")
for i in range(1, n + 1):
    ys2, xs2 = np.where(lbl == i)
    w2 = int(xs2.max()) - int(xs2.min()) + 1
    cy = (int(ys2.min()) + int(ys2.max())) / 2
    print(f"  浅组件{i}: w={w2}({w2 / w_content * 100:.0f}%) cy={cy:.0f} (bottom={bottom:.0f}) 像素={len(ys2)}")
    if w2 > w_content * 0.3:
        print("    → 命中浅色规则, 删除")

# 发丝线规则判定 (不改图, 只判)
band = np.zeros_like(alpha, dtype=bool)
band[int(bottom):, :] = alpha[int(bottom):, :] > 0
lbl2, n2 = ndimage.label(band)
print(f"底部组件 {n2} 个:")
for i in range(1, n2 + 1):
    ys2, xs2 = np.where(lbl2 == i)
    w2 = int(xs2.max()) - int(xs2.min()) + 1
    h2 = int(ys2.max()) - int(ys2.min()) + 1
    hit = (w2 > w_content * 0.3 and h2 < 14) or (h2 <= 2 and w2 > 40)
    print(f"  底组件{i}: w={w2} h={h2} 像素={len(ys2)} 命中={hit}")
