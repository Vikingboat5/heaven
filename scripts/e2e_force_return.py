"""E2E 辅助: 把探针宠物的旅行改为已到期 (触发归来结算→信封)
用法: python scripts/e2e_force_return.py [username] [seed_id]
"""
import json
import sys
from datetime import datetime, timedelta

import psycopg

USER = sys.argv[1] if len(sys.argv) > 1 else "e2e_ui_probe"
SEED = sys.argv[2] if len(sys.argv) > 2 else "myth:moon_palace"

sys.path.insert(0, ".")
from backend.app.core import catalog  # noqa: E402

seed = catalog.SEEDS[SEED]
now = datetime.utcnow()
travel = {
    "left_at": (now - timedelta(hours=3)).isoformat(),
    "back_at": (now - timedelta(minutes=1)).isoformat(),
    "dest": seed["name"],
    "seed": SEED,
}
conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/pet_paradise")
cur = conn.cursor()
cur.execute(
    "UPDATE pets SET travel = %s::jsonb WHERE owner_id = (SELECT id FROM users WHERE username = %s)",
    (json.dumps(travel, ensure_ascii=False), USER),
)
conn.commit()
print(f"{USER} 的旅行已改为到期(目的地 {seed['name']}), 刷新首页触发结算")
conn.close()
