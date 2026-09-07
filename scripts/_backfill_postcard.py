"""给探探补记一张月宫明信片 (补历史账: 明信片机制上线前的旅行没有打卡照)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.postcard import _generate  # noqa: E402

_generate(70, 28)
print("补记完成")
