"""wave/petted 序列剔除第 0 帧 (同 idle: 首帧=参考图风格, 更白更亮会闪)"""
import json
from pathlib import Path

mpath = Path(__file__).resolve().parents[1] / "backend" / "static" / "pets" / "28" / "manifest.json"
m = json.loads(mpath.read_text(encoding="utf-8"))
for action in ("wave", "petted"):
    n = m["actions"][action]["frames"]
    m["actions"][action]["sequence"] = list(range(1, n)) + list(range(n - 2, 0, -1))
mpath.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
print("wave/petted 序列已剔除第 0 帧")
