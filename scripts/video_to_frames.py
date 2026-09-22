"""视频 → 帧序列 → 接入游戏 (帧动画管线跑通版, 2026-09-12)

视频=动作素材中间件, 帧序列=运行时格式。
用法: python scripts/video_to_frames.py [pet_id] [动作名] [视频路径]
默认: python scripts/video_to_frames.py 28 video_idle .../_video_probe/video.mp4

产物: backend/static/pets/{id}/frames/{action}_{i}.png + manifest 写入该动作 + contact.png + preview.gif
"""
import sys
from pathlib import Path

import imageio.v3 as iio
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.petgen.pipeline import cutout_dominant_bg  # noqa: E402
from app.services.petgen.pipeline import _decontaminate  # noqa: E402  # 边缘去白边(复用精灵表工艺)


def remove_ground_shadow(img: Image.Image) -> Image.Image:
    """去掉"脚下的椭圆阴影" (实测阴影是浅灰紫 min~177, 不是近白):
    内容包围盒底部 12% 区域内, 浅色(min>150)且宽(>30%内容宽)的组件判为影子删除。
    狐狸的爪子是深色 → 保留; 白尾尖在中上部 → 不受影响。"""
    a = np.array(img)  # RGBA 副本
    alpha = a[..., 3]
    if not alpha.any():
        return img
    ys, xs = np.where(alpha > 0)
    y0, y1 = int(ys.min()), int(ys.max())
    h = max(1, y1 - y0)
    w_content = int(xs.max()) - int(xs.min()) + 1
    bottom = y0 + h * 0.88  # 底部 12%
    light = (a[..., :3].min(axis=2) > 150) & (alpha > 0)
    light[: int(bottom), :] = False  # 只看底部
    from scipy import ndimage
    lbl, n = ndimage.label(light)
    for i in range(1, n + 1):
        ys2, xs2 = np.where(lbl == i)
        w2 = int(xs2.max()) - int(xs2.min()) + 1
        if w2 > w_content * 0.3:
            a[..., 3][lbl == i] = 0
    # 脚缝间残留的小块浅色影子: 底部区域的浅色像素一律删除 (狐狸脚底是深色, 底部无合法浅色)
    a[..., 3][(a[..., :3].min(axis=2) > 150) & (np.arange(a.shape[0]) > bottom)[:, None] & (alpha > 0)] = 0
    # 影子的深色描边环/发丝线: 底部区域的宽(>30%)且扁(<14px)组件, 或 1-2px 发丝横线(w>40px)
    alpha2 = a[..., 3]
    band = np.zeros_like(alpha2, dtype=bool)
    band[int(bottom):, :] = alpha2[int(bottom):, :] > 0
    lbl2, n2 = ndimage.label(band)
    for i in range(1, n2 + 1):
        ys2, xs2 = np.where(lbl2 == i)
        w2 = int(xs2.max()) - int(xs2.min()) + 1
        h2 = int(ys2.max()) - int(ys2.min()) + 1
        if (w2 > w_content * 0.3 and h2 < 14) or (h2 <= 2 and w2 > 40):
            a[..., 3][lbl2 == i] = 0
    # 影子描边和脚爪连通时的兜底: 最底 3 行只保留脚爪横向范围(±4px)内的像素
    # (实测: 影子描边与脚爪连通成一个组件, 组件规则无法分离, 只能按脚的范围裁)
    alpha3 = a[..., 3]
    ys3, _ = np.where(alpha3 > 0)
    if len(ys3):
        y1b = int(ys3.max())
        feet_zone = alpha3[max(0, y1b - 14): y1b - 3]
        cols = np.where(feet_zone.any(axis=0))[0]
        if len(cols):
            keep_l, keep_r = int(cols.min()) - 4, int(cols.max()) + 5
            tail = alpha3[y1b - 3: y1b + 1]
            mask = np.zeros_like(tail)
            mask[:, keep_l:keep_r] = True
            a[..., 3][y1b - 3: y1b + 1] = np.where(mask, tail, 0)
    return Image.fromarray(a, "RGBA")

PET_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 28
ACTION = sys.argv[2] if len(sys.argv) > 2 else "video_idle"
SRC = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "backend" / "static" / "pets" / "_video_probe" / "video.mp4"

PET_DIR = ROOT / "backend" / "static" / "pets" / str(PET_ID)
SAMPLE_N = 24          # 采 24 帧 (121 帧 5s 视频 → 等距采样)
FRAME_MS = 90
CANVAS = 512


