"""E2E 验证: 对话历史 API 全链路 (repair_verify 的 api-e2e 层)

主流程 (无参数): 注册探针 → 快进孵化值 → 孵化 → 直插两条历史消息 →
GET /api/dialogue/history 断言回显 → 写 .e2e-token/.e2e-username 供 browser 层注入。
--cleanup: 读取 .e2e-username 清理探针数据 (browser 层之后调用)。
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
    except Exception as e:  # 网络错误
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

    uname = f"e2ehist_{int(time.time()) % 1000000}"
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
        s, d = api("POST", "/api/eggs/hatch", token=token, body={"name": "验证兔"})
        if s != 200:
            fail(f"孵化失败 {s}: {d}")
        pet_id = d["id"]

        # 直插两条历史消息 (模拟已聊过)
        cur.execute(
            "INSERT INTO chat_messages (pet_id, role, content, created_at) "
            "VALUES (%s, 'user', '你好呀', now()), (%s, 'assistant', '主人你好呀', now())",
            (pet_id, pet_id),
        )
        conn.commit()

        # GET /history 断言回显
        s, d = api("GET", "/api/dialogue/history", token=token)
        if s != 200:
            fail(f"history 接口失败 {s}: {d}")
        msgs = d.get("messages") or []
        if len(msgs) != 2 or msgs[0].get("content") != "你好呀" or msgs[1].get("content") != "主人你好呀":
            fail(f"回显内容不符: {json.dumps(msgs, ensure_ascii=False)}")
        if msgs[0].get("role") != "user" or msgs[1].get("role") != "pet":
            fail(f"角色映射不符: {json.dumps(msgs, ensure_ascii=False)}")

        # 探针留存: 写 token/用户名供 browser 层注入 (清理由 --cleanup 完成)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(token)
        with open(USER_FILE, "w", encoding="utf-8") as f:
            f.write(uname)
        print(f"[PASS] chat-history api-e2e: 注册→孵化→插消息→回显断言 全部通过 (探针 {uname}, pet {pet_id})")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
