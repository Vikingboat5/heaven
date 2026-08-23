"""E2E 布景脚本 (W1 UI 走查用): 注册探针 → 问答 → 快进孵化 → 塞背包物品 + 到期旅行

用法: python scripts/e2e_setup_w1.py [--cleanup]
前置: 后端跑在 :8000, PostgreSQL 在 :5432。
完成后用 e2e_ui_probe / probe123456 登录前端, 首页应出现归来信封。
"""
import json
import sys
from datetime import datetime, timedelta

import httpx
import psycopg

BASE = "http://localhost:8000"
USER = "e2e_ui_probe"
PWD = "probe123456"
PG = "postgresql://postgres:postgres@localhost:5432/pet_paradise"


def cleanup() -> None:
    conn = psycopg.connect(PG)
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username = %s", (USER,))  # 级联删宠物/蛋/日志
    conn.commit()
    conn.close()
    print(f"探针账号 {USER} 已清理")


def main() -> None:
    if "--cleanup" in sys.argv:
        cleanup()
        return

    c = httpx.Client(base_url=BASE, timeout=30)
    r = c.post("/api/auth/register", json={"username": USER, "password": PWD})
    if r.status_code >= 400:  # 已存在 → 登录
        r = c.post("/api/auth/login", json={"username": USER, "password": PWD})
    r.raise_for_status()
    token = r.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    print(f"账号就绪: {USER}")

    # 问答: 每题选第一个选项
    egg = c.get("/api/eggs/current", headers=auth).json()
    if egg and not egg.get("quiz_done"):
        questions = c.get("/api/quiz", headers=auth).json()
        qlist = questions if isinstance(questions, list) else questions.get("questions", [])
        answers = {}
        for q in qlist:
            opts = q.get("options") or []
            if opts:
                answers[q["key"]] = opts[0]["key"]
        c.post("/api/eggs/quiz", json={"answers": answers}, headers=auth).raise_for_status()
        print(f"问答已提交: {len(answers)} 题")

    # 快进孵化值 + 孵化
    conn = psycopg.connect(PG)
    cur = conn.cursor()
    cur.execute("UPDATE eggs SET hatch_value = 100 WHERE owner_id = (SELECT id FROM users WHERE username = %s)", (USER,))
    conn.commit()
    pet = c.get("/api/pets/me", headers=auth).json()
    if not pet:
        r = c.post("/api/eggs/hatch", json={"name": "探探"}, headers=auth)
        r.raise_for_status()
        pet = r.json()
        print(f"孵化成功: {pet['name']} (id={pet['id']})")
    else:
        print(f"已有宠物: {pet['name']} (id={pet['id']})")

    # 塞背包物品(覆盖三品级+三行囊属性) + 构造到期旅行(月宫, 带伴手礼)
    now = datetime.utcnow()
    inventory = [
        {"item": "osmanthus_cake", "count": 2, "acquired_at": now.isoformat(timespec="minutes"),
         "acquired_zone": "myth:moon_palace", "acquired_via": "forage", "is_new": True},
        {"item": "silver_fish_scale", "count": 1, "acquired_at": now.isoformat(timespec="minutes"),
         "acquired_zone": "field:valley", "acquired_via": "forage", "is_new": True},
        {"item": "moonstone", "count": 1, "acquired_at": now.isoformat(timespec="minutes"),
         "acquired_zone": "myth:moon_palace", "acquired_via": "forage", "is_new": True},
        {"item": "star_sand", "count": 3, "acquired_at": now.isoformat(timespec="minutes"),
         "acquired_zone": "myth:moon_palace", "acquired_via": "exchange", "is_new": False},
    ]
    travel = {
        "left_at": (now - timedelta(hours=3)).isoformat(),
        "back_at": (now - timedelta(minutes=1)).isoformat(),
        "dest": "月宫",
        "seed": "myth:moon_palace",
    }
    cur.execute(
        "UPDATE pets SET inventory = %s::jsonb, travel = %s::jsonb, loadout = %s::jsonb "
        "WHERE owner_id = (SELECT id FROM users WHERE username = %s)",
        (json.dumps(inventory, ensure_ascii=False), json.dumps(travel, ensure_ascii=False),
         json.dumps({"gift": "silver_fish_scale"}), USER),
    )
    conn.commit()
    conn.close()
    print("背包已塞 4 件物品(含 NEW), 月宫旅行已到期, 行囊带伴手礼·银色鱼鳞")
    print(f"→ 前端用 {USER} / {PWD} 登录, 首页会出现归来信封")
    print(f"TOKEN={token}")


if __name__ == "__main__":
    main()
