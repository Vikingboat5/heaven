"""重跑某宠物的单个动作并合并 manifest (开发环境用)

场景: 某动作 QC 过了但目检有瑕疵(格线残留/构图异常), 不想整只宠物全部重生成。
用法: python scripts/regenerate_action.py <pet_id> <action> [<action>...]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.database import SessionLocal  # noqa: E402
from app.models import Pet  # noqa: E402
from app.services.petgen.pipeline import PetForge  # noqa: E402

if len(sys.argv) < 3:
    print("用法: python scripts/regenerate_action.py <pet_id> <action> [<action>...]")
    sys.exit(1)

pet_id = int(sys.argv[1])
actions = tuple(sys.argv[2:])

db = SessionLocal()
try:
    pet = db.get(Pet, pet_id)
    assert pet, f"宠物 {pet_id} 不存在"
    assert pet.appearance and pet.sprite_style, "宠物缺 appearance/style, 先完整重生成"

    forge = PetForge()
    manifest_path = Path(forge.out_root) / str(pet_id) / "manifest.json"
    # generate() 会整体覆盖 manifest, 先备份完整版
    base = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None

    print(f"重生成宠物 #{pet_id} 的动作: {', '.join(actions)}", flush=True)
    partial = forge.generate(pet_id, pet.appearance, pet.sprite_style, actions)

    # 合并: 本次动作的 actions/qc 覆盖进完整 manifest
    full = base or {"pet_id": pet_id, "style": pet.sprite_style,
                    "prompt_version": partial["prompt_version"], "actions": {}, "qc": {}}
    full["actions"].update(partial["actions"])
    full["qc"].update(partial["qc"])
    manifest_path.write_text(json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")
    print("完成, manifest 已合并")
finally:
    db.close()
