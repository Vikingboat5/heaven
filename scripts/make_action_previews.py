"""宠物动作预览生成: 每个动作输出 播放GIF + 帧网格拼图, 供人工目检

产物: docs/demo/pet{id}-actions/{action}.gif + {action}_grid.png
GIF 按 manifest 的 sequence/frame_ms 播放, 底色用家园夜空色 (接近实机效果)。
用法: python scripts/make_action_previews.py <pet_id>
"""
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PET_DIR = ROOT / "backend" / "static" / "pets"
BG = (21, 12, 46)  # --color-night, 接近实机底色


def main() -> None:
    if len(sys.argv) != 2:
        print("用法: python scripts/make_action_previews.py <pet_id>")
        sys.exit(1)
    pet_id = int(sys.argv[1])
    pet_dir = PET_DIR / str(pet_id)
    manifest = json.loads((pet_dir / "manifest.json").read_text(encoding="utf-8"))
    out = ROOT / "docs" / "demo" / f"pet{pet_id}-actions"
    out.mkdir(parents=True, exist_ok=True)

    for action, meta in manifest["actions"].items():
        seq, ms = meta["sequence"], meta["frame_ms"]
        frames = []
        for i in seq:
            f = Image.open(pet_dir / "frames" / f"{action}_{i}.png").convert("RGBA")
            bg = Image.new("RGB", f.size, BG)
            bg.paste(f, (0, 0), f)
            frames.append(bg)
        # 播放 GIF
        frames[0].save(out / f"{action}.gif", save_all=True, append_images=frames[1:],
                       duration=ms, loop=0)
        # 帧网格拼图 (全部帧, 4 列)
        n = meta["frames"]
        cols = 4
        rows = (n + cols - 1) // cols
        grid = Image.new("RGB", (cols * 256, rows * 256), BG)
        for i in range(n):
            f = Image.open(pet_dir / "frames" / f"{action}_{i}.png").convert("RGBA")
            thumb = f.resize((256, 256), Image.LANCZOS)
            cell = Image.new("RGB", (256, 256), BG)
            cell.paste(thumb, (0, 0), thumb)
            grid.paste(cell, ((i % cols) * 256, (i // cols) * 256))
        grid.save(out / f"{action}_grid.png")
        print(f"{action}: {n}帧 @{ms}ms → {action}.gif + {action}_grid.png")

    print(f"\n预览目录: {out}")


if __name__ == "__main__":
    main()
