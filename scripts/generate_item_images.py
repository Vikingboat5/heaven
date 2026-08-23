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


def main() -> None:
    live = "--live" in sys.argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if live:
        # TODO: 生图套餐恢复后在此实跑 Ark 生成 + QC; 当前直接拒绝, 防止误烧钱
        raise SystemExit("live 模式尚未接入 Ark (生图套餐不可用), 请先用占位模式")
    for item in catalog.ITEMS.values():
        path = OUT_DIR / f"{item['id']}.png"
        if path.exists():
            continue  # 幂等: 已有图(如实跑产物)不覆盖
        placeholder(item, path)
        print(f"[item-image] 占位图 {item['id']}")


if __name__ == "__main__":
    main()
