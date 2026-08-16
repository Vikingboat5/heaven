"""查看单个宠物的形象状态 (用法: python scripts/pet_status.py <pet_id>)"""
import sys

import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/pet_paradise")
cur = conn.cursor()
cur.execute(
    "SELECT id, owner_id, name, species, color, sprite_status, sprite_style, appearance "
    "FROM pets WHERE id = %s",
    (int(sys.argv[1]),),
)
for row in cur.fetchall():
    print(row)
conn.close()
