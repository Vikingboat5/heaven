"""离线修正: UI 素材与物品图的 bbox 裁剪失效修复 (零 token)

根因: 抠图羽化让 alpha 全图带微量非零值, getbbox 返回整张画布 → 未裁剪,
前端 100% 拉伸后内容只剩中间一条。按 alpha>24 重新裁切。
物品图额外重置为 256x256 居中画布。

用法: python scripts/fix_asset_bboxes.py
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "backend" / "static"


def tight_crop(img: Image.Image, alpha_min: int = 24) -> Image.Image:
    """裁到最大连通域的 bbox (+8px 边距): 角落散点噪斑不该撑大包围盒"""
    from scipy import ndimage
    a = np.asarray(img.convert("RGBA"))
    mask = a[..., 3] > alpha_min
    if not mask.any():
        return img
    lbl, n = ndimage.label(mask)
    if n == 0:
        return img
    sizes = ndimage.sum(mask, lbl, range(1, n + 1))
    main = lbl == (int(np.argmax(sizes)) + 1)
    ys, xs = np.where(main)
    m = 8
    return img.crop((max(0, int(xs.min()) - m), max(0, int(ys.min()) - m),
                     min(img.width, int(xs.max()) + 1 + m), min(img.height, int(ys.max()) + 1 + m)))


def main() -> None:
    import sys
    _root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(_root / "backend"))
    sys.path.insert(0, str(_root))
    from app.services.petgen.pipeline import cutout_dominant_bg
    from scripts.gen_scene_layers import erase_watermark

    # UI 素材: 从 _raw 重切 (水印修补 + 主色抠图 + 紧致裁剪)
    for raw in sorted((ROOT / "ui" / "_raw").glob("*.jpg")):
        img = cutout_dominant_bg(erase_watermark(Image.open(raw)))
        cropped = tight_crop(img)
        out = ROOT / "ui" / f"{raw.stem}.png"
        cropped.save(out)
        print(f"[ui] {raw.stem}: 重切 -> {cropped.size}")
    # 物品图: 裁剪 + 回 256 居中画布
    for p in sorted((ROOT / "items").glob("*.png")):
        img = tight_crop(Image.open(p))
        side = 256
        ratio = (side * 0.85) / max(img.width, img.height)
        img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.LANCZOS)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
        canvas.save(p)
        print(f"[item] {p.name} 重裁剪居中")


if __name__ == "__main__":
    main()
