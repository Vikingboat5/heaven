"""AtlasCloud 视频客户端 (seedance-2.0-mini/image-to-video)

管道 S3 的正式实现 (替代方舟控制台手工步骤):
- 首尾帧直接传 base64 data URI (无需公网 URL)
- 提交 → 轮询 → 下载 mp4
- 时长档位 4-15s (AtlasCloud 下限 4s, 覆盖 spec §6 的 3s 精简结论)
"""
from __future__ import annotations

import base64
import json
import time
import urllib.request
from pathlib import Path

from ...config import settings  # type: ignore  # 脚本直接调用时由调用方保证 path

BASE = "https://api.atlascloud.ai/api/v1"
MODEL = "bytedance/seedance-2.0-mini/image-to-video"


class AtlasVideoError(Exception):
    pass


def _key() -> str:
    key = getattr(settings, "atlascloud_api_key", "")
    if not key:
        raise AtlasVideoError("backend/.env 缺 ATLASCLOUD_API_KEY (从 https://console.atlascloud.ai 获取)")
    return key


def _api(method: str, path: str, payload: dict | None = None, retries: int = 2) -> dict:
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            f"{BASE}{path}",
            data=json.dumps(payload).encode() if payload else None,
            headers={
                "Authorization": f"Bearer {_key()}",
                "Content-Type": "application/json",
                # Cloudflare 1010 反爬: 裸 urllib 会被拦, 需要正常 UA
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) petparadise-pipeline/1.0",
                "Accept": "application/json",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise AtlasVideoError(f"{e.code}: {e.read().decode(errors='replace')[:300]}")
        except Exception as e:  # 网络抖动/SSL EOF: 重试
            last = e
            time.sleep(3 * (attempt + 1))
    raise AtlasVideoError(f"网络错误(重试{retries}次): {last}")


def _to_data_uri(png_path: Path) -> str:
    """PNG(带透明) → 白底铺平 → 缩到 768px → base64 data URI
    (原尺寸 2048 的 base64 有 ~4MB, 单 POST 会 SSL EOF; 480p 视频 768 引导图绰绰有余)"""
    from PIL import Image
    img = Image.open(png_path).convert("RGBA")
    if max(img.size) > 768:
        ratio = 768 / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, (0, 0), img)
    import io
    buf = io.BytesIO()
    bg.save(buf, format="JPEG", quality=88)  # JPEG 更小 (无透明需求了)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def generate_video(first_frame: Path, last_frame: Path | None, prompt: str,
                   out_mp4: Path, duration: int = 4, poll_s: int = 3, timeout_s: int = 600) -> Path:
    """首尾帧图生视频: 提交 → 轮询 → 下载, 返回 mp4 路径"""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "image": _to_data_uri(first_frame),
        "duration": duration,          # AtlasCloud 档位 4-15s
        "resolution": "480p",          # 我们最终只要 512px, 480p 够用且省
        "ratio": "adaptive",
        "bitrate_mode": "standard",
        "generate_audio": False,
        "watermark": False,
        "return_last_frame": False,
    }
    if last_frame is not None and last_frame.exists():
        payload["last_image"] = _to_data_uri(last_frame)

    result = _api("POST", "/model/generateVideo", payload)
    pred_id = result["data"]["id"]
    print(f"[atlas] 任务 {pred_id} 已提交, 生成中...", flush=True)

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(poll_s)
        st = _api("GET", f"/model/prediction/{pred_id}")
        status = st["data"]["status"]
        if status in ("completed", "succeeded"):
            url = st["data"]["outputs"][0]
            urllib.request.urlretrieve(url, out_mp4)
            print(f"[atlas] 出片: {out_mp4.name} ({out_mp4.stat().st_size // 1024}KB)", flush=True)
            return out_mp4
        if status == "failed":
            raise AtlasVideoError(f"生成失败: {st['data'].get('error')}")
    raise AtlasVideoError(f"超时 {timeout_s}s 未出片")
