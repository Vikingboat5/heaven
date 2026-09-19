"""单测 remove_ground_shadow: 加载 video_idle_12.png, 跑规则, 看底部组件命运"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from video_to_frames import remove_ground_shadow  # noqa: E402

p = ROOT / "backend" / "static" / "pets" / "28" / "frames" / "video_idle_12.png"
img = Image.open(p)
before = np.asarray(img).copy()
after = np.asarray(remove_ground_shadow(img))
diff = (before[..., 3] != after[..., 3]).sum()
print("alpha 变化像素数:", diff)

# 手动复查底部组件
alpha = after[..., 3]
ys, xs = np.where(alpha > 0)
y0, y1 = ys.min(), ys.max()
bottom = y0 + (y1 - y0) * 0.88
band = np.zeros_like(alpha, dtype=bool)
band[int(bottom):, :] = alpha[int(bottom):, :] > 0
lbl, n = ndimage.label(band)
print("清理后底部组件:")
for i in range(1, n + 1):
    ys2, xs2 = np.where(lbl == i)
    print(f"  组件{i}: w={xs2.max()-xs2.min()+1} h={ys2.max()-ys2.min()+1} 像素={len(ys2)}")
