"""迁移胶囊导出: pg_dump + static 打包 (一键)
产物: migration_capsule/{pet_paradise.dump, static.zip, RESTORE.md}
.env 不打进胶囊——单独复制 (见 docs/dev/migration-guide.md)
"""
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "migration_capsule"
OUT.mkdir(exist_ok=True)

# 1. pg_dump (用容器里的 pg_dump, 自定义格式)
print("导出数据库...")
subprocess.run([
    "docker", "exec", "pet_heaven_postgres",
    "pg_dump", "-U", "postgres", "-Fc", "pet_paradise",
], stdout=open(OUT / "pet_paradise.dump", "wb"), check=True)
print(f"  pet_paradise.dump: {(OUT / 'pet_paradise.dump').stat().st_size // 1024}KB")

# 2. static 打包
print("打包 static/ ...")
with zipfile.ZipFile(OUT / "static.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in (ROOT / "backend" / "static").rglob("*"):
        if f.is_file():
            z.write(f, f.relative_to(ROOT / "backend"))
print(f"  static.zip: {(OUT / 'static.zip').stat().st_size // 1024 // 1024}MB")

print(f"完成: {OUT}")
print("记得单独复制 backend/.env (含全部 key, 不进胶囊不进 git)")
