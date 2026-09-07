"""查 pet29 最近日志的明信片状态"""
import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/pet_paradise")
cur = conn.cursor()
cur.execute(
    "SELECT id, rewards->>'seed' AS seed, rewards->>'postcard' AS pc, "
    "rewards->>'postcard_pending' AS pp FROM adventure_logs WHERE pet_id=29 ORDER BY id DESC LIMIT 3"
)
for r in cur.fetchall():
    print(f"log#{r[0]} seed={r[1]} postcard={r[2]} pending={r[3]}")
conn.close()
