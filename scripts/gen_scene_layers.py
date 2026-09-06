"""场景图层生成实验 (规范 §3.3): 分层 AI 生图 + 白底抠图 + 宠物锚点合成目检

生成家园夜景两层 (抠图后带 alpha):
  layer_far.png    —— 远景: 远山+孤独的树+山谷灯火 (深蓝紫剪影, 白底)
  layer_ground.png —— 地面: 草地+巢, 中央偏左留平坦空地(宠物锚点)
并合成预览 composite.png = 夜空底 + 远景 + 地面 + 宠物帧(锚点处), 供目检。

用法: python scripts/gen_scene_layers.py [--pet-id 28] [--reprocess]
  --reprocess  不重新生图, 用已落盘 raw_*.jpg 离线重切(含水印修补)
产物: backend/static/scenes/home_night/{layer_far.png,layer_ground.png,composite.png,raw_*.jpg,params.json}
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from app.services.petgen.pipeline import ArkImageClient, cutout_white_bg, download  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "backend" / "static" / "scenes" / "home_night"
BG_NIGHT = (21, 12, 46)

# 宠物锚点 (相对场景宽高的百分比): 中央偏左的平坦空地
ANCHOR_X, ANCHOR_Y = 0.44, 0.72
PET_SCALE = 0.30   # 宠物帧高占场景高比例

# Ark 生图右下角固定带 "AI生成" 水印 (2048 图约 660x110), 用左侧同源草地修补
# (生产上线若对外分发需注意 AI 内容标识合规; 本机开发预览先行去除)
WATERMARK_RECT = (1560, 1880, 2020, 2010)  # (x0, y0, x1, y1) on 2048x2048
WATERMARK_PATCH_OFFSET = -700              # 从该 x 偏移处取干净补丁


def erase_watermark(img: Image.Image) -> Image.Image:
    """用左移 W 像素的同源区域覆盖右下角水印"""
    img = img.convert("RGB")
    x0, y0, x1, y1 = WATERMARK_RECT
    if img.width < x1 or img.height < y1:
        return img
    patch = img.crop((x0 + WATERMARK_PATCH_OFFSET, y0,
                      x1 + WATERMARK_PATCH_OFFSET, y1))
    img.paste(patch, (x0, y0))
    return img

PROMPTS = {
    "far": (
        "手绘童话插画风横版场景素材, 深蓝紫色空气透视的三层远山剪影, 右侧一棵孤独的大树剪影, "
        "山谷间几点温暖的橙黄色灯火, 山脚有淡淡的雾, 地平线横贯画面下方三分之一处, "
        "纯白色背景, 无天空无星星无月亮, 无文字无边框, 画面底部三分之一留白"
    ),
    "ground": (
        "手绘童话插画风横版场景素材, 一片柔软的深紫绿色草地地面, 草地上有一个干草编成的小圆巢, "
        "中央偏左留有一片平坦的空草地(什么都不要放), 几丛小草和零星的萤火虫光点, "
        "纯白色背景, 无天空, 无文字无边框, 草地只占画面下半部分, 上半部分纯白"
    ),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pet-id", type=int, default=28)
    ap.add_argument("--reprocess", action="store_true", help="离线重切(不重新生图)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    params = {}

    if args.reprocess:
        for key in PROMPTS:
            raw = OUT / f"raw_{key}.jpg"
            if not raw.exists():
                raise SystemExit(f"缺原始图 {raw}, 先正常生成一次")
            layer = cutout_white_bg(erase_watermark(Image.open(raw)))
            bbox = layer.getchannel("A").getbbox()
            if bbox:
                layer = layer.crop(bbox)  # 裁到内容包围盒, CSS bottom:0 对齐 = 合成图对齐
            layer.save(OUT / f"layer_{key}.png")
            print(f"[{key}] 离线重切完成", flush=True)
    else:
        client = ArkImageClient()
        for key, prompt in PROMPTS.items():
            print(f"[{key}] 生成中...", flush=True)
            url = client.generate_image(prompt, size="2048x2048")
            raw = OUT / f"raw_{key}.jpg"
            download(url, raw)
            layer = cutout_white_bg(erase_watermark(Image.open(raw)))
            bbox = layer.getchannel("A").getbbox()
            if bbox:
                layer = layer.crop(bbox)
            layer.save(OUT / f"layer_{key}.png")
            params[key] = {"prompt": prompt, "size": "2048x2048"}
            print(f"[{key}] 抠图完成 → layer_{key}.png", flush=True)

    # ---- 合成目检图: 夜空底 + 远景 + 地面 + 宠物锚点 ----
    W = H = 1024
    canvas = Image.new("RGB", (W, H), BG_NIGHT)
    for key in ("far", "ground"):
        layer = Image.open(OUT / f"layer_{key}.png").convert("RGBA")
        bbox = layer.getchannel("A").getbbox()
        if bbox:
            layer = layer.crop(bbox)
        # 图层铺到画布底部对齐, 宽铺满
        ratio = W / layer.width
        layer = layer.resize((W, int(layer.height * ratio)), Image.LANCZOS)
        canvas.paste(layer, (0, H - layer.height), layer)

    pet_frame = Path(__file__).resolve().parents[1] / "backend" / "static" / "pets" / str(args.pet_id) / "frames" / "idle_0.png"
    pet = Image.open(pet_frame).convert("RGBA")
    ph = int(H * PET_SCALE)
    pw = int(pet.width * (ph / pet.height))
    pet = pet.resize((pw, ph), Image.LANCZOS)
    px = int(W * ANCHOR_X - pw / 2)
    py = int(H * ANCHOR_Y - ph)
    canvas.paste(pet, (px, py), pet)
    canvas.save(OUT / "composite.png")

    params["anchor"] = {"x": ANCHOR_X, "y": ANCHOR_Y, "pet_scale": PET_SCALE}
    (OUT / "params.json").write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n合成目检图: {OUT / 'composite.png'}")
    print(f"锚点: x={ANCHOR_X:.0%} y={ANCHOR_Y:.0%} (宠物脚底), 宠物高={PET_SCALE:.0%}场景高")


if __name__ == "__main__":
    main()
