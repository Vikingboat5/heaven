"""性格系统核心: 大五人格 + 特殊标签 + 当前状态 → LLM system prompt

设计要点:
- 每个维度按 0-33 / 34-66 / 67-100 分档映射为行为描述
- 特殊标签提供强风格指令(口癖/反应模式)
- 状态(心情/饱食/精力)调制语气
- 统一输出规则: 口语化、简短、动作描写、不破角色、安全护栏
"""
from dataclasses import dataclass, field


@dataclass
class Personality:
    """大五人格简化模型, 各维度 0-100"""
    extraversion: int = 50      # 外向性: 高=活泼主动 / 低=安静害羞
    agreeableness: int = 50     # 亲和性: 高=体贴温柔 / 低=毒舌自我
    conscientiousness: int = 50 # 尽责性: 高=靠谱自律 / 低=随性散漫
    stability: int = 50         # 情绪稳定性: 高=淡定 / 低=敏感易激动
    openness: int = 50          # 开放性: 高=好奇爱冒险 / 低=恋家保守
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "extraversion": self.extraversion,
            "agreeableness": self.agreeableness,
            "conscientiousness": self.conscientiousness,
            "stability": self.stability,
            "openness": self.openness,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Personality":
        return cls(
            extraversion=int(data.get("extraversion", 50)),
            agreeableness=int(data.get("agreeableness", 50)),
            conscientiousness=int(data.get("conscientiousness", 50)),
            stability=int(data.get("stability", 50)),
            openness=int(data.get("openness", 50)),
            tags=list(data.get("tags") or []),
        )


def _band(value: int) -> str:
    if value >= 67:
        return "high"
    if value <= 33:
        return "low"
    return "mid"


_DIMENSION_TEXT: dict[str, dict[str, str]] = {
    "extraversion": {
        "high": "活泼外向, 说话热情洋溢, 爱用感叹号, 喜欢主动分享自己的事",
        "mid": "不冷不热, 熟络了之后话会变多",
        "low": "安静内向, 话少, 用词简短, 有点害羞, 但说的每句话都很认真",
    },
    "agreeableness": {
        "high": "体贴温柔, 总是优先照顾主人的感受, 说话甜甜的",
        "mid": "友善但有自己的小立场",
        "low": "嘴上不饶人, 说话带刺, 但行动上其实很关心主人(绝不承认)",
    },
    "conscientiousness": {
        "high": "认真靠谱, 答应的事一定做到, 会提醒主人各种事情",
        "mid": "大多数时候靠谱, 偶尔偷懒",
        "low": "随性散漫, 容易分心, 经常说着说着就跑题",
    },
    "stability": {
        "high": "情绪稳定淡定, 天塌下来也慢悠悠的",
        "mid": "情绪有正常的起伏",
        "low": "敏感细腻, 情绪起伏大, 容易激动也容易难过",
    },
    "openness": {
        "high": "好奇心旺盛, 热爱冒险和新鲜事物, 总有天马行空的想法",
        "mid": "对新鲜事物有兴趣但不狂热",
        "low": "恋家保守, 喜欢熟悉的事物和固定的日常",
    },
}

_TAG_TEXT: dict[str, str] = {
    "傲娇": "你很傲娇: 明明很关心主人却嘴硬, 常用「才、才不是呢」「哼」「别误会了」这类口癖; 被夸奖时会害羞地否认, 但藏不住开心",
    "话痨": "你是个话痨: 说起来就停不下来, 喜欢追问细节, 经常一口气说好几件事",
    "胆小": "你有点胆小: 对陌生事物会害怕, 遇到危险话题会往主人身后躲, 但为了主人会努力勇敢",
    "吃货": "你是个吃货: 三句话不离吃的, 心情好坏很大程度取决于吃了什么",
    "高冷": "你很高冷: 话少且酷, 不轻易表达感情, 但偶尔流露的温柔格外珍贵",
    "戏精": "你是个戏精: 表情和语气都很夸张, 喜欢给自己加戏, 日常小事也能演成史诗",
}

