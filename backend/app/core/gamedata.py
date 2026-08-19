"""游戏数值配置: 物种/天赋/技能/性格标签/名字池/旅行事件库/内容安全

单人开发决策: 配置放代码模块(可版本化/可单测), 不做管理后台。
旅行事件库改这里+跑测试验证。
"""

# ---- 物种池 (按稀有度分层) ----
SPECIES_POOL: dict[str, list[dict]] = {
    "common": [
        {"id": "fox", "name": "小狐狸"},
        {"id": "rabbit", "name": "垂耳兔"},
        {"id": "cat", "name": "狸花猫"},
        {"id": "shiba", "name": "柴犬"},
    ],
    "rare": [
        {"id": "wolf", "name": "小狼"},
        {"id": "deer", "name": "梅花鹿"},
    ],
    "legendary": [
        {"id": "dragon", "name": "小青龙"},
    ],
}

# 蛋稀有度 → 物种层概率
RARITY_SPECIES_TABLE: dict[str, dict[str, float]] = {
    "normal": {"common": 1.0},
    "rare": {"common": 0.7, "rare": 0.3},
    "legendary": {"common": 0.35, "rare": 0.40, "legendary": 0.25},
}

COLORS = ["赤橙", "雪白", "青灰", "暖棕", "黛蓝", "杏黄"]

# ---- 天赋池 (被动, 按稀有度分层) ----
TALENT_POOL: dict[str, list[dict]] = {
    "common": [
        {"id": "early_bird", "name": "早起的鸟儿", "desc": "清晨探险收获+10%"},
        {"id": "good_appetite", "name": "好胃口", "desc": "旅途中更爱觅食, 常带回食物纪念品"},
        {"id": "nap_master", "name": "打盹高手", "desc": "旅途中打盹也能攒灵感(休息经验更多)"},
        {"id": "curious", "name": "好奇心", "desc": "探索新区域概率+10%"},
    ],
    "rare": [
        {"id": "night_walker", "name": "夜行者", "desc": "夜间探险收益+20%"},
        {"id": "treasure_nose", "name": "寻宝鼻", "desc": "探险发现稀有道具概率+15%"},
        {"id": "social_star", "name": "社交明星", "desc": "与其他宠物互动亲密度+25%"},
    ],
    "legendary": [
        {"id": "rainbow_luck", "name": "虹运", "desc": "所有随机收获有5%概率翻倍"},
        {"id": "soul_link", "name": "心灵感应", "desc": "能感知主人快要上线, 提前在门口等待"},
    ],
}

# ---- 技能池 (初始1个, 成长解锁更多) ----
SKILL_POOL: list[dict] = [
    {"id": "dig", "name": "刨土", "category": "adventure", "desc": "探险时有机会挖出埋藏的道具"},
    {"id": "climb", "name": "攀树", "category": "adventure", "desc": "可以到达树冠区域探险"},
    {"id": "cheer", "name": "加油打气", "category": "dialogue", "desc": "主人低落时的安慰更有效"},
    {"id": "storyteller", "name": "讲故事", "category": "dialogue", "desc": "冒险日志会更加生动"},
    {"id": "greeting", "name": "礼貌问候", "category": "social", "desc": "初次见面能给其他宠物留下好印象"},
    {"id": "gift_sense", "name": "挑礼物", "category": "social", "desc": "送出的礼物更受欢迎"},
    {"id": "forage", "name": "觅食", "category": "production", "desc": "每天有机会带回一份小食材"},
    {"id": "collect_dew", "name": "收集晨露", "category": "production", "desc": "清晨可收集晨露(合成材料)"},
]

# ---- 性格标签池 (与 persona.py 的标签文案对应) ----
PERSONALITY_TAGS = ["傲娇", "话痨", "胆小", "吃货", "高冷", "戏精"]

# ---- 推荐名字池 ----
NAME_POOL = ["团子", "糯米", "豆豆", "皮皮", "栗子", "泡芙", "可乐", "年糕", "芝麻", "雪球", "芒果", "布丁"]

