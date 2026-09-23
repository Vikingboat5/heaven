"""用 git 凭据直接调 GitHub API 创建 release 并上传胶囊附件"""
import json
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "Vikingboat5/heaven"
TAG = "vacation-capsule-2026-09-20"

# git credential fill 拿 token
p = subprocess.run(["git", "credential", "fill"], input="url=https://github.com\n",
                   capture_output=True, text=True)
token = [l.split("=", 1)[1] for l in p.stdout.splitlines() if l.startswith("password=")][0]


def api(method, url, payload=None, data=None, ctype="application/json"):
    req = urllib.request.Request(url, data=data or (json.dumps(payload).encode() if payload else None),
                                 headers={"Authorization": f"token {token}", "Content-Type": ctype,
                                          "Accept": "application/vnd.github+json"}, method=method)
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read()) if r.status != 204 else {}


# 1. 创建 release
rel = api("POST", f"https://api.github.com/repos/{REPO}/releases", {
    "tag_name": TAG, "name": "休假迁移胶囊 2026-09-20",
    "body": "static.zip=全部生成素材(144MB); pet_paradise.dump=数据库快照(pg_dump -Fc); 恢复见 docs/dev/migration-guide.md; .env 永远不在其中",
})
print("release 创建:", rel["html_url"])
upload_base = rel["upload_url"].split("{")[0]

# 2. 上传附件
for f, ct in [(ROOT / "migration_capsule" / "pet_paradise.dump", "application/octet-stream"),
              (ROOT / "migration_capsule" / "static.zip", "application/zip")]:
    print(f"上传 {f.name} ({f.stat().st_size // 1024 // 1024}MB)...", flush=True)
    api("POST", f"{upload_base}?name={f.name}", data=f.read_bytes(), ctype=ct)
    print(f"  {f.name} 完成", flush=True)
print("全部完成")
