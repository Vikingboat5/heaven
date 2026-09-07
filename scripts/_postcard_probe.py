"""一次性: 明信片探针账号 (postcard_probe) 首趟旅行结算, 验证 H8 明信片链路"""
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

BASE = "http://localhost:8000"
PG = "postgresql://postgres:postgres@localhost:5432/pet_paradise"
USER = "postcard_probe"
PWD = "probe123456"

c = httpx.Client(base_url=BASE, timeout=30)
r = c.post("/api/auth/register", json={"username": USER, "password": PWD})
if r.status_code >= 400:
    r = c.post("/api/auth/login", json={"username": USER, "password": PWD})
r.raise_for_status()
auth = {"Authorization": f"Bearer {r.json()['token']}"}
print(f"账号就绪: {USER}")

egg = c.get("/api/eggs/current", headers=auth).json()
if egg and not egg.get("quiz_done"):
    qs = c.get("/api/quiz", headers=auth).json()
    qlist = qs if isinstance(qs, list) else qs.get("questions", [])
    answers = {q["key"]: q["options"][0]["key"] for q in qlist if q.get("options")}
    c.post("/api/eggs/quiz", json={"answers": answers}, headers=auth).raise_for_status()
    print(f"问答已提交: {len(answers)} 题")

conn = psycopg.connect(PG)
cur = conn.cursor()
cur.execute("UPDATE eggs SET hatch_value = 100 WHERE owner_id = (SELECT id FROM users WHERE username = %s)", (USER,))
conn.commit()
conn.close()

pet = c.get("/api/pets/me", headers=auth).json()
if not pet:
    r = c.post("/api/eggs/hatch", json={"name": "片片"}, headers=auth)
    r.raise_for_status()
    pet = r.json()
    print(f"孵化: {pet['name']} (id={pet['id']})")
else:
    print(f"已有宠物: {pet['name']} (id={pet['id']})")

now = datetime.utcnow()
seed = sys.argv[1] if len(sys.argv) > 1 else "myth:moon_palace"
dest = {"myth:moon_palace": "月宫", "field:valley": "潺潺溪谷", "field:forest": "萤火森林",
        "field:hillside": "风语山坡", "field:village": "蘑菇村"}.get(seed, seed)
travel = {"left_at": (now - timedelta(hours=3)).isoformat(),
          "back_at": (now - timedelta(minutes=1)).isoformat(),
          "dest": dest, "seed": seed}
conn = psycopg.connect(PG)
cur = conn.cursor()
cur.execute("UPDATE pets SET travel = %s::jsonb WHERE id = %s", (json.dumps(travel), pet["id"]))
conn.commit()
conn.close()
print("到期旅行已设")

r = c.get("/api/adventure/check", headers=auth).json()
print("check event:", r.get("event"))
log_id = (r.get("log") or {}).get("id")
pending = ((r.get("log") or {}).get("rewards") or {}).get("postcard_pending")
print(f"log#{log_id} postcard_pending={pending}")

if pending:
    print("等待明信片生成 (最多 180s)...", flush=True)
    deadline = time.time() + 180
    while time.time() < deadline:
        time.sleep(10)
        logs = c.get("/api/adventure/logs", headers=auth).json()["logs"]
        pc = (logs[0]["rewards"] or {}).get("postcard") if logs else None
        if pc:
            print(f"明信片已生成: {pc}")
            img = httpx.get(f"{BASE}{pc}", timeout=30)
            print(f"图片可访问: HTTP {img.status_code}, {len(img.content) // 1024}KB")
            break
    else:
        print("超时未生成!")