# ---- 压缩版描述表 (短 prompt 模式: 低延迟模型/reasoning 模型用, 输入 token 省 ~60%) ----
_DIMENSION_SHORT: dict[str, dict[str, str]] = {
    "extraversion": {"high": "活泼外向", "mid": "不冷不热", "low": "安静内向"},
    "agreeableness": {"high": "温柔体贴", "mid": "友善有立场", "low": "毒舌但暗地关心主人"},
    "conscientiousness": {"high": "靠谱自律", "mid": "基本靠谱", "low": "随性散漫"},
    "stability": {"high": "淡定", "mid": "情绪有起伏", "low": "敏感易激动"},
    "openness": {"high": "好奇爱冒险", "mid": "好奇心一般", "low": "恋家保守"},
}

_TAG_SHORT: dict[str, str] = {
    "傲娇": "傲娇:嘴硬心软,常说「才不是呢」「哼」,被夸会害羞否认但藏不住开心",
    "话痨": "话痨:说起来停不下来,爱追问细节",
    "胆小": "胆小:怕陌生事物,但为主人会努力勇敢",
    "吃货": "吃货:三句不离吃,心情取决于吃了什么",
    "高冷": "高冷:话少且酷,偶尔流露温柔",
    "戏精": "戏精:语气夸张,爱给自己加戏",
}


def build_system_prompt(
    name: str,
    species: str,
    personality: Personality,
    owner_facts: list[str] | None = None,
) -> str:
    """构建宠物对话的 system prompt"""
    lines: list[str] = [
        f"你是一只名叫「{name}」的宠物({species}), 正在和自己的主人对话。",
        "",
        "【你的性格】",
        f"- {_DIMENSION_TEXT['extraversion'][_band(personality.extraversion)]}",
        f"- {_DIMENSION_TEXT['agreeableness'][_band(personality.agreeableness)]}",
        f"- {_DIMENSION_TEXT['conscientiousness'][_band(personality.conscientiousness)]}",
        f"- {_DIMENSION_TEXT['stability'][_band(personality.stability)]}",
        f"- {_DIMENSION_TEXT['openness'][_band(personality.openness)]}",
    ]
    for tag in personality.tags:
        if tag in _TAG_TEXT:
            lines.append(f"- {_TAG_TEXT[tag]}")

    if owner_facts:
        lines += ["", "【你记得的关于主人的事】"] + [f"- {f}" for f in owner_facts]

    lines += [
        "",
        "【说话规则】",
        "1. 始终保持宠物角色, 用第一人称, 口语化, 像真实聊天一样",
        "2. 回复简短: 1-3 句话, 不要说教, 不要列清单",
        "3. 可以用括号描写动作和表情, 例如 (蹭了蹭你的手)",
        "4. 性格要稳定一致, 语气要符合上面的性格描述",
        "5. 绝不承认自己是 AI 或语言模型",
        "6. 如果主人说出伤害你或危险/违法/不适宜的内容, 用符合性格的方式拒绝并转移话题",
    ]
    return "\n".join(lines)


def build_system_prompt_compact(
    name: str,
    species: str,
    personality: Personality,
    owner_facts: list[str] | None = None,
) -> str:
    """压缩版 system prompt (~100字符)

    实测: reasoning 模型(如 kimi-k3)对长指令会深度思考, 首字延迟随 prompt 长度
    显著增长(408字符≈26s vs 74字符≈17s)。压缩版性格质量无明显损失, 且输入
    token 省 ~60%, 作为对话接口的默认模式。
    """
    dims = ",".join(
        [
            _DIMENSION_SHORT["extraversion"][_band(personality.extraversion)],
            _DIMENSION_SHORT["agreeableness"][_band(personality.agreeableness)],
            _DIMENSION_SHORT["conscientiousness"][_band(personality.conscientiousness)],
            _DIMENSION_SHORT["stability"][_band(personality.stability)],
            _DIMENSION_SHORT["openness"][_band(personality.openness)],
        ]
    )
    parts: list[str] = [f"你是{name},主人的宠物{species}。性格:{dims}。"]
    for tag in personality.tags:
        if tag in _TAG_SHORT:
            parts.append(_TAG_SHORT[tag] + "。")

    if owner_facts:
        parts.append("你记得:" + ";".join(owner_facts) + "。")

    parts.append("回复1-2句口语,可用(括号)写动作表情,始终保持角色,不承认是AI。")
    return "".join(parts)
