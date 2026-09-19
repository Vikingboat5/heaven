"""动作首尾帧自动生成 (动画管道 S2, pet-animation-pipeline-spec §2)

宠物诞生后调用: 按物种路由动作设计表 → 每个标配动作用 i2i 生成首帧+尾帧
→ 存 _anim_pending/{action}_first.png / {action}_last.png / {action}.txt (视频 prompt)
→ 人工(或未来 API)用首尾帧生成视频 → video_to_frames.py 采收

用法: python scripts/gen_animation_frames.py <pet_id> [--actions idle,wave]
"""
import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Pet  # noqa: E402
from app.services.petgen.pipeline import cutout_dominant_bg, download  # noqa: E402

BASE = "https://ark.cn-beijing.volces.com/api/plan/v3"
KEY = [l.split("=", 1)[1].strip() for l in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines() if l.startswith("ARK_API_KEY=")][0]
MODEL = "doubao-seedream-5.0-lite"
STYLE = "手绘童话插画风, 暖色调, 水彩质感"

DESIGNS = json.loads((ROOT / "backend" / "app" / "content" / "animation_designs.json").read_text(encoding="utf-8"))


def route_for(species: str) -> dict:
    for route in DESIGNS["routes"]:
        if any(k in species for k in route["match"]):
            return route["actions"]
    return DESIGNS["default_actions"]


def gen_frame(prompt: str, ref: str, out: Path) -> None:
    payload = {"model": MODEL, "prompt": prompt, "size": "2048x2048", "response_format": "url", "image": ref}
    req = urllib.request.Request(
        f"{BASE}/images/generations",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        url = json.loads(r.read())["data"][0]["url"]
    raw = out.with_suffix(".raw.jpg")
    download(url, raw)
    img = cutout_dominant_bg(Image.open(raw))
    bbox = img.getchannel("A").getbbox()
    if bbox:
        img = img.crop(bbox)
    img.save(out)


def gen_strip(action: str, spec: dict, appearance: str, ref: str, out_dir: Path) -> None:
    """条带模式 (2026-09-19 拍板): 一次生图出"双帧条带"(2列1行), 从中线切开 = 首帧+尾帧。
    同一次生成 → 两帧角色一致性天然锁定, 且调用减半。"""
    prompt = (
        f"一张游戏角色双帧对比图, 2列1行均匀排列同一角色的两个连续动作关键帧: "
        f"左帧: {spec['first']}; 右帧: {spec['last']}。"
        f"角色是{appearance}, 两帧毛色长相画风完全一致、大小一致、间距均匀互不重叠, "
        f"{STYLE}, 纯白色背景, 无阴影, 无文字, 无网格线无边框"
    )
    payload = {"model": MODEL, "prompt": prompt, "size": "2048x2048", "response_format": "url", "image": ref}
    req = urllib.request.Request(
        f"{BASE}/images/generations",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        url = json.loads(r.read())["data"][0]["url"]
    raw = out_dir / f"{action}_strip_raw.jpg"
    download(url, raw)
    img = Image.open(raw)
    w, h = img.size
    for i, phase in enumerate(("first", "last")):
        cell = img.crop((i * w // 2, 0, (i + 1) * w // 2, h))
        cut = cutout_dominant_bg(cell)
        bbox = cut.getchannel("A").getbbox()
        if bbox:
            cut = cut.crop(bbox)
        cut.save(out_dir / f"{action}_{phase}.png")
    print(f"  {action}: 条带切分完成 (first/last)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pet_id", type=int)
    ap.add_argument("--actions", default="")  # 逗号分隔, 默认全套
    ap.add_argument("--strip", action="store_true", help="条带模式: 一次生图出双帧再切开 (默认开)")
    ap.add_argument("--no-strip", dest="strip", action="store_false")
    ap.set_defaults(strip=True)
    args = ap.parse_args()

    db = SessionLocal()
    pet = db.get(Pet, args.pet_id)
    db.close()
    assert pet, f"宠物 {args.pet_id} 不存在"
    appearance = pet.appearance or f"一只可爱的{pet.color}色系的{pet.species}"
    print(f"宠物: {pet.name} ({pet.species}), 外观: {appearance}", flush=True)

    actions = route_for(pet.species)
    only = set(args.actions.split(",")) if args.actions else set(actions.keys())
    ref_frame = ROOT / "backend" / "static" / "pets" / str(pet.id) / "frames" / "idle_0.png"
    assert ref_frame.is_file(), "先有形象帧 (idle_0.png) 才能设计动作帧"
    ref = "data:image/png;base64," + base64.b64encode(ref_frame.read_bytes()).decode()

    out_dir = ROOT / "backend" / "static" / "pets" / str(pet.id) / "_anim_pending"
    out_dir.mkdir(parents=True, exist_ok=True)

    for action, spec in actions.items():
        if action not in only:
            continue
        if args.strip:
            # 条带模式: 一次生图出双帧 (角色一致性锁定, 调用减半)
            if (out_dir / f"{action}_first.png").exists() and (out_dir / f"{action}_last.png").exists():
                print(f"  跳过已有 {action}", flush=True)
            else:
                print(f"  生成 {action} 条带...", flush=True)
                gen_strip(action, spec, appearance, ref, out_dir)
            (out_dir / f"{action}.txt").write_text(
                spec["video_prompt"] + ", 纯白背景", encoding="utf-8")
            continue
        for phase in ("first", "last"):
            out = out_dir / f"{action}_{phase}.png"
            if out.exists():
                print(f"  跳过已有 {action}_{phase}", flush=True)
                continue
            prompt = (f"参考图中的这只小家伙({appearance}), 保持完全相同的毛色长相画风, "
                      f"{spec[phase]}, {STYLE}, 纯白色背景, 无阴影, 无文字")
            print(f"  生成 {action}_{phase}...", flush=True)
            gen_frame(prompt, ref, out)
        (out_dir / f"{action}.txt").write_text(
            spec["video_prompt"] + ", 纯白背景", encoding="utf-8")
        print(f"  {action}: 首尾帧+视频prompt 就绪", flush=True)

    print(f"\n全部就绪: {out_dir}")
    print("下一步: 控制台用 首帧+尾帧+{action}.txt 的提示词生成视频, mp4 放回该目录后跑 video_to_frames.py 采收")


if __name__ == "__main__":
    main()
