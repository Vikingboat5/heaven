"""S3.1 生成管线测试: 金样本离线切帧(零 token) + prompt 构建

金样本 = docs/demo/ 下已验收的精灵表原图, 管线改动后重跑防劣化。
"""
from pathlib import Path

import pytest

from backend.app.services.petgen import (
    ACTION_TEMPLATES,
    STYLE_PROFILES,
    build_prompt,
    process_sheet,
)

GOLDEN = Path(__file__).resolve().parents[2] / "docs" / "demo"


@pytest.mark.skipif(not (GOLDEN / "sheet12" / "sheet12_raw.jpg").exists(),
                    reason="金样本不在本机(docs/demo)")
def test_illustration_idle_golden():
    # 金样本: 2026-09 帧数实验的 12 帧精灵表 (4x3), 目检验收见 contact.png
    frames, qc = process_sheet(GOLDEN / "sheet12" / "sheet12_raw.jpg",
                               ACTION_TEMPLATES["idle"],
                               STYLE_PROFILES["illustration"])
    assert len(frames) == 12
    assert qc["passed"], f"插画风金样本质检失败: {qc}"


@pytest.mark.skipif(not (GOLDEN / "pixel" / "pixel_raw.jpg").exists(),
                    reason="金样本不在本机(docs/demo)")
def test_pixel_wave_golden():
    frames, qc = process_sheet(GOLDEN / "pixel" / "pixel_raw.jpg",
                               ACTION_TEMPLATES["wave"],
                               STYLE_PROFILES["pixel"])
    assert len(frames) == 8
    assert qc["passed"], f"像素风金样本质检失败: {qc}"


def test_build_prompt_structure():
    p = build_prompt(ACTION_TEMPLATES["idle"], "一只橙色小狐狸",
                     STYLE_PROFILES["pixel"])
    # 必备约束: 网格/逐帧顺序/外观/风格/白底强硬约束
    assert "4列3行" in p and "12个动画关键帧" in p
    assert "从左到右、从上到下" in p
    assert "一只橙色小狐狸" in p
    assert "像素" in p
    assert "纯白色背景" in p and "无网格线" in p
    # 12 帧姿势描述全部注入
    for i in range(1, 13):
        assert f"第{i}帧" in p
