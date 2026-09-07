"""同步重跑 log#71 的明信片生成, 直接看报错"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.postcard import _generate  # noqa: E402

_generate(71, 29)
print("同步执行完毕")
