"""idle 序列剔除第 0 帧 (首帧=参考图风格,与视频主体风格不一致,循环里闪一次)"""
import json
from pathlib import Path

mpath = Path(__file__).resolve().parents[1] / "backend" / "static" / "pets" / "28" / "manifest.json"
m = json.loads(mpath.read_text(encoding="utf-8"))
# [1..23] + [22..1]: 绕开第 0 帧, ping-pong 保持
m["actions"]["idle"]["sequence"] = list(range(1, 24)) + list(range(22, 0, -1))
mpath.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
print("idle 序列已剔除第 0 帧:", m["actions"]["idle"]["sequence"][:6], "...")
