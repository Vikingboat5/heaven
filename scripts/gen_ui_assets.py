"""UI 素材生成 (规范 §3.3 延伸): 主页木牌/图标/便签全部换 AI 手绘素材, 与场景同一画风

产物: backend/static/ui/{name}.png (带 alpha) + _raw/ 原始图可离线重切
用法: python scripts/gen_ui_assets.py [--only name1,name2] [--force]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from PIL import Image  # noqa: E402

from app.services.petgen.pipeline import ArkImageClient, cutout_dominant_bg, download  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "backend" / "static" / "ui"
STYLE = "手绘童话插画风, 暖色调, 柔和线条, 水彩质感"

ASSETS = {
    # 木牌底: 按钮/信息牌共用 (横版; 无孔无绳 —— 孔洞会让上面的文字透底)
    "wood_plaque": f"一块圆角木牌匾, 温润的蜂蜜色木纹, 完整无孔洞无绳结, {STYLE}, 居中, 纯白色背景, 无阴影无发光, 无文字",
    # 图标 (放木牌上)
    "icon_pack": f"一个小小的帆布旅行背包, 系着背带, {STYLE}, 居中, 纯白色背景, 无阴影无发光, 无文字",
    "icon_basket": f"一个装满星星和卡片的藤编小篮子, {STYLE}, 居中, 纯白色背景, 无阴影无发光, 无文字",
    "icon_letter": f"一个奶白色信封, 封口有火漆印, 一角露出信纸, {STYLE}, 居中, 纯白色背景, 无阴影无发光, 无文字",
    # 便签纸底 (归来信用)
    "paper_note": f"一张微微泛黄的方形便签纸, 边缘轻微卷起, 顶部一枚红色圆图钉, {STYLE}, 居中, 纯白色背景, 无阴影无发光, 无文字",
    # 返回箭头木牌 (内容页返回键)
    "icon_back": f"一块小木牌上刻着向左的箭头, {STYLE}, 居中, 纯白色背景, 无阴影无发光",
}


def gen(name: str, prompt: str, force: bool) -> None:
    path = OUT / f"{name}.png"
    if path.exists() and not force:
        print(f"[ui] 跳过已有 {name}", flush=True)
        return
    client = ArkImageClient()
    url = client.generate_image(prompt, size="2048x2048")
    raw = OUT / "_raw" / f"{name}.jpg"
    raw.parent.mkdir(parents=True, exist_ok=True)
    download(url, raw)
    img = cutout_dominant_bg(Image.open(raw))
    bbox = img.getchannel("A").getbbox()
    if bbox:
        img = img.crop(bbox)
    img.save(path)
    (OUT / "_raw" / f"{name}.prompt.json").write_text(
        json.dumps({"name": name, "prompt": prompt}, ensure_ascii=False), encoding="utf-8")
    print(f"[ui] 生成 {name}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(args.only.split(",")) if args.only else set(ASSETS)
    for name, prompt in ASSETS.items():
        if name in only:
            gen(name, prompt, args.force)


if __name__ == "__main__":
    main()
