"""查 H10 记忆卡状态 + 最新信件 (E2E 验证)"""
import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/pet_paradise")
cur = conn.cursor()
cur.execute("SELECT seed_id, memory, visit_count FROM pet_seed_memories WHERE pet_id = 28")
for r in cur.fetchall():
    print(f"记忆卡[{r[0]}]: {r[1][:90]} | 次数: {r[2]}")
cur.execute("SELECT narrative FROM adventure_logs WHERE pet_id = 28 ORDER BY id DESC LIMIT 1")
print()
print("=== 最新信件 ===")
print(cur.fetchone()[0])
conn.close()
