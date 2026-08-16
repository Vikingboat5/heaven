"""开发环境快进: 把指定用户的蛋孵化值拉到 100 (跳过 2-3 天照料等待)

用法: python scripts/fastforward_hatch.py <username>
只改孵化值, 问答/孵化/生图流程全部原样保留。
"""
import sys

import psycopg

if len(sys.argv) != 2:
    print("用法: python scripts/fastforward_hatch.py <username>")
    sys.exit(1)

username = sys.argv[1]
conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/pet_paradise")
cur = conn.cursor()

cur.execute(
    "UPDATE eggs SET hatch_value = 100 "
    "WHERE owner_id = (SELECT id FROM users WHERE username = %s)",
    (username,),
)
conn.commit()

cur.execute(
    "SELECT e.id, e.hatch_value, "
    "(e.quiz_answers IS NOT NULL AND e.quiz_answers::text NOT IN ('', '{}')) AS quiz_done "
    "FROM eggs e JOIN users u ON u.id = e.owner_id WHERE u.username = %s",
    (username,),
)
rows = cur.fetchall()
conn.close()

if not rows:
    print(f"未找到用户 {username!r} 或该用户没有蛋")
    sys.exit(1)

for egg_id, hatch_value, quiz_done in rows:
    print(f"蛋 #{egg_id}: hatch_value={hatch_value}, 问答已完成={quiz_done}")
print("孵化值已就绪, 刷新首页即可看到「孵化」入口。")
