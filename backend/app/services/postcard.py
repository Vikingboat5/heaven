"""明信片 (H8): 宠物首次到达某地 → 打卡照生成

一致性方案 (2026-09-06 探针实测拍板): i2i, 参考图 = 宠物 idle_0 帧的 base64 data URL
(Plan 端点支持 data URL, scripts/probe_postcard_i2i.py 验证)。
明信片是完整场景插画, 不抠图。异步后台生成, 不阻塞结算/信件。
"""
from __future__ import annotations

import base64
import threading
from pathlib import Path

from ..database import SessionLocal
from ..models import AdventureLog, Pet
from ..services.petgen.pipeline import ArkImageClient, download

_POSTCARD_ROOT = Path(__file__).resolve().parents[2] / "static" / "postcards"
_PETS_ROOT = Path(__file__).resolve().parents[2] / "static" / "pets"

STYLE = "手绘童话插画风, 暖色调, 水彩质感"


def is_first_visit(db, pet_id: int, seed_id: str) -> bool:
    """该宠物此前没有到访过这个种子 (按日志 rewards.seed 判定)"""
    rows = db.query(AdventureLog).filter(AdventureLog.pet_id == pet_id).all()
    return not any((r.rewards or {}).get("seed") == seed_id for r in rows)


def _generate(log_id: int, pet_id: int) -> None:
    """后台线程: 生成打卡照并回写日志。失败只留痕, 不影响主链路"""
    db = SessionLocal()
    try:
        log = db.get(AdventureLog, log_id)
        pet = db.get(Pet, pet_id)
        if log is None or pet is None:
            return
        seed_id = (log.rewards or {}).get("seed", "")
        from ..core import catalog
        seed_def = catalog.SEEDS.get(seed_id, {})
        background = seed_def.get("background", seed_def.get("name", "远方"))
        appearance = pet.appearance or f"一只可爱的{pet.color}色系的{pet.species}"

        frame = _PETS_ROOT / str(pet_id) / "frames" / "idle_0.png"
        reference = None
        if frame.is_file():
            reference = "data:image/png;base64," + base64.b64encode(frame.read_bytes()).decode()

        prompt = (
            f"一张旅行明信片插画: 参考图中的这只小家伙({appearance})在{background}开心地坐着打卡, "
            f"{STYLE}, 明信片式构图, 无文字"
        )
        url = ArkImageClient().generate_image(prompt, size="2048x2048", reference_url=reference)
        _POSTCARD_ROOT.mkdir(parents=True, exist_ok=True)
        out = _POSTCARD_ROOT / f"log_{log_id}.jpg"
        download(url, out)
        rewards = dict(log.rewards or {})
        rewards.pop("postcard_pending", None)
        rewards["postcard"] = f"/static/postcards/log_{log_id}.jpg"
        log.rewards = rewards
        db.commit()
        print(f"[postcard] log#{log_id} 明信片已生成")
    except Exception as e:
        print(f"[postcard] log#{log_id} 明信片生成失败: {e}")  # 兜底留痕
    finally:
        db.close()


def dispatch_postcard(log_id: int, pet_id: int) -> None:
    """结算时调用: 异步生成, 立即返回"""
    threading.Thread(target=_generate, args=(log_id, pet_id), daemon=True).start()
