"""查 e2e_ui_probe 名下的宠物和日志归属 (日记里出现'咿呀'署名的排查)"""
import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/pet_paradise")
cur = conn.cursor()
cur.execute("SELECT id, name, owner_id, level FROM pets WHERE owner_id = 32 ORDER BY id")
print("owner=32 的宠物:")
for r in cur.fetchall():
    print(f"  pet#{r[0]} {r[1]} Lv.{r[3]}")
cur.execute("SELECT pet_id, COUNT(*) FROM adventure_logs GROUP BY pet_id ORDER BY pet_id")
print("日志归属:")
for r in cur.fetchall():
    print(f"  pet#{r[0]}: {r[1]} 条")
cur.execute("SELECT id, narrative FROM adventure_logs WHERE pet_id = 28 ORDER BY id DESC LIMIT 3")
print("pet28 最新日志署名检查:")
for r in cur.fetchall():
    tail = (r[1] or "")[-16:].replace("\n", " ")
    print(f"  log#{r[0]} ...{tail}")
conn.close()
