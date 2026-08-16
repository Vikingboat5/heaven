"""T2.7 内容安全 v1: 敏感词双向过滤 + 性格化兜底话术

- 输入侧: 命中则不调用 LLM(省 token), 直接返回兜底话术
- 输出侧: 流式输出用"滚动截留"检测(见 dialogue.py), 命中则整段替换
- 词表在 gamedata.SENSITIVE_WORDS, MVP 小词库; 上线前接审核 API 并扩充
"""
from .gamedata import SAFETY_FALLBACKS, SENSITIVE_WORDS

# 预计算最长敏感词长度(输出侧滚动截留窗口必须 >= 该值)
MAX_WORD_LEN = max((len(w) for w in SENSITIVE_WORDS), default=4)


def contains_sensitive(text: str) -> bool:
    """子串匹配。MVP 够用; 变体/拆字对抗交给后续审核 API。"""
    if not text:
        return False
    compact = text.replace(" ", "").replace("\n", "")
    return any(word in compact for word in SENSITIVE_WORDS)


def fallback_for(tags: list[str] | None) -> str:
    """按宠物性格标签选兜底话术"""
    for tag in tags or []:
        if tag in SAFETY_FALLBACKS:
            return SAFETY_FALLBACKS[tag]
    return SAFETY_FALLBACKS["default"]
