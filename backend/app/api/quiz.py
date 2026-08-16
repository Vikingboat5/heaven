"""诞生问答接口: 获取题目配置"""
from fastapi import APIRouter

from ..core.gamedata import QUIZ_QUESTIONS

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


@router.get("")
def get_quiz():
    """返回问答题配置(文案/选项/类型)。映射字段(personality/tag/species)不下发"""
    return [
        {"key": q["key"], "text": q["text"], "type": q["type"],
         "optional": q.get("optional", False),
         "max_len": q.get("max_len"),
         "options": [{"key": o["key"], "text": o["text"]} for o in q.get("options", [])]}
        for q in QUIZ_QUESTIONS
    ]
