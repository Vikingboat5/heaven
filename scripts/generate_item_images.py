"""物品图标生成脚本 (spec §5.3: 预生成, 不走运行时)

用法:
  python scripts/generate_item_images.py              # 占位模式: Pillow 画占位图(纯本地)
  python scripts/generate_item_images.py --live       # 实跑模式: Ark 生图(需生图套餐可用)

实跑模式 prompt 模板: "单个游戏道具图标, {appearance}, 居中, 纯白色背景无阴影"
TODO(live): 接 Ark 端点 + 复用 petgen 白底抠图/QC (套餐恢复后实跑, 参考 services/petgen/pipeline.py)
占位图只是权宜: 图鉴有图可显示, live 实跑后同名覆盖即可。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.core import catalog

OUT_DIR = Path(__file__).resolve().parents[1] / "backend" / "static" / "items"

# 品级 → 占位底色
_RARITY_COLORS = {"common": (200, 200, 210), "rare": (120, 170, 255), "epic": (230, 180, 80)}


def placeholder(item: dict, path: Path) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = _RARITY_COLORS.get(item["rarity"], (200, 200, 210))
    d.rounded_rectangle([16, 16, 240, 240], radius=40, fill=color + (255,))
    # 物品名首字 (默认字体不支持中文时退化为品级首字母, 不阻塞生成)
    label = item["name"][0]
    try:
        d.text((128, 128), label, fill=(40, 30, 60, 255), anchor="mm")
    except Exception as e:
        print(f"[item-image] 文字绘制降级 {item['id']}: {e}")
        d.text((128, 128), item["rarity"][0].upper(), fill=(40, 30, 60, 255), anchor="mm")
    img.save(path)


def generate_live(item: dict, path: Path) -> None:
    """实跑: Ark 生图 + 白底抠图 (复用 petgen 工艺)。原始图落盘支持离线重切"""
    import json as _json

    from PIL import Image

    from backend.app.services.petgen.pipeline import (
        ArkImageClient,
        cutout_white_bg,
        download,
    )

    raw_dir = OUT_DIR / "_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    client = ArkImageClient()
    prompt = (
        f"单个游戏道具图标, {item['appearance']}, 居中, 手绘童话插画风, 暖色调, "
        "纯白色背景, 无阴影, 无文字, 无边框"
    )
    url = client.generate_image(prompt, size="2048x2048")  # 该端点只认 2048x2048 (1024 实测 400)
    raw = raw_dir / f"{item['id']}.jpg"
    download(url, raw)
    img = cutout_white_bg(Image.open(raw))
    bbox = img.getchannel("A").getbbox()
    if bbox:
        img = img.crop(bbox)
    # 统一 256 边长居中
    side = 256
    ratio = (side * 0.85) / max(img.width, img.height)
    img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.LANCZOS)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    canvas.save(path)
    (raw_dir / f"{item['id']}.prompt.json").write_text(
        _json.dumps({"item": item["id"], "prompt": prompt}, ensure_ascii=False), encoding="utf-8")
    print(f"[item-image] 实跑生成 {item['id']}")


def main() -> None:
    live = "--live" in sys.argv
    force = "--force" in sys.argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for item in catalog.ITEMS.values():
        path = OUT_DIR / f"{item['id']}.png"
        if path.exists() and not force:
            continue  # 幂等: 已有图(如实跑产物)不覆盖; --force 可重跑覆盖占位图
        if live:
            generate_live(item, path)
        else:
            placeholder(item, path)
            print(f"[item-image] 占位图 {item['id']}")


if __name__ == "__main__":
    main()
