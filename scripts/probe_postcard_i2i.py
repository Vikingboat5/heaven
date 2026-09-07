"""明信片技术验证: i2i 参考图是否支持 base64 data URL (决定打卡照的角色一致性方案)
顺带验证: 纯文本外观词方案的兜底效果对照
产物: backend/static/postcards/_probe_*.jpg
"""
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.petgen.pipeline import ArkImageClient, download  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "backend" / "static" / "postcards"
OUT.mkdir(parents=True, exist_ok=True)

pet_frame = Path(__file__).resolve().parents[1] / "backend" / "static" / "pets" / "28" / "frames" / "idle_0.png"
ref_data_url = "data:image/png;base64," + base64.b64encode(pet_frame.read_bytes()).decode()
print(f"参考图 data URL 长度: {len(ref_data_url) // 1024}KB", flush=True)

client = ArkImageClient()
prompt = (
    "一张旅行明信片插画: 参考图中的这只小狐狸坐在银白色的云端宫殿前的玉石阶上, 背景有桂树和大月亮, "
    "手绘童话插画风, 暖色调, 水彩质感, 明信片式构图, 无文字"
)

# 方案 A: data URL 作参考图 (角色一致性最强)
try:
    url = client.generate_image(prompt, size="2048x2048", reference_url=ref_data_url)
    download(url, OUT / "_probe_i2i.jpg")
    print("方案A (i2i data URL): 成功", flush=True)
except Exception as e:
    print(f"方案A 失败: {e}", flush=True)

# 方案 B: 纯文本外观词 (兜底)
try:
    prompt_b = (
        "一张旅行明信片插画: 一只可爱的暖橙色系的小狐狸, 大眼睛, 蓬松尾巴, "
        "坐在银白色的云端宫殿前的玉石阶上, 背景有桂树和大月亮, "
        "手绘童话插画风, 暖色调, 水彩质感, 明信片式构图, 无文字"
    )
    url = client.generate_image(prompt_b, size="2048x2048")
    download(url, OUT / "_probe_text.jpg")
    print("方案B (纯文本): 成功", flush=True)
except Exception as e:
    print(f"方案B 失败: {e}", flush=True)
