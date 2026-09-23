# 迁移指南：Windows → MacBook（休假开发连续性）

> 2026-09-20 创建。目标：换一台 MacBook 后 10 分钟内恢复完整开发环境（代码+素材+数据+密钥）。

## 四样东西，四种走法

| 内容 | 走法 | 说明 |
|---|---|---|
| 代码 | **git 私有远端** | 全部代码+文档+脚本 |
| 生成的素材（146MB：帧/明信片/物品/场景/UI） | **迁移胶囊**（`migration_capsule/static.zip`） | gitignore 覆盖，不进 git |
| 数据库（宠物/日志/背包/记忆卡/账号） | **迁移胶囊**（`pet_paradise.dump`） | pg_dump 自定义格式 |
| 密钥（`backend/.env`） | **手动复制**（U盘/加密笔记，绝不进 git/胶囊） | 含 ARK/AtlasCloud/LLM 全部 key |

## 出发前（在 Windows 上）

```powershell
# 1. 代码推远端 (首次需要先在 GitHub/Gitee 建私有仓库)
cd D:\heaven
git remote add origin <你的私有仓库URL>
git push -u origin master

# 2. 导出迁移胶囊
python scripts\export_capsule.py

# 3. 把这三样带走 (U盘/网盘):
#    migration_capsule\  (整个文件夹)
#    backend\.env        (密钥, 单独放)
```

## 到达后（在 MacBook 上）

```bash
# 1. 装环境: Docker Desktop for Mac + Python 3.11 + Node 20+
# 2. 拉代码
git clone <你的私有仓库URL> heaven && cd heaven

# 3. 放密钥
cp /path/to/.env backend/.env

# 4. 起数据库 (docker-compose.yml 的凭据已和 .env 对齐: postgres/postgres)
docker compose up -d

# 5. 恢复数据
cat migration_capsule/pet_paradise.dump | docker exec -i pet-paradise-db pg_restore -U postgres -d pet_paradise --clean

# 6. 恢复素材
unzip migration_capsule/static.zip -d backend/

# 7. 装依赖
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && pip install imageio imageio-ffmpeg
cd ../frontend && npm install

# 8. 跑起来
cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --port 8000 &
cd frontend && npm run dev
# 打开 http://localhost:5173
```

## 休假期间的节奏建议

- 每次收工：`git push`（代码）+ 有重大生成时 `python3 scripts/export_capsule.py`（胶囊是 Mac 本地的，回程时带回）
- 回 Windows 时反向操作：git pull + 导一次胶囊灌回来
- AI 会话历史不迁移（新机器新会话），但项目记忆都在仓库里：`CLAUDE.md` / `docs/spec/` / git log
