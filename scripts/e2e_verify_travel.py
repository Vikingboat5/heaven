"""E2E 验证: 旅行状态机 (P4) 全链路

主流程: 注册→孵化 → check(在家 null) → 手动出门(leave ok) → pets/me away=true
→ chat 409 锁定 → 快进 back_at 到过去 → check(returned+log) → pets/me away=false
--cleanup: 清理探针。
"""
import json
import sys
import time
import urllib.error
import urllib.request

import psycopg

BASE = "http://localhost:8000"
DSN = "postgresql://postgres:postgres@localhost:5432/pet_paradise"
TOKEN_FILE = ".e2e-token"
USER_FILE = ".e2e-username"


def api(method, path, token=None, body=None, timeout=30):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except Exception:
            return e.code, None
    except Exception as e:
        return 0, str(e)


def fail(msg):
    print(f"[FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


def cleanup_mode():
    try:
        with open(USER_FILE, encoding="utf-8") as f:
            uname = f.read().strip()
    except OSError:
        print("[PASS] 无探针记录, 跳过清理")
        return 0
    conn = psycopg.connect(DSN)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = %s", (uname,))
    row = cur.fetchone()
    if not row:
        conn.close()
        print("[PASS] 探针已不存在")
        return 0
    uid = row[0]
    cur.execute("DELETE FROM chat_messages WHERE pet_id IN (SELECT id FROM pets WHERE owner_id = %s)", (uid,))
    cur.execute("DELETE FROM fact_memories WHERE pet_id IN (SELECT id FROM pets WHERE owner_id = %s)", (uid,))
    cur.execute("DELETE FROM adventure_logs WHERE pet_id IN (SELECT id FROM pets WHERE owner_id = %s)", (uid,))
    cur.execute("DELETE FROM pets WHERE owner_id = %s", (uid,))
    cur.execute("DELETE FROM eggs WHERE owner_id = %s", (uid,))
    cur.execute("DELETE FROM users WHERE id = %s", (uid,))
    conn.commit()
    conn.close()
    print(f"[PASS] 探针 {uname} 已清理")
    return 0


def main():
    if "--cleanup" in sys.argv:
        return cleanup_mode()

    uname = f"e2etravel_{int(time.time()) % 1000000}"
    s, d = api("POST", "/api/auth/register", body={"username": uname, "password": "probe123"})
    if s != 200:
        fail(f"注册失败 {s}")
    token = d["token"]

    conn = psycopg.connect(DSN)
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE eggs SET hatch_value=100 WHERE owner_id=(SELECT id FROM users WHERE username=%s)", (uname,)
        )
        conn.commit()
        s, d = api("POST", "/api/eggs/hatch", token=token, body={"name": "旅行兔"})
        if s != 200:
            fail(f"孵化失败 {s}: {d}")
        pet_id = d["id"]

        # 1. 在家 → check 返回 null
        s, d = api("GET", "/api/adventure/check", token=token)
        if s != 200 or d.get("event") is not None:
            fail(f"新鲜宠物 check 应 event=null, 实际 {s}: {d}")

        # 2. 手动出门
        s, d = api("POST", "/api/adventure/leave", token=token)
        if s != 200 or not d.get("ok"):
            fail(f"leave 失败 {s}: {d}")

        # 3. pets/me → away=true
        s, d = api("GET", "/api/pets/me", token=token)
        if s != 200 or d.get("away") is not True:
            fail(f"出门后 away 应为 true, 实际 {s}: {d}")

        # 4. 旅行中对话锁定 → 409
        s, _ = api("POST", "/api/dialogue/chat", token=token, body={"message": "在吗"})
        if s != 409:
            fail(f"旅行中对话应 409, 实际 {s}")

        # 5. 快进 back_at 到过去 → check 返回 returned
        cur.execute(
            "UPDATE pets SET travel = jsonb_set(COALESCE(travel::jsonb,'{}'::jsonb), '{back_at}', "
            "to_jsonb((now() - interval '1 hour')::text)) WHERE id=%s", (pet_id,)
        )
        conn.commit()
        s, d = api("GET", "/api/adventure/check", token=token)
        if s != 200 or d.get("event") != "returned" or d.get("log") is None:
            fail(f"归来应 event=returned 且有 log, 实际 {s}: {d}")

        # 6. 归来后 away=false
        s, d = api("GET", "/api/pets/me", token=token)
        if s != 200 or d.get("away") is not False:
            fail(f"归来后 away 应为 false, 实际 {s}: {d}")

        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(token)
        with open(USER_FILE, "w", encoding="utf-8") as f:
            f.write(uname)
        print(f"[PASS] travel 状态机: 在家→出门→旅行中锁对话→归来带日志→回家 全部通过 (探针 {uname})")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
