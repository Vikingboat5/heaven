"""宠物生成管线: 精灵表生成 → 网格切帧 → 抠图(防吃白毛三件套) → 对齐 → QC → manifest

工艺要点(全部来自实测, 勿随意改动):
- 单图精灵表: 1 次调用 16k tokens 出 8 帧, 角色一致性优于逐帧 i2i
- 网格单元切帧: 模型布局足够规整, 按均分格子切, 格内保留全部前景(分离肢体不丢)
- 防吃白毛三件套: opening 断桥 → fill_holes 填洞 → 画布级 fill_holes 终检(有些通道裁剪后才闭合)
- TOS 预签名 URL 24h 过期, 必须即时下载落盘
- 原始图 + 生成参数落盘: 后处理迭代可离线重跑(reprocess), 零 token 成本
"""
from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from ...config import settings
from .profiles import (
    ACTION_TEMPLATES,
    WHITE_BG_CLAUSE,
    ActionTemplate,
    StyleProfile,
)

CANVAS = 512            # 输出帧画布
GEN_RETRY = 2           # 生成重试上限
DOWNLOAD_RETRY = 4

# 默认素材根目录: 以本文件位置锚定(backend/static/pets), 不依赖启动时的工作目录
_DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "static" / "pets"


class PetGenError(Exception):
    """生成管线异常: 触发降级链"""


@dataclass
class GenParams:
    """落盘的生成参数: 离线重跑后处理的完整上下文"""
    pet_id: int
    style: str
    action: str
    appearance: str        # 外观描述(物种+颜色+IP特征词)
    prompt: str
    prompt_version: str
    model: str


def build_prompt(action: ActionTemplate, appearance: str, style: StyleProfile) -> str:
    """精灵表 prompt 模板 (spec 4.0 定稿)"""
    n = action.frame_count
    return (
        f"一张游戏角色精灵表(sprite sheet), "
        f"{action.grid_cols}列{action.grid_rows}行均匀排列{n}个动画关键帧, "
        f"同一角色的动画渐变序列, 按从左到右、从上到下顺序: "
        f"{action.frame_order_clause}. "
        f"角色是{appearance}, {style.prompt_style}. "
        f"{n}个关键帧大小一致、角色完整位于各自格内且四周留有空白边距(不可超出格子)、"
        f"姿势只有细微差别、风格完全一致、间距均匀互不重叠, "
        f"{WHITE_BG_CLAUSE}"
    )


