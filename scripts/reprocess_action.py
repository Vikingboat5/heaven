"""离线重跑某动作的后处理 (零 token): 用落盘的原始图+参数重切帧
用法: python scripts/reprocess_action.py <pet_id> <action>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.petgen.pipeline import PetForge  # noqa: E402

if len(sys.argv) != 3:
    print("用法: python scripts/reprocess_action.py <pet_id> <action>")
    sys.exit(1)

qc = PetForge().reprocess(int(sys.argv[1]), sys.argv[2])
print("QC:", "passed" if qc["passed"] else f"未过: {qc}")
