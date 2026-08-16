"""E2E 验证: 任务领取全链路 (repair_verify 的 api-e2e 层)

主流程: 注册探针 → 快进孵化值 → 孵化 → 喂食一次(触发 daily_feed 进度) →
GET /api/tasks 断言 claimable → POST claim 断言 ok → 再次 GET 断言 claimed →
写 .e2e-token/.e2e-username 供 browser 层复用 (探针留存, 清理由 --cleanup 完成)。
--cleanup: 清理探针数据。
退出码: 0 = 通过, 1 = 失败。
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


def find_task(d, code):
    for t in d.get("tasks") or []:
        if t.get("code") == code:
            return t
    return None


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
        print("[PASS] 探针已不存在, 跳过清理")
        return 0
    uid = row[0]
    cur.execute("DELETE FROM chat_messages WHERE pet_id IN (SELECT id FROM pets WHERE owner_id = %s)", (uid,))
    cur.execute("DELETE FROM fact_memories WHERE pet_id IN (SELECT id FROM pets WHERE owner_id = %s)", (uid,))
    cur.execute("DELETE FROM adventure_logs WHERE pet_id IN (SELECT id FROM pets WHERE owner_id = %s)", (uid,))
    cur.execute("DELETE FROM pets WHERE owner_id = %s", (uid,))
    cur.execute("DELETE FROM user_task_progress WHERE user_id = %s", (uid,))
    cur.execute("DELETE FROM eggs WHERE owner_id = %s", (uid,))
    cur.execute("DELETE FROM users WHERE id = %s", (uid,))
    conn.commit()
    conn.close()
    print(f"[PASS] 探针 {uname} 已清理")
    return 0


def main():
    if "--cleanup" in sys.argv:
        return cleanup_mode()

    uname = f"e2etask_{int(time.time()) % 1000000}"
    s, d = api("POST", "/api/auth/register", body={"username": uname, "password": "probe123"})
    if s != 200:
        fail(f"注册失败 {s}: {d}")
    token = d["token"]

    conn = psycopg.connect(DSN)
    cur = conn.cursor()
    try:
        # 快进孵化值 → 孵化
        cur.execute(
            "UPDATE eggs SET hatch_value = 100 "
            "WHERE owner_id = (SELECT id FROM users WHERE username = %s)",
            (uname,),
        )
        conn.commit()
        s, d = api("POST", "/api/eggs/hatch", token=token, body={"name": "任务兔"})
        if s != 200:
            fail(f"孵化失败 {s}: {d}")

        # 喂食一次 → daily_feed 进度 1/1 → claimable
        s, d = api("POST", "/api/pets/feed", token=token)
        if s != 200:
            fail(f"喂食失败 {s}: {d}")

        s, d = api("GET", "/api/tasks", token=token)
        if s != 200:
            fail(f"任务列表失败 {s}: {d}")
        t = find_task(d, "daily_feed")
        if t is None or t.get("status") != "claimable":
            fail(f"daily_feed 应为 claimable, 实际: {json.dumps(t, ensure_ascii=False)}")

        s, d = api("POST", "/api/tasks/daily_feed/claim", token=token)
        if s != 200 or not d.get("ok"):
            fail(f"领取失败 {s}: {d}")

        s, d = api("GET", "/api/tasks", token=token)
        t = find_task(d, "daily_feed")
        if t is None or t.get("status") != "claimed":
            fail(f"领取后 daily_feed 应为 claimed, 实际: {json.dumps(t, ensure_ascii=False)}")

        # 探针留存: 供 browser 层打开任务面板断言"已领取"
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(token)
        with open(USER_FILE, "w", encoding="utf-8") as f:
            f.write(uname)
        print(f"[PASS] task-claim api-e2e: 注册→孵化→喂食→claimable→领取→claimed 断言全部通过 (探针 {uname})")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
