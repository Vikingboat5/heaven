"""诞生问答服务 (spec 4.0): 答案校验/清洗 + 生成倾向构建

答案存在 Egg.quiz_answers, 孵化时构建 QuizBias 注入种子化生成;
style/color/ip 供 petgen 管线组装外观 prompt (S3.3)。
"""
from __future__ import annotations

from ..core.gamedata import QUIZ_QUESTIONS
from ..core.safety import contains_sensitive
from .generation import QuizBias

_QUESTIONS = {q["key"]: q for q in QUIZ_QUESTIONS}
_OPTIONS = {q["key"]: {o["key"]: o for o in q.get("options", [])}
            for q in QUIZ_QUESTIONS}


class QuizError(Exception):
    """业务异常: detail 直接返回给前端"""


def validate_answers(raw: dict) -> dict:
    """校验并清洗问答答案。未知题目/非法选项忽略; 文本题截断+敏感词回退"""
    if not isinstance(raw, dict):
        raise QuizError("答案格式不正确")
    clean: dict = {}
    for key, value in raw.items():
        q = _QUESTIONS.get(key)
        if not q:
            continue
        qtype = q["type"]
        if qtype == "choice":
            if value in _OPTIONS[key]:
                clean[key] = value
        elif qtype == "choice_or_text":
            if value in _OPTIONS[key]:
                clean[key] = value
            elif isinstance(value, str):
                text = value.strip()[: q["max_len"]]
                # 手动输入: 空/敏感 → 回退默认色系
                clean[key] = text if text and not contains_sensitive(text) \
                    else q["fallback"]
        elif qtype == "text":
            if isinstance(value, str):
                text = value.strip()[: q["max_len"]]
                if text and not contains_sensitive(text):
                    clean[key] = text
    return clean


def build_bias(answers: dict) -> QuizBias:
    """问答答案 → 生成倾向 (性格/标签/物种)"""
    personality: dict = {}
    tag = None
    species_id = None
    for key, value in answers.items():
        opt = _OPTIONS.get(key, {}).get(value)
        if not opt:
            continue
        for dim, delta in (opt.get("personality") or {}).items():
            personality[dim] = max(-15, min(15, personality.get(dim, 0) + delta))
        tag = tag or opt.get("tag")
        species_id = species_id or opt.get("species")
    return QuizBias(personality=personality or None, tag=tag, species_id=species_id)


def resolve_style(answers: dict) -> str | None:
    """画风路由: 返回 StyleProfile key; 未选/缘分 → None(由孵化种子决定)"""
    opt = _OPTIONS.get("style", {}).get(answers.get("style") or "")
    return (opt or {}).get("style")


def resolve_color(answers: dict) -> str:
    """色系: 快捷选项映射或手动输入文本(已清洗)"""
    key = answers.get("color")
    opt = _OPTIONS.get("color", {}).get(key or "")
    if opt:
        return opt["color"]
    if isinstance(key, str) and key:
        return key
    return "暖橙"