# ---- 孵化配置 ----
HATCH_VALUE_TARGET = 100
CARE_VALUE = 15            # 每次照料增加的孵化值
CARE_DAILY_LIMIT = 3       # 每日照料次数上限
REGISTRATION_EGG_RARITY = "normal"  # 注册赠送蛋的稀有度(可配置)

# ================= Sprint 2 =================

EXP_PER_LEVEL = 100         # 升级所需 exp = level * 100

# ---- 旅行配置 (P4 旅行青蛙化; 出门阈值/时长见 services/adventure.py) ----
MAX_SIMULATE_HOURS = 8      # 单次模拟时长上限
ADVENTURE_TICK_MINUTES = 45 # 每个行为 tick 的时长
ADVENTURE_MAX_TICKS = 10    # 单次模拟行为数上限

ADVENTURE_ZONES: list[dict] = [
    {"id": "forest", "name": "萤火森林", "min_level": 1},
    {"id": "valley", "name": "潺潺溪谷", "min_level": 1},
    {"id": "hillside", "name": "风语山坡", "min_level": 2},
    {"id": "village", "name": "蘑菇村", "min_level": 3},
    {"id": "lake", "name": "月光湖", "min_level": 5},
]

# ---- 冒险事件库 v1 (34 条, 按区域/等级抽取; type: find_item/meet_creature/scenery/danger/treasure) ----
ADVENTURE_EVENTS: list[dict] = [
    # 萤火森林
    {"id": "f1", "zone": "forest", "type": "find_item", "text": "在萤火虫的指引下, 找到了{item}", "items": ["发光蘑菇", "浆果"], "exp": 8},
    {"id": "f2", "zone": "forest", "type": "meet_creature", "text": "遇到一只迷路的小刺猬, 把食物分给了它", "exp": 10},
    {"id": "f3", "zone": "forest", "type": "scenery", "text": "躺在蘑菇圈中间看萤火虫跳舞, 看入了迷", "exp": 5},
    {"id": "f4", "zone": "forest", "type": "find_item", "text": "在古树根部挖到了{item}", "items": ["橡果", "琥珀色的树脂"], "exp": 8},
    {"id": "f5", "zone": "forest", "type": "danger", "text": "差点被荆棘丛困住, 幸好及时跳了出来", "exp": 12},
    {"id": "f6", "zone": "forest", "type": "meet_creature", "text": "和一只松鼠比赛收集坚果, 输得心服口服", "exp": 8},
    {"id": "f7", "zone": "forest", "type": "scenery", "text": "发现一片四叶草地, 偷偷许了个愿", "exp": 6},
    {"id": "f8", "zone": "forest", "type": "treasure", "text": "拨开落叶堆, 发现了闪闪发光的{item}!", "items": ["古老铜币"], "exp": 15},
    # 潺潺溪谷
    {"id": "v1", "zone": "valley", "type": "find_item", "text": "在溪边捡到了{item}", "items": ["鹅卵石", "透明的水晶石"], "exp": 8},
    {"id": "v2", "zone": "valley", "type": "meet_creature", "text": "陪小蝌蚪找妈妈, 在水草间玩了好一会儿", "exp": 8},
    {"id": "v3", "zone": "valley", "type": "scenery", "text": "把爪子伸进清凉的溪水里, 舒服得眯起眼睛", "exp": 5},
    {"id": "v4", "zone": "valley", "type": "find_item", "text": "顺着水流追到了一片{item}", "items": ["银色鱼鳞"], "exp": 9},
    {"id": "v5", "zone": "valley", "type": "danger", "text": "踩到湿滑的青苔差点摔进溪里, 虚惊一场", "exp": 10},
    {"id": "v6", "zone": "valley", "type": "meet_creature", "text": "一只蜻蜓停在鼻尖上, 一动不动地对视了三秒", "exp": 6},
    {"id": "v7", "zone": "valley", "type": "scenery", "text": "对着溪谷的回声喊了一嗓子, 把自己吓了一跳", "exp": 5},
    {"id": "v8", "zone": "valley", "type": "treasure", "text": "在瀑布后面的石缝里发现了{item}!", "items": ["水滴吊坠"], "exp": 15},
    # 风语山坡
    {"id": "h1", "zone": "hillside", "type": "find_item", "text": "顶着大风采到了{item}", "items": ["高山野花", "风干的草药"], "exp": 9},
    {"id": "h2", "zone": "hillside", "type": "scenery", "text": "从草坡上骨碌碌滚下来, 草屑沾了满身, 但是好开心", "exp": 8},
    {"id": "h3", "zone": "hillside", "type": "meet_creature", "text": "和一只山羊对视良久, 它先移开了目光, 是我赢了", "exp": 10},
    {"id": "h4", "zone": "hillside", "type": "danger", "text": "突然下起太阳雨, 躲在大石头下面等雨停", "exp": 8},
    {"id": "h5", "zone": "hillside", "type": "find_item", "text": "在风口捡到了一根特别漂亮的{item}", "items": ["鹰的羽毛"], "exp": 10},
    {"id": "h6", "zone": "hillside", "type": "scenery", "text": "躺在山顶看云朵变成各种动物的形状", "exp": 6},
    {"id": "h7", "zone": "hillside", "type": "treasure", "text": "在石堆里翻到了{item}!", "items": ["风化的化石碎片"], "exp": 14},
    # 蘑菇村
    {"id": "m1", "zone": "village", "type": "meet_creature", "text": "蘑菇村的小精灵请我喝了露水茶", "exp": 12},
    {"id": "m2", "zone": "village", "type": "find_item", "text": "在集市角落淘到了{item}", "items": ["彩色玻璃珠", "旧纽扣"], "exp": 10},
    {"id": "m3", "zone": "village", "type": "scenery", "text": "看小精灵们排队跳房子, 忍不住加入了进去", "exp": 8},
    {"id": "m4", "zone": "village", "type": "find_item", "text": "帮老奶奶精灵捡柿子, 收到了{item}作为谢礼", "items": ["甜柿饼"], "exp": 11},
    {"id": "m5", "zone": "village", "type": "danger", "text": "差点把毒蘑菇当礼物买下来, 幸好店主拦住了我", "exp": 12},
    {"id": "m6", "zone": "village", "type": "treasure", "text": "在旧货摊底下发现了{item}!", "items": ["迷你藏宝图"], "exp": 16},
    # 月光湖
    {"id": "l1", "zone": "lake", "type": "scenery", "text": "月光洒在湖面上像撒了一层碎银, 看呆了", "exp": 10},
    {"id": "l2", "zone": "lake", "type": "meet_creature", "text": "湖里的银色大鱼跃出水面, 和我打了个招呼", "exp": 14},
    {"id": "l3", "zone": "lake", "type": "find_item", "text": "在湖边拾到了{item}", "items": ["月光贝", "珍珠母"], "exp": 12},
    {"id": "l4", "zone": "lake", "type": "danger", "text": "湖面突然起雾, 沿着岸边的灯草才找到回家的路", "exp": 14},
    {"id": "l5", "zone": "lake", "type": "treasure", "text": "湖水退潮后, 在滩涂上挖到了{item}!", "items": ["人鱼的歌谣贝壳"], "exp": 20},
]

