"""回填图鉴解锁记录 (collection): 从当前背包 + 历史日志 rewards.items 汇总
2026-09-12 collection 列上线前的存量数据迁移
"""
import json

import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/pet_paradise")
cur = conn.cursor()
cur.execute("SELECT id, inventory FROM pets")
pets = cur.fetchall()
cur.execute("SELECT pet_id, rewards FROM adventure_logs")
logs = cur.fetchall()
by_pet: dict[int, set] = {}
for pet_id, rewards in logs:
    for e in (rewards or {}).get("items", []):
        iid = e.get("item") if isinstance(e, dict) else str(e)
        by_pet.setdefault(pet_id, set()).add(iid)
for pet_id, inv in pets:
    coll = by_pet.get(pet_id, set())
    for e in inv or []:
        coll.add(e.get("item"))
    cur.execute("UPDATE pets SET collection = %s::jsonb WHERE id = %s",
                (json.dumps(sorted(coll), ensure_ascii=False), pet_id))
    print(f"pet#{pet_id}: collection 回填 {len(coll)} 件")
conn.commit()
conn.close()
