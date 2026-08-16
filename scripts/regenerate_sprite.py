"""手动重跑宠物形象生成任务 (开发环境用)

场景: 后端旧代码孵化导致 sprite_status=failed/pending, 或想换模式重新生成。
在 backend 目录下运行: python ..\scripts\regenerate_sprite.py <pet_id>
按当前 .env 的 PETGEN_MODE 执行 (reuse=复用素材库, live=真实生图)。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.petgen.birth import generate_sprite_task  # noqa: E402

if len(sys.argv) != 2:
    print("用法: python scripts/regenerate_sprite.py <pet_id>")
    sys.exit(1)

pet_id = int(sys.argv[1])
print(f"为宠物 #{pet_id} 重跑形象生成任务...")
generate_sprite_task(pet_id)
print("完成。刷新前端页面即可看到最新状态。")
