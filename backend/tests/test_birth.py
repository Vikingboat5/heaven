"""S3.3 诞生形象生成测试: 外观组装 / 后台任务状态机 / 降级 / 素材库复用"""
import json

import pytest

from backend.app import models
from backend.app.config import settings
from backend.app.services.petgen import birth
from backend.app.services.petgen.pipeline import PetGenError


def _pet_with_egg(db, answers=None):
    u = models.User(username="birther", password_hash="x")
    db.add(u)
    db.flush()
    egg = models.Egg(owner_id=u.id, hatch_seed="seed-abc",
                     status="hatched", quiz_answers=answers or {})
    db.add(egg)
    pet = models.Pet(
        owner_id=u.id, name="团团", species="小狐狸", color="暖棕",
        personality={}, talents=[], skills=[],
        hatch_seed="seed-abc", sprite_status="pending",
    )
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


def test_build_appearance():
    s = birth.build_appearance("小狐狸", "薄荷绿", "黄色电气老鼠, 闪电尾巴")
    assert "薄荷绿" in s and "小狐狸" in s and "闪电尾巴" in s
    # 无 IP 特征时不含特征段
    assert "特征" not in birth.build_appearance("垂耳兔", "暖橙")


def test_sprite_task_success(db, monkeypatch):
    pet = _pet_with_egg(db, {"style": "pixel", "color": "green", "ip": "皮卡丘"})
    called = {}

    class FakeForge:
        def generate(self, pet_id, appearance, style, actions):
            called.update(pet_id=pet_id, appearance=appearance,
                          style=style, actions=actions)
            return {"actions": {}}

    async def fake_transcribe(text):
        return "黄色圆胖小家伙, 闪电形尾巴"

    monkeypatch.setattr(birth, "PetForge", lambda: FakeForge())
    monkeypatch.setattr(birth, "_transcribe_ip", fake_transcribe)

    birth.generate_sprite_task(pet.id, session_factory=lambda: db)
    db.refresh(pet)
    assert pet.sprite_status == "ready"
    assert pet.sprite_style == "pixel"
    assert called["style"] == "pixel"
    assert called["actions"] == ("idle", "wave")
    assert "翠绿" in called["appearance"]          # 快捷色系映射
    assert "闪电形尾巴" in called["appearance"]    # IP 转译注入


def _make_library(tmp_path):
    """构造临时素材库: 2 帧 + manifest(pixel 风格)"""
    lib = tmp_path / "lib"
    (lib / "frames").mkdir(parents=True)
    (lib / "frames" / "idle_0.png").write_bytes(b"png0")
    (lib / "frames" / "idle_1.png").write_bytes(b"png1")
    (lib / "manifest.json").write_text(json.dumps({
        "pet_id": 6, "style": "pixel",
        "actions": {"idle": {"frames": 8, "sequence": [0, 1], "frame_ms": 130}},
    }), encoding="utf-8")
    return lib


def test_sprite_task_failure_degrades(db, monkeypatch, tmp_path):
    pet = _pet_with_egg(db, {"style": "illustration"})

    class FailForge:
        def generate(self, *a, **kw):
            raise PetGenError("质检失败")

    monkeypatch.setattr(birth, "PetForge", lambda: FailForge())
    monkeypatch.setattr(birth, "_LIBRARY_DIR", tmp_path / "no-library")  # 素材库缺失
    monkeypatch.setattr(birth, "_PETS_ROOT", tmp_path / "pets")
    birth.generate_sprite_task(pet.id, session_factory=lambda: db)
    db.refresh(pet)
    assert pet.sprite_status == "failed"  # 无素材库可用 → 落 failed, 前端降级预制 SVG


def test_sprite_task_failure_reuses_library(db, monkeypatch, tmp_path):
    """生图失败但素材库可用 → 兜底复用素材库形象"""
    pet = _pet_with_egg(db, {"style": "illustration"})

    class FailForge:
        def generate(self, *a, **kw):
            raise PetGenError("质检失败")

    monkeypatch.setattr(birth, "PetForge", lambda: FailForge())
    monkeypatch.setattr(birth, "_LIBRARY_DIR", _make_library(tmp_path))
    out = tmp_path / "pets"
    monkeypatch.setattr(birth, "_PETS_ROOT", out)

    birth.generate_sprite_task(pet.id, session_factory=lambda: db)
    db.refresh(pet)
    assert pet.sprite_status == "ready"
    assert pet.sprite_style == "pixel"          # 画风随素材库 manifest
    assert (out / str(pet.id) / "frames" / "idle_0.png").exists()
    manifest = json.loads((out / str(pet.id) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["pet_id"] == pet.id         # manifest 的 pet_id 改写为新宠物


def test_reuse_mode_skips_generation(db, monkeypatch, tmp_path):
    """PETGEN_MODE=reuse: 不调用生图 API/IP 转译, 直接复用素材库"""
    pet = _pet_with_egg(db, {"style": "illustration", "ip": "皮卡丘"})

    class BoomForge:
        def generate(self, *a, **kw):
            raise AssertionError("reuse 模式不应调用生图管线")

    async def boom_transcribe(text):
        raise AssertionError("reuse 模式不应调用 IP 转译")

    monkeypatch.setattr(birth, "PetForge", lambda: BoomForge())
    monkeypatch.setattr(birth, "_transcribe_ip", boom_transcribe)
    monkeypatch.setattr(birth, "_LIBRARY_DIR", _make_library(tmp_path))
    monkeypatch.setattr(birth, "_PETS_ROOT", tmp_path / "pets")

    settings.petgen_mode = "reuse"
    try:
        birth.generate_sprite_task(pet.id, session_factory=lambda: db)
    finally:
        settings.petgen_mode = "live"
    db.refresh(pet)
    assert pet.sprite_status == "ready"
    assert pet.sprite_style == "pixel"
    assert (tmp_path / "pets" / str(pet.id) / "frames" / "idle_1.png").exists()


def test_sprite_task_seeded_style_when_fate(db, monkeypatch):
    pet = _pet_with_egg(db, {})  # 无问答 → 种子决定画风
    seen = {}

    class FakeForge:
        def generate(self, pet_id, appearance, style, actions):
            seen["style"] = style
            return {}

    monkeypatch.setattr(birth, "PetForge", lambda: FakeForge())
    birth.generate_sprite_task(pet.id, session_factory=lambda: db)
    db.refresh(pet)
    assert pet.sprite_status == "ready"
    assert seen["style"] in ("illustration", "pixel")
    # 同种子可复现
    assert birth._seeded_style("seed-abc") == birth._seeded_style("seed-abc")


def test_hatch_sets_pending_and_out_fields(api_client, db, noop_sprite_task):
    token = api_client.post("/api/auth/register",
                            json={"username": "hatchsprite", "password": "pass123"}).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    egg = db.query(models.Egg).filter(models.Egg.owner_id == 1).first()
    egg.hatch_value = 100
    db.commit()
    pet = api_client.post("/api/eggs/hatch", json={}, headers=auth).json()
    # 孵化即进入 pending(后台任务测试环境不执行); 输出包含形象字段
    assert pet["sprite_status"] == "pending"
    assert "sprite_style" in pet
