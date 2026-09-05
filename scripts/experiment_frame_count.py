"""帧数实验 (2026-09): 同一外观在不同帧数下的精灵表质量对比

候选: 12 帧 (4x3, cell 512x682) vs 16 帧 (4x4, cell 512x512)
每组: 生图 → 下载 → 切帧+QC → 拼图 contact.png 供目检
产物: backend/static/pets/_experiment/{12,16}/{raw.jpg,qc.json,contact.png}

用法: python scripts/experiment_frame_count.py
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

SPECS_12 = (
    "睁眼自然微笑", "睁眼放松", "眼睛微眯", "眼睛半闭",
    "闭眼微笑", "闭眼微笑保持", "眼睛半闭", "眼睛微眯",
    "睁眼自然微笑", "双耳微微竖起", "头微微向左倾", "睁眼自然微笑与第1帧相同",
)
SPECS_16 = (
    "睁眼自然微笑", "睁眼放松", "眼睛微眯", "眼睛半闭",
    "闭眼微笑", "闭眼微笑保持", "眼睛半闭", "眼睛微眯",
    "睁眼自然微笑", "双耳微微竖起", "头微微向左倾", "头微微向左倾保持",
    "睁眼自然微笑", "头微微向右倾", "头微微向右倾保持", "睁眼自然微笑与第1帧相同",
)

CANDIDATES = {
    12: ActionTemplate(
        key="idle12", frame_count=12, grid_cols=4, grid_rows=3,
        frame_specs=SPECS_12, sequence=tuple(range(12)), frame_ms=110,
    ),
    16: ActionTemplate(
        key="idle16", frame_count=16, grid_cols=4, grid_rows=4,
        frame_specs=SPECS_16, sequence=tuple(range(16)), frame_ms=100,
    ),
}

OUT = Path(__file__).resolve().parents[1] / "backend" / "static" / "pets" / "_experiment"


def main() -> None:
    client = ArkImageClient()
    for n, action in CANDIDATES.items():
        d = OUT / str(n)
        d.mkdir(parents=True, exist_ok=True)
        print(f"[{n}帧] 生成中...", flush=True)
        prompt = build_prompt(action, APPEARANCE, STYLE)
        url = client.generate_image(prompt)
        raw = d / "raw.jpg"
        download(url, raw)
        frames, qc = process_sheet(raw, action, STYLE)
        # 拼图目检: 深色底上按网格排布提取帧
        cols, rows = action.grid_cols, action.grid_rows
        sheet = Image.new("RGBA", (cols * 256, rows * 256), (30, 20, 50, 255))
        for i, f in enumerate(frames):
            thumb = f.resize((256, 256), Image.LANCZOS)
            sheet.paste(thumb, ((i % cols) * 256, (i // cols) * 256), thumb)
        sheet.save(d / "contact.png")
        (d / "qc.json").write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
        bad_holes = {k: v for k, v in qc["holes"].items() if v}
        print(f"[{n}帧] QC passed={qc['passed']} outliers={qc['area_outliers']} holes={bad_holes}", flush=True)
    print("实验完成, 目检 _experiment/{12,16}/contact.png")


if __name__ == "__main__":
    main()
