"""查明信片记录 vs 文件"""
import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/pet_paradise")
cur = conn.cursor()
cur.execute("SELECT id, rewards->>'postcard' AS pc FROM adventure_logs WHERE pet_id = 28 AND rewards->>'postcard' IS NOT NULL")
rows = cur.fetchall()
print(f"DB 里有明信片的日志: {len(rows)} 条")
for r in rows:
    print(" ", r)
cur.execute("SELECT id, rewards->>'postcard_pending' FROM adventure_logs WHERE pet_id = 28 AND rewards->>'postcard_pending' = 'true'")
print(f"pending 未生成: {cur.fetchall()}")
conn.close()
