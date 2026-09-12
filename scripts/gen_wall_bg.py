"""明信片墙梦幻背景生成 (规范 v1.3.1): 与主页同画风的竖幅夜空, 供挂绳页整幅铺底
产物: backend/static/scenes/wall_dream/bg.jpg (完整图, 不抠图)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.petgen.pipeline import ArkImageClient, download  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "backend" / "static" / "scenes" / "wall_dream"
OUT.mkdir(parents=True, exist_ok=True)

prompt = (
    "竖幅梦幻夜空场景插画: 深紫蓝色夜空, 一条淡淡的银河斜挂, 大大小小的星星闪烁, "
    "右上角一弯温柔的月牙带银辉, 几朵薄云, 远处山谷有几粒温暖的灯火, 底部淡淡的远山轮廓, "
    "大量留白的中上部空间, 手绘童话插画风, 水彩质感, 无文字无边框无网格线"
)

print("生成梦幻背景...", flush=True)
url = ArkImageClient().generate_image(prompt, size="2048x2048")
download(url, OUT / "bg.jpg")
print(f"完成: {OUT / 'bg.jpg'}")