# ---- 非探险行为模板 (行为引擎用) ----
FORAGE_EVENTS = [
    {"text": "在营地附近找到了一些{item}", "items": ["浆果", "香草", "甜根"]},
    {"text": "凭着好鼻子刨出了埋着的{item}", "items": ["橡果", "小土豆"]},
]
REST_EVENTS = ["在软软的草地上睡了一觉", "蜷成一团打了个长长的盹", "趴在树荫下休息了一会儿"]
SOCIALIZE_EVENTS = [
    "遇到了邻居家的{animal}, 一起追了一会儿蝴蝶",
    "和路过的{animal}互相闻了闻, 交换了气味名片",
    "陪{animal}玩了一阵子捉迷藏",
]
SOCIALIZE_ANIMALS = ["小猫咪", "小土狗", "垂耳兔", "小仓鼠"]
PLAY_EVENTS = ["追着自己的尾巴转了十圈", "和一片落叶搏斗了三百回合", "对着自己的影子汪汪叫阵"]

# ================= Sprint 3 =================

# ---- 诞生问答配置 (spec 4.0 初稿, 负责人审定版; 文案改动只动这里) ----
# personality 值为五维倾向增量(±15 内); tag 为性格标签倾向; species 为物种倾向(common 池)
QUIZ_QUESTIONS: list[dict] = [
    {"key": "weekend", "text": "周末的理想过法？", "type": "choice", "options": [
        {"key": "social", "text": "约朋友去热闹的地方",
         "personality": {"extraversion": 15, "openness": 5}},
        {"key": "explore", "text": "一个人探索没去过的角落",
         "personality": {"openness": 15, "extraversion": -5}},
        {"key": "home", "text": "宅在家睡到自然醒",
         "personality": {"extraversion": -10, "stability": 10}},
        {"key": "organize", "text": "把没做完的事安排妥当",
         "personality": {"conscientiousness": 15}},
    ]},
    {"key": "friends_say", "text": "朋友一般怎么形容你？", "type": "choice", "options": [
        {"key": "talkative", "text": "话多热情小太阳", "tag": "话痨"},
        {"key": "quiet", "text": "安静但靠谱", "tag": "高冷"},
        {"key": "dramatic", "text": "戏很多的开心果", "tag": "戏精"},
        {"key": "gentle", "text": "温柔好脾气", "tag": "吃货"},
    ]},
    {"key": "species", "text": "希望它是什么小家伙？", "type": "choice", "options": [
        {"key": "fox", "text": "狐狸系", "species": "fox"},
        {"key": "cat", "text": "猫咪系", "species": "cat"},
        {"key": "rabbit", "text": "兔兔系", "species": "rabbit"},
        {"key": "dog", "text": "狗狗系", "species": "shiba"},
        {"key": "fate", "text": "交给缘分", "species": None},
    ]},
    {"key": "style", "text": "喜欢什么画风？", "type": "choice", "options": [
        {"key": "illustration", "text": "手绘童话插画风", "style": "illustration"},
        {"key": "pixel", "text": "复古像素游戏风", "style": "pixel"},
        {"key": "fate", "text": "交给缘分", "style": None},
    ]},
    # choice_or_text: 可选快捷项也可手动输入(≤10字符, 敏感词过滤, 无效回退暖橙)
    {"key": "color", "text": "希望它是什么色系？", "type": "choice_or_text",
     "max_len": 10, "fallback": "暖橙", "options": [
        {"key": "warm_orange", "text": "暖橙", "color": "暖橙"},
        {"key": "green", "text": "翠绿", "color": "翠绿"},
        {"key": "blue", "text": "黛蓝", "color": "黛蓝"},
        {"key": "pink", "text": "樱粉", "color": "樱粉"},
    ]},
    # text: 可跳过的自由输入; 孵化时 LLM 转译为外观特征词(原名不进 prompt)
    {"key": "ip", "text": "有特别喜欢的角色吗？游戏/动漫/神话都可以",
     "type": "text", "optional": True, "max_len": 30},
]


