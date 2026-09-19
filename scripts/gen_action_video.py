"""动作视频一键生成+采收 (动画管道 S3+S4, AtlasCloud 版)

对 _anim_pending/ 里每个已备好首尾帧的动作:
  AtlasCloud 提交(首帧+尾帧 base64) → 轮询 → 下载 mp4 → video_to_frames 采帧入库
用法: python scripts/gen_action_video.py <pet_id> [action]   # 默认处理全部 pending 动作
前置: backend/.env 里 ATLASCLOUD_API_KEY=<从 console.atlascloud.ai 获取>
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.services.petgen.atlas_video import generate_video  # noqa: E402
from video_to_frames import cut_video  # noqa: E402


def main() -> None:
    pet_id = int(sys.argv[1])
    only = sys.argv[2] if len(sys.argv) > 2 else None
    pending = ROOT / "backend" / "static" / "pets" / str(pet_id) / "_anim_pending"
    if not pending.is_dir():
        raise SystemExit(f"没有待生成目录: {pending} (先跑 gen_animation_frames.py)")

    actions = [only] if only else sorted({p.name.rsplit("_", 1)[0] for p in pending.glob("*_first.png")})
    if not actions:
        raise SystemExit("没有待生成的动作 (缺 *_first.png)")

    for action in actions:
        first = pending / f"{action}_first.png"
        last = pending / f"{action}_last.png"
        prompt_file = pending / f"{action}.txt"
        if not first.exists():
            print(f"跳过 {action}: 缺首帧")
            continue
        prompt = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else "smooth gentle loopable motion, pure white background"
        mp4 = pending / f"{action}.mp4"
        print(f"[{action}] 生成视频...", flush=True)
        generate_video(first, last if last.exists() else None, prompt, mp4)
        print(f"[{action}] 采帧入库...", flush=True)
        cut_video(pet_id, action, mp4)
        print(f"[{action}] 完成", flush=True)

    print("全部动作处理完毕")


if __name__ == "__main__":
    main()
