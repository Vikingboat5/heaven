"""只读检查: 当前用户/蛋/宠物状态 (供体验全流程前确认)"""
import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/pet_paradise")
cur = conn.cursor()

cur.execute("SELECT id, username, created_at FROM users ORDER BY id")
print("USERS:", cur.fetchall())

cur.execute(
    "SELECT id, owner_id, rarity, hatch_value, created_at, "
    "(quiz_answers IS NOT NULL AND quiz_answers::text NOT IN ('', '{}')) AS quiz_done "
    "FROM eggs ORDER BY id"
)
print("EGGS:", cur.fetchall())

cur.execute("SELECT id, owner_id, name, species, sprite_status, sprite_style FROM pets ORDER BY id")
print("PETS:", cur.fetchall())

cur.execute("SELECT COUNT(*) FROM chat_messages")
print("CHAT_MSGS:", cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM adventure_logs")
print("ADV_LOGS:", cur.fetchone()[0])

conn.close()
