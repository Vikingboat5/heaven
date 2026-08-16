"""S3.2 诞生问答测试: 答案清洗 / 倾向构建 / 生成注入 / API"""
from backend.app.services.generation import QuizBias, generate_pet
from backend.app.services.quiz import (
    build_bias,
    resolve_color,
    resolve_style,
    validate_answers,
)


# ---- 答案清洗 ----

def test_validate_choice_and_ignore_unknown():
    clean = validate_answers({"weekend": "social", "hack": "x", "species": "badopt"})
    assert clean == {"weekend": "social"}  # 未知题/非法选项被忽略


def test_validate_manual_color_kept_and_sanitized():
    assert validate_answers({"color": "薄荷绿"})["color"] == "薄荷绿"
    assert validate_answers({"color": "暖橙"})["color"] == "暖橙"  # 快捷项
    # 敏感词回退默认
    assert validate_answers({"color": "赌博网站"})["color"] == "暖橙"
    # 超长截断
    assert len(validate_answers({"color": "x" * 30})["color"]) == 10


def test_validate_ip_text():
    assert validate_answers({"ip": "皮卡丘"})["ip"] == "皮卡丘"
    assert "ip" not in validate_answers({"ip": "  "})  # 空白忽略
    assert "ip" not in validate_answers({"ip": "自杀"})  # 敏感忽略


# ---- 倾向构建 ----

def test_build_bias_mapping():
    bias = build_bias({"weekend": "social", "friends_say": "talkative", "species": "fox"})
    assert bias.personality == {"extraversion": 15, "openness": 5}
    assert bias.tag == "话痨"
    assert bias.species_id == "fox"


def test_resolve_style_and_color():
    assert resolve_style({"style": "pixel"}) == "pixel"
    assert resolve_style({"style": "fate"}) is None
    assert resolve_color({"color": "green"}) == "翠绿"
    assert resolve_color({"color": "奶茶色"}) == "奶茶色"
    assert resolve_color({}) == "暖橙"


# ---- 生成注入 ----

def test_generation_with_bias_deterministic():
    bias = QuizBias(personality={"extraversion": 15}, tag="话痨", species_id="fox")
    p1 = generate_pet(seed="s1", bias=bias)
    p2 = generate_pet(seed="s1", bias=bias)
    assert p1.to_dict() == p2.to_dict()
    assert p1.species_id == "fox"           # 物种倾向生效
    assert p1.personality["tags"][0] == "话痨"  # 标签置首


def test_generation_bias_species_ignored_when_not_in_pool():
    # 稀有层池没有 fox 时回退池内随机(倾向不破坏稀有度规则)
    bias = QuizBias(species_id="dragon")
    p = generate_pet(seed="s1", rarity="normal", bias=bias)
    assert p.species_id in ("fox", "rabbit", "cat", "shiba")


# ---- API ----

def test_quiz_api_structure(api_client):
    resp = api_client.get("/api/quiz")
    assert resp.status_code == 200
    questions = resp.json()
    assert len(questions) == 6
    color_q = next(q for q in questions if q["key"] == "color")
    assert color_q["type"] == "choice_or_text"
    # 映射字段不下发
    assert "personality" not in questions[0]["options"][0]


def test_submit_quiz_and_hatch_with_bias(api_client, db):
    token = api_client.post("/api/auth/register",
                            json={"username": "quizzer", "password": "pass123"}).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}

    resp = api_client.post("/api/eggs/quiz", json={"answers": {
        "weekend": "social", "friends_say": "talkative",
        "species": "fox", "style": "pixel", "color": "薄荷绿",
    }}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["quiz_done"] is True

    # 灌满孵化值后孵化, 验证倾向注入
    from backend.app.models import Egg
    egg = db.query(Egg).filter(Egg.owner_id == 1).first()
    assert egg.quiz_answers["color"] == "薄荷绿"
    egg.hatch_value = 100
    db.commit()
    pet = api_client.post("/api/eggs/hatch", json={}, headers=auth).json()
    assert pet["species"] == "小狐狸"
    assert pet["personality"]["tags"][0] == "话痨"