def _robust_content_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    """稳健内容包围盒: alpha>24 且只保留 ≥最大组件 1.5% 的组件 (碎屑不撑包围盒)
    对齐 fix_asset_bboxes.py 的工艺——alpha 羽化散点会让朴素 getbbox 失效"""
    from scipy import ndimage
    a = np.asarray(img)
    mask = a[..., 3] > 24
    if not mask.any():
        return None
    lbl, n = ndimage.label(mask)
    if n == 0:
        return None
    sizes = np.bincount(lbl.ravel())[1:]
    keep = np.zeros_like(mask)
    biggest = sizes.max()
    for i in range(1, n + 1):
        if sizes[i - 1] >= max(100, biggest * 0.015):
            keep[lbl == i] = True
    ys, xs = np.where(keep)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _feet_cx(img: Image.Image, bbox: tuple[int, int, int, int]) -> float:
    """脚底水平质心 (根骨骼锚点, 2026-09-20 拍板"根不动身体活"):
    包围盒底部 12% 区域(脚爪)的前景像素水平均值。
    骨骼动画的原理: 根骨骼(脚底)永不动, 身体在根上方自由呼吸/摇摆——
    锚定在脚 = 地面感; 锚定在头 = 把头也锁死(僵)。
    尾巴垂地时也在底部, 但尾巴摆动是绕脚踝的小角度, 质心漂移远小于剪影中心。"""
    a = np.asarray(img)
    x0, y0, x1, y1 = bbox
    band_h = max(2, int((y1 - y0) * 0.12))
    mask = a[y1 - band_h: y1, x0: x1, 3] > 24
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return (x0 + x1) / 2
    return x0 + float(xs.mean())


def _drop_specks(img: Image.Image) -> Image.Image:
    """删除前景小碎屑: 只保留 ≥最大组件 1.5% 的组件 (视频抠图后的残留碎点)"""
    from scipy import ndimage
    a = np.array(img)
    mask = a[..., 3] > 24
    if not mask.any():
        return img
    lbl, n = ndimage.label(mask)
    sizes = np.bincount(lbl.ravel())[1:]
    biggest = sizes.max()
    keep = np.zeros_like(mask)
    for i in range(1, n + 1):
        if sizes[i - 1] >= max(100, biggest * 0.015):
            keep[lbl == i] = True
    a[..., 3] = np.where(keep, a[..., 3], 0)
    return Image.fromarray(a, "RGBA")


def _feet_y(img: Image.Image, bbox: tuple[int, int, int, int]) -> int:
    """脚线 = 身体中央列(45%宽)内的内容底边 (排除两侧尾巴尖)
    2026-09-20 修"点击后上下位移": 锚'剪影底部'锚到的是尾巴尖, idle尾尖垂得低/petted不垂,
    两个动作的'脚'上下差30px; 锚'脚'(中央列底)才是同一条地面线"""
    a = np.asarray(img)
    x0, _, x1, _ = bbox
    w = x1 - x0
    cx0 = x0 + int(w * 0.275)
    cx1 = x0 + int(w * 0.725)
    col = a[:, cx0:cx1, 3]
    ys, _ = np.where(col > 24)
    return int(ys.max()) + 1 if len(ys) else bbox[3]


