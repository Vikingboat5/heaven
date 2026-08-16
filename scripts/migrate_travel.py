"""补真实 PG 表结构: 新增 travel 列 (P4 旅行状态机)"""
import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/pet_paradise")
cur = conn.cursor()
cur.execute("ALTER TABLE pets ADD COLUMN IF NOT EXISTS travel JSON NOT NULL DEFAULT '{}'::json")
conn.commit()
print("travel column ready")
conn.close()
