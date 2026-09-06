"""重建实验 B 的 24 帧 GIF: 用最新后处理(线条清除)离线重切 B 双表"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT))  # 让 scripts.experiment_smooth_idle 可导入

from PIL import Image  # noqa: E402
from app.services.petgen.pipeline import process_sheet  # noqa: E402
from app.services.petgen.profiles import STYLE_PROFILES  # noqa: E402
from scripts.experiment_smooth_idle import B1, B2, save_gif, save_grid  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "backend" / "static" / "pets" / "_smooth"
STYLE = STYLE_PROFILES["illustration"]

frames1, qc1 = process_sheet(OUT / "B_sheet1.jpg", B1, STYLE)
frames2, qc2 = process_sheet(OUT / "B_sheet2.jpg", B2, STYLE)
save_grid(frames1, OUT / "B_grid1.png")
save_grid(frames2, OUT / "B_grid2.png")
save_gif(frames1 + frames2, OUT / "B_24f.gif", 90)
print(f"sheet1 passed={qc1['passed']}, sheet2 passed={qc2['passed']}, B_24f.gif 已重建")

# A 的呼吸式排帧 GIF 也用清线后的 idle 帧重建
from scripts.experiment_smooth_idle import A_MS, A_SEQUENCE, PET28  # noqa: E402

idle_frames = [Image.open(PET28 / "frames" / f"idle_{i}.png").convert("RGBA") for i in range(12)]
save_gif([idle_frames[i] for i in A_SEQUENCE], OUT / "A_paced.gif", A_MS)
print("A_paced.gif 已重建")
