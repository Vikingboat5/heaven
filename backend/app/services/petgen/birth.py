"""诞生形象生成 (S3.3): 外观组装 + IP 转译 + 后台生成任务

流程: 孵化接口仅把 sprite_status 置 pending 并派生后台任务 →
本模块在后台完成 IP 转译(LLM) → 外观组装 → petgen 管线生成 → 回写状态。
任何环节失败 → 素材库兜底 → sprite_status=failed, 前端降级预制 SVG, 主链路不阻塞。

素材库复用 (生图套餐不可用时的临时方案, PETGEN_MODE=reuse):
跳过生图 API, 把 backend/static/pets/_library/ 的帧序列+manifest 复制到新宠物目录。
生图恢复后把 PETGEN_MODE 改回 live 即可。
"""
from __future__ import annotations

import asyncio
import json
import random
import shutil
from pathlib import Path

from ...config import settings
from ...database import SessionLocal
from ...llm.gateway import gateway
from ...models import Egg, Pet
from ..quiz import resolve_color, resolve_style
from .pipeline import PetForge, PetGenError
from .profiles import STYLE_PROFILES

# 生成素材根目录(与 pipeline 的默认输出目录一致)
_PETS_ROOT = Path(__file__).resolve().parents[3] / "static" / "pets"
# 素材库: 复用模式的形象来源(现有已验收宠物的帧序列副本)
_LIBRARY_DIR = _PETS_ROOT / "_library"

# 后台生成的动作集: idle 待机 + wave 招手 + 生活动作三件套 (H6: stretch/groom/doze)
BIRTH_ACTIONS = ("idle", "wave", "stretch", "groom", "doze")

_IP_SYSTEM = (
    "把用户提到的角色名转译为不超过30字的外观特征描述(毛色/体型/标志性元素)。"
    "只输出特征词本身, 不要提角色名和作品名。无法识别就只输出: 无"
)


def reuse_library_assets(pet: Pet, source: Path | None = None) -> None:
    """复用素材库已有形象: 复制帧序列 + manifest 到宠物目录, 状态置 ready。

    manifest 的 pet_id 改写为当前宠物, style 同步到 pet.sprite_style。
    素材库缺失/为空 → 抛 PetGenError(由调用方落到 failed)。
    """
    src = source or _LIBRARY_DIR
    manifest_path = src / "manifest.json"
    frames_dir = src / "frames"
    if not manifest_path.is_file() or not frames_dir.is_dir():
        raise PetGenError("素材库不存在")

    pet_dir = _PETS_ROOT / str(pet.id)
    (pet_dir / "frames").mkdir(parents=True, exist_ok=True)
    for f in frames_dir.glob("*.png"):
        shutil.copy2(f, pet_dir / "frames" / f.name)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pet_id"] = pet.id
    (pet_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    pet.sprite_style = manifest.get("style", "")
    pet.sprite_status = "ready"


async def _transcribe_ip(ip_text: str) -> str:
    """IP 角色名 → 外观特征词 (compact prompt, 失败/无效返回空串)"""
    try:
        result = await gateway.chat(
            [{"role": "system", "content": _IP_SYSTEM},
             {"role": "user", "content": ip_text}],
            tier="lite", pet_id="petgen-ip", max_tokens=64, temperature=0.3,
        )
        text = result.content.strip()
        return "" if text in ("无", "", "无。") else text[:60]
    except Exception:
        return ""  # 转译是增强, 失败静默


def build_appearance(species_name: str, color_desc: str, ip_traits: str = "") -> str:
    """组装外观描述词 (注入精灵表 prompt 的 {外观描述} 段)"""
    parts = [f"一只可爱的{color_desc}色系的{species_name}"]
    parts.append("大眼睛, 蓬松尾巴")
    if ip_traits:
        parts.append(f"带有这些特征: {ip_traits}")
    return ", ".join(parts)


def _seeded_style(hatch_seed: str) -> str:
    """问答选'交给缘分'时由种子决定画风(可复现)"""
    rng = random.Random(f"style:{hatch_seed}")
    return rng.choice(list(STYLE_PROFILES.keys()))


def generate_sprite_task(pet_id: int, session_factory=None) -> None:
    """后台任务入口(自带 DB 会话, 供 BackgroundTasks/线程调用)

    session_factory: 测试注入用; 生产默认 SessionLocal(任务自建自关)
    """
    own_session = session_factory is None
    db = (session_factory or SessionLocal)()
    pet: Pet | None = None
    try:
        pet = db.get(Pet, pet_id)
        if pet is None:
            return
        egg = db.query(Egg).filter(Egg.hatch_seed == pet.hatch_seed).first()
        answers = (egg.quiz_answers if egg else None) or {}

        # 生图套餐不可用: 直接复用素材库已有形象, 跳过 IP 转译与生图 API
        if settings.petgen_mode == "reuse":
            reuse_library_assets(pet)
            return

        ip_traits = ""
        if answers.get("ip"):
            ip_traits = asyncio.run(_transcribe_ip(answers["ip"]))

        appearance = build_appearance(pet.species, resolve_color(answers), ip_traits)
        style = resolve_style(answers) or _seeded_style(pet.hatch_seed)
        pet.appearance = appearance
        pet.sprite_style = style
        db.commit()

        PetForge().generate(pet.id, appearance, style, BIRTH_ACTIONS)
        pet.sprite_status = "ready"
    except PetGenError:
        if pet is not None:
            try:
                reuse_library_assets(pet)  # 生图失败 → 兜底复用已有素材
            except PetGenError:
                pet.sprite_status = "failed"
    except Exception:
        if pet is not None:
            pet.sprite_status = "failed"
    finally:
        try:
            db.commit()
        except Exception:
            db.rollback()
        if own_session:
            db.close()