def cut_video(pet_id: int, action: str, src: Path,
              sample_n: int = SAMPLE_N, frame_ms: int = FRAME_MS) -> None:
    """视频 → 帧序列 → manifest 合并 (可被 gen_action_video.py 复用)
    尺寸/位置统一锚点 (2026-09-19): 以 video_idle_0 为基准, 各动作用"帧的中位数包围盒"
    对齐到同一身高/同一水平中心/同一脚底线, 消除动作切换时的忽大忽小"""
    import json
    print(f"读取 {src.name}...", flush=True)
    vid = iio.imread(src)
    total = vid.shape[0]
    idxs = [round(i * (total - 1) / (sample_n - 1)) for i in range(sample_n)]
    print(f"总 {total} 帧, 采 {sample_n} 帧", flush=True)

    pet_dir = ROOT / "backend" / "static" / "pets" / str(pet_id)
    frames_dir = pet_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # 第一遍: 抠图+净化+去碎屑, 收集稳健包围盒
    cleaned: list[tuple[Image.Image, tuple[int, int, int, int]]] = []
    for fi in idxs:
        img = cutout_dominant_bg(Image.fromarray(vid[fi]))
        img = Image.fromarray(_decontaminate(np.array(img)), "RGBA")  # 边缘去白边
        img = remove_ground_shadow(img)                               # 去脚下白影
        img = _drop_specks(img)                                       # 去碎屑
        bbox = _robust_content_bbox(img)
        if bbox:
            cleaned.append((img, bbox))

    # 中位数指标 (稳健包围盒): 排除抬爪/歪头等瞬时姿态对包围盒的影响
    # 缩放基准 = 身长 (头顶→脚线, 解剖学参考) 而非"最紧凑姿势的包围盒高"——
    # 后者因姿势定义不同在各动作间不一致 (2026-09-20 修"点击后上下位移~10px")
    import statistics
    body_lens = [(_feet_y(img, b) - b[1]) for img, b in cleaned]
    med_body_len = statistics.median(body_lens)

    # 统一身高锚点: 写在 manifest.meta, 第一个视频动作设定, 后续动作全部对齐
    # (2026-09-19: 修"动作切换狐狸忽大忽小"——按身体最紧凑姿态等比, 不按包围盒中位数)
    mpath_pre = pet_dir / "manifest.json"
    if mpath_pre.exists():
        _m = json.loads(mpath_pre.read_text(encoding="utf-8"))
    else:
        _m = {"pet_id": pet_id, "style": "video", "actions": {}, "qc": {}}
    anchor = _m.get("meta", {}).get("anchor_height")
    if action == "video_idle" or anchor is None:
        anchor = int(CANVAS * 0.72)
        _m.setdefault("meta", {})["anchor_height"] = anchor
        mpath_pre.write_text(json.dumps(_m, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  设定身高锚点: {anchor}px", flush=True)
    else:
        print(f"  沿用身高锚点: {anchor}px", flush=True)
    ref_cx = CANVAS / 2
    ref_bottom = CANVAS - 30

    scale = anchor / med_body_len
    # 并集裁剪窗: 全部帧的稳健包围盒取并集, 整个动作共用同一个窗口
    # (逐帧 re-anchor 是漂移和偏移的总根因——帧动画的正确做法是"同一画布注册", 视频自带的位置/摇晃原样保留)
    ux0 = min(b[0] for _, b in cleaned)
    uy0 = min(b[1] for _, b in cleaned)
    ux1 = max(b[2] for _, b in cleaned)
    uy1 = max(b[3] for _, b in cleaned)

    # 跨动作注册对齐 (2026-09-20): 以第一个动作(通常是 idle)的"内容落点"为全局锚,
    # 其他动作的整段帧统一平移对齐, 消除"点一下狐狸跳位置"
    # 落点x = 各帧内容包围盒的中位数中心x; 落点y = 各帧"脚线"(中央列底)的中位数, 统一到 ref_bottom
    med_cx = statistics.median((b[0] + b[2]) / 2 for _, b in cleaned)
    med_feet = statistics.median(_feet_y(img, b) for img, b in cleaned)
    canvas_cx = ref_cx + (med_cx - (ux0 + ux1) / 2) * scale
    meta = _m.setdefault("meta", {})
    if meta.get("anchor_cx") is None:
        meta["anchor_cx"] = round(canvas_cx, 1)
        mpath_pre.write_text(json.dumps(_m, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  设定注册中心x: {meta['anchor_cx']}", flush=True)
    dx = meta["anchor_cx"] - canvas_cx
    # 脚线直接对 ref_bottom (所有动作同一条地面线, 不需要存锚)
    feet_canvas = ref_bottom + (med_feet - uy1) * scale
    dy = ref_bottom - feet_canvas
    if abs(dx) > 1 or abs(dy) > 1:
        print(f"  注册对齐偏移: dx={dx:.0f} dy={dy:.0f}", flush=True)

    frames = []
    for out_i, (img, bbox) in enumerate(cleaned):
        # 统一窗口裁剪 (不逐帧裁): 视频里的相对位置原样保留, 帧间零位移
        img = img.crop((ux0, uy0, ux1, uy1))
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
        # 窗口固定摆放: 居中 x, 底边对锚点 y, 加跨动作注册偏移
        px = int(round(ref_cx - img.width / 2 + dx))
        py = int(round(ref_bottom - img.height + dy))
        canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        canvas.paste(img, (px, py), img)
        canvas.save(frames_dir / f"{action}_{out_i}.png")
        frames.append(canvas)

    # manifest 写入该动作 (幂等: 读现有 manifest 合并)
    # 序列 = ping-pong 正放+倒放 (2026-09-20 拍板, 对齐游戏动画设计: 动作"出去再回来",
    # 天然消循环接缝 + 天然回到待机姿势, 无需首尾帧==同一张图)
    mpath = pet_dir / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {
        "pet_id": pet_id, "style": "video", "actions": {}, "qc": {}}
    sequence = list(range(sample_n)) + list(range(sample_n - 2, 0, -1))
    manifest["actions"][action] = {
        "frames": sample_n,
        "sequence": sequence,
        "frame_ms": frame_ms,
    }
    manifest.setdefault("qc", {})[action] = {"source": str(src.name), "sampled": sample_n}
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 目检: 拼图 + GIF
    BG = (21, 12, 46)
    cols, rows = 6, 4
    grid = Image.new("RGB", (cols * 170, rows * 170), BG)
    for i, f in enumerate(frames):
        t = f.resize((170, 170), Image.LANCZOS)
        cell = Image.new("RGB", (170, 170), BG)
        cell.paste(t, (0, 0), t)
        grid.paste(cell, ((i % cols) * 170, (i // cols) * 170))
    grid.save(pet_dir / f"contact_{action}.png")
    rgb = []
    for f in frames:
        bg = Image.new("RGB", f.size, BG)
        bg.paste(f, (0, 0), f)
        rgb.append(bg.resize((256, 256), Image.LANCZOS))
    rgb[0].save(pet_dir / f"preview_{action}.gif", save_all=True, append_images=rgb[1:], duration=frame_ms, loop=0)
    print(f"完成: {sample_n} 帧写入 {frames_dir}, manifest 已更新")
    print(f"目检: {pet_dir / f'contact_{action}.png'} / preview_{action}.gif")


def main() -> None:
    cut_video(PET_ID, ACTION, SRC)


if __name__ == "__main__":
    main()
