"""查所有待生成明信片并补跑 (pet28 的月光湖明信片曾 pending 卡住)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import psycopg  # noqa: E402

from app.services.postcard import _generate  # noqa: E402

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/pet_paradise")
cur = conn.cursor()
cur.execute(
    "SELECT id, pet_id FROM adventure_logs "
    "WHERE rewards->>'postcard_pending' = 'true' AND rewards->>'postcard' IS NULL"
)
rows = cur.fetchall()
print(f"待补跑: {rows}")
for log_id, pet_id in rows:
    print(f"补跑 log#{log_id} pet#{pet_id}")
    _generate(log_id, pet_id)
conn.close()
print("完成")