# ---- 内容安全 v1 (敏感词表, MVP 小词库; 上线前接审核 API 并扩充) ----
SENSITIVE_WORDS: list[str] = [
    # 政治敏感(示例少量, 生产以审核服务为准)
    "煽动颠覆", "分裂国家", "恐怖主义",
    # 色情
    "约炮", "裸聊", "色情", "援交",
    # 暴力/自伤
    "自杀", "自残", "杀了你", "制造炸弹", "毒品",
    # 违法
    "赌博", "诈骗", "洗钱",
]

# 性格化兜底话术(命中敏感词时使用, 不破坏角色感)
SAFETY_FALLBACKS: dict[str, str] = {
    "傲娇": "哼, 才、才不想聊这个呢……说点别的嘛!",
    "话痨": "哎呀哎呀, 这个话题可不行哦! 我们聊点别的吧, 比如你今天吃了什么好吃的?",
    "胆小": "(往你身后缩了缩) 这、这个话题有点可怕……我们换个开心点的话题吧?",
    "吃货": "唔, 聊这个不如聊聊吃的! 你今天吃好吃的了吗?",
    "高冷": "……不聊这个。换个话题。",
    "戏精": "(夸张地捂住耳朵) 不听不听! 这种话题配不上本大明星! 换一个!",
    "default": "(摇摇头) 人家不想聊这个嘛……我们换个话题吧?",
}
