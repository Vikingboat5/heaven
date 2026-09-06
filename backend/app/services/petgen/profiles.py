"""宠物生成管线: 画风配置(StyleProfile) + 动作模板(ActionTemplate)

可迭代设计(spec 4.0): 新增画风/动作 = 在这里加配置, 不改管线代码。
每个 profile 的参数都是实测定型的(见 docs/demo/ 金样本)。
prompt_version 写入 manifest, prompt 优化后可按版本回溯重新生成。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StyleProfile:
    """画风配置: prompt 风格词 + 后处理参数 + QC 规则"""
    key: str
    prompt_style: str          # 注入精灵表 prompt 的风格描述
    prompt_version: str        # prompt 模板版本(优化后递增)
    whitish_threshold: int     # 白底判定阈值(像素最小通道 > 该值视为近白)
    opening_iterations: int    # 形态学腐蚀断桥次数(防 JPEG 噪点桥吃掉浅色毛发)
    feather_sigma: float       # alpha 边缘羽化; 0 = 硬边(像素风)
    resize_nearest: bool       # True = NEAREST(像素风保锐利), False = LANCZOS
    max_area_outlier: float    # QC: 帧面积离群容忍(相对中位数倍数)


STYLE_PROFILES: dict[str, StyleProfile] = {
    # 手绘童话插画风: 柔边, LANCZOS 平滑缩放 (docs/demo/sheet8 验收; v2: idle 12帧模板)
    "illustration": StyleProfile(
        key="illustration",
        prompt_style="手绘童话插画风, 暖色调, 柔和线条, 水彩质感",
        prompt_version="illustration-v2",
        whitish_threshold=235,
        opening_iterations=2,
        feather_sigma=1.2,
        resize_nearest=False,
        max_area_outlier=2.0,
    ),
    # 复古像素风: 硬边, NEAREST 缩放保像素颗粒 (docs/demo/pixel 验收; v2: idle 12帧模板)
    "pixel": StyleProfile(
        key="pixel",
        prompt_style="复古16-bit像素画风格(pixel art), 清晰锐利的像素颗粒, 有限色板, 色块平涂无渐变",
        prompt_version="pixel-v2",
        whitish_threshold=240,
        opening_iterations=2,
        feather_sigma=0.0,
        resize_nearest=True,
        max_area_outlier=2.0,
    ),
}

DEFAULT_STYLE = "illustration"

# 白底约束: 实测必须强硬, 弱约束模型会自行加草地背景导致抠图失败;
# "无边框无分隔线" 针对生活动作表实测复发的格线瑕疵 (2026-09)
WHITE_BG_CLAUSE = "纯白色背景, 无草地无阴影无网格线无边框无分隔线无编号文字无任何环境元素"


@dataclass(frozen=True)
class ActionTemplate:
    """动作模板: 帧数/网格/逐帧姿势描述/播放序列/帧间隔"""
    key: str
    frame_count: int
    grid_cols: int
    grid_rows: int
    frame_specs: tuple[str, ...]   # 逐帧姿势描述, 按从左到右、从上到下
    sequence: tuple[int, ...]      # 播放序列(帧索引)
    frame_ms: int

    @property
    def frame_order_clause(self) -> str:
        """prompt 中的逐帧描述段"""
        parts = [f"第{i+1}帧{spec}" for i, spec in enumerate(self.frame_specs)]
        return ", ".join(parts)


ACTION_TEMPLATES: dict[str, ActionTemplate] = {
    # 待机: 12帧完整眨眼渐变 + 耳/头微动 (2026-09 帧数实验: 12帧(4x3)一致性/QC全胜,
    # 16帧(4x4)模型画出网格线且帧幅不一, 超出布局稳定区; 全序列顺序播放 110ms 更流畅)
    "idle": ActionTemplate(
        key="idle",
        frame_count=12,
        grid_cols=4,
        grid_rows=3,
        frame_specs=(
            "睁眼自然微笑", "睁眼放松", "眼睛微眯", "眼睛半闭",
            "闭眼微笑", "闭眼微笑保持", "眼睛半闭", "眼睛微眯",
            "睁眼自然微笑", "双耳微微竖起", "头微微向左倾", "睁眼自然微笑与第1帧相同",
        ),
        sequence=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
        frame_ms=110,
    ),
    # 招手: 抬爪→举高→左右挥→放下 (docs/demo/pixel 验收)
    "wave": ActionTemplate(
        key="wave",
        frame_count=8,
        grid_cols=4,
        grid_rows=2,
        frame_specs=(
            "站立自然右爪放下", "右爪微微抬起", "右爪举到肩高", "右爪举到最高",
            "右爪举高向左挥", "右爪举高向右挥", "右爪回落到肩高",
            "站立自然与第1帧相同",
        ),
        sequence=(0, 1, 2, 3, 4, 5, 6, 5, 4, 5, 6, 7),
        frame_ms=140,
    ),
    # ---- 生活动作 (H6, 2026-09-05): 12帧 4x3, 单次播完回 idle ----
    # 伸懒腰: 下沉→前伸→翘臀保持→回弹→甩头
    "stretch": ActionTemplate(
        key="stretch",
        frame_count=12,
        grid_cols=4,
        grid_rows=3,
        frame_specs=(
            "站立自然睁眼", "前身开始下沉", "前爪向前伸出身体压低", "前爪伸到最直屁股高高翘起",
            "保持伸懒腰姿势闭眼", "保持伸懒腰姿势闭眼", "身体开始回弹", "站直轻轻甩了甩头",
            "站立自然睁眼", "打了个小哈欠", "睁眼自然微笑", "站立自然与第1帧相同",
        ),
        sequence=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
        frame_ms=120,
    ),
    # 舔爪子: 抬爪→低头舔→眯眼满足→放下
    "groom": ActionTemplate(
        key="groom",
        frame_count=12,
        grid_cols=4,
        grid_rows=3,
        frame_specs=(
            "坐姿自然睁眼", "抬起右前爪", "低头凑近爪子", "伸出舌头舔爪子",
            "舔爪子", "眯起眼睛舔爪子", "抬起头眯眼满足", "放下爪子",
            "坐姿自然睁眼", "双耳轻轻抖了一下", "坐姿自然睁眼", "坐姿自然与第1帧相同",
        ),
        sequence=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
        frame_ms=120,
    ),
    # 打盹: 趴下→头埋爪子→睡→耳朵偶抖
    "doze": ActionTemplate(
        key="doze",
        frame_count=12,
        grid_cols=4,
        grid_rows=3,
        frame_specs=(
            "站立自然睁眼", "前腿弯曲身体下沉", "趴下前爪收拢", "趴着头抬着",
            "头慢慢低下", "头埋在前爪上闭眼", "闭眼睡觉", "闭眼睡觉",
            "闭眼睡觉耳朵抖了一下", "闭眼睡觉", "头埋在前爪上闭眼", "趴着头抬着",
        ),
        sequence=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
        frame_ms=150,
    ),
}

DEFAULT_ACTIONS = ("idle",)
