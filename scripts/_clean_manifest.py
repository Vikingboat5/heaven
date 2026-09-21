"""清理 manifest: 移除被视频版取代的旧动作 (wandering video_idle + 水彩 stretch/groom/doze)
保留 idle/wave/petted (全部视频源, ping-pong 序列)"""
import json
from pathlib import Path

mpath = Path(__file__).resolve().parents[1] / "backend" / "static" / "pets" / "28" / "manifest.json"
m = json.loads(mpath.read_text(encoding="utf-8"))
removed = []
for a in ("video_idle", "stretch", "groom", "doze"):
    if m["actions"].pop(a, None) is not None:
        removed.append(a)
    m.get("qc", {}).pop(a, None)
mpath.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"移除: {removed}, 保留: {list(m['actions'].keys())}")
