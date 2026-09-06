"""idle 流畅度对比实验 (2026-09): 节奏排帧 vs 双表24帧i2i链

产物 (backend/static/pets/_smooth/):
  A_paced.gif   —— 12帧不变, 呼吸式排帧(安静停留+偶尔动作) @140ms, 零生成成本
  B_sheet1.jpg / B_sheet2.jpg —— 双表: 第2表以第1表(生成返回的TOS URL)为参考图 i2i
  B_24f.gif     —— 拼接 24 帧 @90ms
  B_grid1.png / B_grid2.png —— 两张表的帧网格目检图
  report.json   —— 两表 QC

用法: python scripts/experiment_smooth_idle.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from PIL import Image  # noqa: E402

from app.services.petgen.pipeline import (  # noqa: E402
    ArkImageClient,
    build_prompt,
    download,
    process_sheet,
)
from app.services.petgen.profiles import STYLE_PROFILES, ActionTemplate  # noqa: E402

APPEARANCE = "一只可爱的暖橙色系的小狐狸, 大眼睛, 蓬松尾巴"
STYLE = STYLE_PROFILES["illustration"]
BG = (21, 12, 46)

# A: 呼吸式排帧 —— 安静(0重复) → 眨眼(1-7) → 安静 → 竖耳歪头(8-10) → 回正
A_SEQUENCE = (0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 0, 0, 0, 0, 8, 9, 10, 11, 0, 0, 0)
A_MS = 140

# B: 双表 24 帧。表1=眨眼+竖耳, 表2(i2i参考表1)=更细腻的头部摆动+尾巴轻摆
B1 = ActionTemplate(
    key="idleA", frame_count=12, grid_cols=4, grid_rows=3,
    frame_specs=(
        "睁眼自然微笑", "睁眼放松", "眼睛微眯", "眼睛半闭",
        "闭眼微笑", "闭眼微笑保持", "眼睛半闭", "眼睛微眯",
        "睁眼自然微笑", "双耳微微竖起", "双耳竖起保持", "睁眼自然微笑与第1帧相同",
    ),
    sequence=tuple(range(12)), frame_ms=90,
)
B2 = ActionTemplate(
    key="idleB", frame_count=12, grid_cols=4, grid_rows=3,
    frame_specs=(
        "睁眼自然微笑头居中", "头微微向左转", "头向左转保持", "头回中",
        "睁眼自然微笑", "头微微向右转", "头向右转保持", "头回中",
        "睁眼自然微笑", "蓬松尾巴轻轻向左摆", "蓬松尾巴轻轻向右摆", "睁眼自然微笑与第1帧相同",
    ),
    sequence=tuple(range(12)), frame_ms=90,
)
# i2i 参考提示: 强调与参考图同一角色同一布局
B2_REFERENCE_CLAUSE = "与参考图片中是完全相同的角色、相同的画风、相同的12格精灵表布局, "

OUT = Path(__file__).resolve().parents[1] / "backend" / "static" / "pets" / "_smooth"
PET28 = Path(__file__).resolve().parents[1] / "backend" / "static" / "pets" / "28"


def save_gif(frames: list[Image.Image], path: Path, ms: int) -> None:
    rgb = []
    for f in frames:
        bg = Image.new("RGB", f.size, BG)
        bg.paste(f, (0, 0), f)
        rgb.append(bg)
    rgb[0].save(path, save_all=True, append_images=rgb[1:], duration=ms, loop=0)


def save_grid(frames: list[Image.Image], path: Path, cols: int = 4) -> None:
    rows = (len(frames) + cols - 1) // cols
    grid = Image.new("RGB", (cols * 256, rows * 256), BG)
    for i, f in enumerate(frames):
        thumb = f.resize((256, 256), Image.LANCZOS)
        cell = Image.new("RGB", (256, 256), BG)
        cell.paste(thumb, (0, 0), thumb)
        grid.paste(cell, ((i % cols) * 256, (i // cols) * 256))
    grid.save(path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- A: 纯节奏版 (用 pet28 现有 idle 帧, 零生成成本) ----
    idle_frames = [Image.open(PET28 / "frames" / f"idle_{i}.png").convert("RGBA") for i in range(12)]
    save_gif([idle_frames[i] for i in A_SEQUENCE], OUT / "A_paced.gif", A_MS)
    print("A_paced.gif 完成 (12帧呼吸式排帧@140ms, 循环3.4s)", flush=True)

    # ---- B: 双表 24 帧 i2i 链 ----
    client = ArkImageClient()
    print("B 表1 生成中...", flush=True)
    url1 = client.generate_image(build_prompt(B1, APPEARANCE, STYLE))
    download(url1, OUT / "B_sheet1.jpg")
    frames1, qc1 = process_sheet(OUT / "B_sheet1.jpg", B1, STYLE)
    save_grid(frames1, OUT / "B_grid1.png")
    print(f"B 表1 QC passed={qc1['passed']}", flush=True)

    print("B 表2 生成中 (i2i 参考表1)...", flush=True)
    prompt2 = B2_REFERENCE_CLAUSE + build_prompt(B2, APPEARANCE, STYLE)
    url2 = client.generate_image(prompt2, reference_url=url1)
    download(url2, OUT / "B_sheet2.jpg")
    frames2, qc2 = process_sheet(OUT / "B_sheet2.jpg", B2, STYLE)
    save_grid(frames2, OUT / "B_grid2.png")
    print(f"B 表2 QC passed={qc2['passed']}", flush=True)

    save_gif(frames1 + frames2, OUT / "B_24f.gif", 90)
    (OUT / "report.json").write_text(json.dumps(
        {"sheet1": qc1, "sheet2": qc2}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("B_24f.gif 完成 (24帧@90ms, 循环2.2s)")
    print(f"\n产物目录: {OUT}")


if __name__ == "__main__":
    main()