class ArkImageClient:
    """方舟生图客户端 (Agent Plan 端点)"""

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None, timeout: int = 180):
        self.api_key = api_key or settings.ark_api_key
        self.base_url = (base_url or settings.ark_image_base_url).rstrip("/")
        self.model = model or settings.ark_image_model
        self.timeout = timeout

    def generate_image(self, prompt: str, size: str = "2048x2048",
                       reference_url: str | None = None) -> str:
        """文生图/i2i(传 reference_url), 返回 TOS 预签名 URL(24h 过期)"""
        payload: dict = {"model": self.model, "prompt": prompt,
                         "size": size, "response_format": "url"}
        if reference_url:
            payload["image"] = reference_url
        last_err: Exception | None = None
        for attempt in range(GEN_RETRY + 1):
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/images/generations",
                    data=json.dumps(payload).encode(),
                    headers={"Authorization": f"Bearer {self.api_key}",
                             "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read())["data"][0]["url"]
            except Exception as e:  # 网络波动/限流, 重试
                last_err = e
                time.sleep(5 * (attempt + 1))
        raise PetGenError(f"生图失败(重试{GEN_RETRY}次): {last_err}")


def download(url: str, path: Path) -> None:
    """下载生成结果(TOS URL 24h 过期, 必须即时落盘)"""
    last_err: Exception | None = None
    for attempt in range(DOWNLOAD_RETRY):
        try:
            urllib.request.urlretrieve(url, path)
            return
        except Exception as e:
            last_err = e
            time.sleep(3)
    raise PetGenError(f"下载失败(重试{DOWNLOAD_RETRY}次): {last_err}")


# ---------------- 后处理(纯本地, 可离线重跑) ----------------

def _cutout_cell(cell: Image.Image, profile: StyleProfile) -> np.ndarray:
    """格内抠图: 防吃白毛三件套。返回 RGBA 数组"""
    a = np.asarray(cell).astype(np.float32)
    # ① opening 断 JPEG 噪点细桥, 再洪泛(防浅色毛发被吃)
    whitish = a.min(axis=2) > profile.whitish_threshold
    if profile.opening_iterations:
        whitish = ndimage.binary_opening(whitish, iterations=profile.opening_iterations)
    lbl, _ = ndimage.label(whitish)
    border = set(np.unique(np.concatenate(
        [lbl[0, :], lbl[-1, :], lbl[:, 0], lbl[:, -1]])))
    border.discard(0)
    fg = ~np.isin(lbl, list(border))
    # 格内保留全部前景(分离的肢体不丢), 只滤小噪点(水印)
    comp, nc = ndimage.label(fg)
    if nc > 0:
        sizes = np.array([ndimage.sum(fg, comp, i + 1) for i in range(nc)])
        keep = np.zeros_like(fg)
        for i in range(nc):
            if sizes[i] > sizes.max() * 0.02:
                keep |= comp == (i + 1)
        fg = keep
    # ② 填闭合空洞
    fg = ndimage.binary_fill_holes(fg)
    alpha = (fg * 255).astype(np.uint8)
    if profile.feather_sigma > 0:
        alpha = np.clip(ndimage.gaussian_filter(
            alpha.astype(np.float32), sigma=profile.feather_sigma), 0, 255).astype(np.uint8)
    return np.dstack([a.astype(np.uint8), alpha])


def _normalize(rgba: np.ndarray, profile: StyleProfile) -> Image.Image:
    """对齐: alpha 包围盒裁剪 → 等比缩放 → 底部居中锚定画布

    缩放取高/宽两个方向的最小比 (2026-09 doze 实测: 趴睡姿势宽大于高,
    只按高缩放会横向溢出裁掉耳朵/头)。"""
    im = Image.fromarray(rgba, "RGBA")
    bbox = im.getchannel("A").getbbox()
    if not bbox:
        raise PetGenError("切帧后前景为空")
    crop = im.crop(bbox)
    ratio = min((CANVAS * 0.80) / crop.height, (CANVAS * 0.86) / crop.width)
    w, h = max(1, int(crop.width * ratio)), max(1, int(crop.height * ratio))
    resample = Image.NEAREST if profile.resize_nearest else Image.LANCZOS
    crop = crop.resize((w, h), resample)
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    canvas.paste(crop, ((CANVAS - w) // 2, CANVAS - h - 30), crop)
    # ③ 画布级终检: 有些通道裁剪后才闭合, 必须在这里再堵一次
    ca = np.asarray(canvas).copy()
    fa = ndimage.binary_fill_holes(ca[..., 3] > 0)
    ca[..., 3] = (fa * 255).astype(np.uint8)
    return Image.fromarray(ca, "RGBA")


def _has_drawn_border(cell: Image.Image) -> bool:
    """QC 辅助: 检测模型手绘的格线边框 (生活动作表实测复发, 2026-09)。

    判定: 单元格四边 6px 条带的暗色像素占比全部 > 25%
    (角色贴边只会压一两条边, 完整矩形框才会四边全占)。
    """
    lum = np.asarray(cell).astype(np.int16).min(axis=2)
    s = 6
    strips = (lum[:s, :], lum[-s:, :], lum[:, :s], lum[:, -s:])
    return all(float((strip < 150).mean()) > 0.25 for strip in strips)


def count_holes(frame: Image.Image) -> int:
    """QC: 闭合透明空洞像素数(交付帧必须为 0)"""
    t = np.asarray(frame)[..., 3] == 0
    lbl, _ = ndimage.label(t)
    border = set(np.unique(np.concatenate(
        [lbl[0, :], lbl[-1, :], lbl[:, 0], lbl[:, -1]])))
    border.discard(0)
    return int((~np.isin(lbl, list(border)) & t).sum())


def process_sheet(raw_path: Path, action: ActionTemplate,
                  profile: StyleProfile) -> tuple[list[Image.Image], dict]:
    """精灵表 → 帧序列 + QC 报告。纯本地处理, 可离线重跑"""
    img = Image.open(raw_path).convert("RGB")
    W, H = img.size
    cw, ch = W // action.grid_cols, H // action.grid_rows

    frames: list[Image.Image] = []
    areas: list[int] = []
    border_cells: list[int] = []
    for row in range(action.grid_rows):
        for col in range(action.grid_cols):
            cell = img.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch))
            if _has_drawn_border(cell):
                border_cells.append(row * action.grid_cols + col)
            rgba = _cutout_cell(cell, profile)
            areas.append(int((rgba[..., 3] > 0).sum()))
            frames.append(_normalize(rgba, profile))

    # QC: 帧数 + 面积离群(AI 瑕疵帧如多尾巴会面积异常) + 空洞 + 手绘格线边框
    median = float(np.median(areas))
    outliers = [i for i, a in enumerate(areas)
                if not (median / profile.max_area_outlier <= a <= median * profile.max_area_outlier)]
    holes = {i: count_holes(f) for i, f in enumerate(frames)}
    bad_holes = {i: h for i, h in holes.items() if h > 0}
    qc = {
        "frame_count": len(frames),
        "expected": action.frame_count,
        "areas": areas,
        "area_outliers": outliers,
        "holes": holes,
        "border_cells": border_cells,
        "passed": (len(frames) == action.frame_count
                   and not outliers and not bad_holes and not border_cells),
    }
    return frames, qc


# ---------------- 管线入口 ----------------

class PetForge:
    """宠物形象生成管线"""

    def __init__(self, client: ArkImageClient | None = None,
                 out_root: Path | None = None):
        self.client = client or ArkImageClient()
        self.out_root = out_root or _DEFAULT_ROOT

    def _pet_dir(self, pet_id: int) -> Path:
        d = self.out_root / str(pet_id)
        (d / "frames").mkdir(parents=True, exist_ok=True)
        return d

    def generate(self, pet_id: int, appearance: str, style_key: str,
                 action_keys: tuple[str, ...] = ("idle",)) -> dict:
        """完整生成: 每个动作一张精灵表 → 切帧 → QC → 落盘 + manifest

        QC 失败重试 GEN_RETRY 次, 仍失败抛 PetGenError 触发降级链。
        """
        from .profiles import STYLE_PROFILES
        profile = STYLE_PROFILES[style_key]
        pet_dir = self._pet_dir(pet_id)
        manifest: dict = {"pet_id": pet_id, "style": style_key,
                          "prompt_version": profile.prompt_version,
                          "actions": {}, "qc": {}}

        for action_key in action_keys:
            action = ACTION_TEMPLATES[action_key]
            prompt = build_prompt(action, appearance, profile)
            last_qc: dict | None = None
            frames: list[Image.Image] | None = None
            for attempt in range(GEN_RETRY + 1):
                url = self.client.generate_image(prompt)
                raw_path = pet_dir / f"raw_sheet_{action_key}.jpg"
                download(url, raw_path)
                # 生成参数落盘(支持 reprocess 离线重跑)
                (pet_dir / f"gen_params_{action_key}.json").write_text(
                    json.dumps(asdict(GenParams(
                        pet_id=pet_id, style=style_key, action=action_key,
                        appearance=appearance, prompt=prompt,
                        prompt_version=profile.prompt_version,
                        model=self.client.model)), ensure_ascii=False, indent=2),
                    encoding="utf-8")
                frames, last_qc = process_sheet(raw_path, action, profile)
                if last_qc["passed"]:
                    break
            # H6: 非 idle 动作 QC 连败 → 只跳过该动作(记 manifest), 不影响其余动作
            if not (last_qc and last_qc["passed"]):
                if action_key == "idle":
                    raise PetGenError(f"动作 {action_key} 质检连续失败: {last_qc}")
                manifest["qc"][action_key] = {
                    "passed": False, "reason": "qc_failed", "detail": last_qc,
                }
                continue

            for i, frame in enumerate(frames or []):
                frame.save(pet_dir / "frames" / f"{action_key}_{i}.png")
            manifest["actions"][action_key] = {
                "frames": action.frame_count,
                "sequence": list(action.sequence),
                "frame_ms": action.frame_ms,
            }
            manifest["qc"][action_key] = last_qc

        (pet_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest

    def reprocess(self, pet_id: int, action_key: str) -> dict:
        """离线重跑后处理: 用落盘的原始图 + 参数, 零 token 成本。

        后处理算法/profile 参数迭代时用。返回 QC 报告。
        """
        from .profiles import STYLE_PROFILES
        pet_dir = self._pet_dir(pet_id)
        params = json.loads((pet_dir / f"gen_params_{action_key}.json").read_text(encoding="utf-8"))
        profile = STYLE_PROFILES[params["style"]]
        action = ACTION_TEMPLATES[action_key]
        frames, qc = process_sheet(pet_dir / f"raw_sheet_{action_key}.jpg", action, profile)
        if not qc["passed"]:
            raise PetGenError(f"重处理质检失败: {qc}")
        for i, frame in enumerate(frames):
            frame.save(pet_dir / "frames" / f"{action_key}_{i}.png")
        return qc
