"""清理临时探针账号 (开发环境用)"""
import sys

import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/pet_paradise")
cur = conn.cursor()

for username in sys.argv[1:]:
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    if not row:
        print(f"{username}: 不存在")
        continue
    uid = row[0]
    # 按外键依赖顺序删除 (chat_messages 挂 pet_id)
    cur.execute("DELETE FROM chat_messages WHERE pet_id IN (SELECT id FROM pets WHERE owner_id = %s)", (uid,))
    cur.execute("DELETE FROM fact_memories WHERE pet_id IN (SELECT id FROM pets WHERE owner_id = %s)", (uid,))
    cur.execute("DELETE FROM adventure_logs WHERE pet_id IN (SELECT id FROM pets WHERE owner_id = %s)", (uid,))
    cur.execute("DELETE FROM pets WHERE owner_id = %s", (uid,))
    cur.execute("DELETE FROM user_task_progress WHERE user_id = %s", (uid,))
    cur.execute("DELETE FROM eggs WHERE owner_id = %s", (uid,))
    cur.execute("DELETE FROM users WHERE id = %s", (uid,))
    conn.commit()
    print(f"{username}: 已清理")
conn.close()
