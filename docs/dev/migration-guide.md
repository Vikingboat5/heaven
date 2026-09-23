# 迁移指南：Windows → MacBook（休假开发连续性）

> 2026-09-20 创建。目标：换一台 MacBook 后 10 分钟内恢复完整开发环境（代码+素材+数据+密钥）。

## 四样东西，四种走法

| 内容 | 走法 | 说明 |
|---|---|---|
| 代码 | **git 私有远端** | 全部代码+文档+脚本 |
| 生成的素材（146MB：帧/明信片/物品/场景/UI） | **GitHub Release 附件**（首选）或胶囊文件夹 | gitignore 覆盖，不进 git（单文件>100MB GitHub 硬拒+历史膨胀） |
| 数据库（宠物/日志/背包/记忆卡/账号） | **GitHub Release 附件**（首选）或胶囊文件夹 | pg_dump 自定义格式 |
| 密钥（`backend/.env`） | **手动复制**（U盘/加密笔记，绝不进 git/胶囊/Release） | 含 ARK/AtlasCloud/LLM 全部 key |

> Release 附件位置：`https://github.com/Vikingboat5/heaven/releases/tag/vacation-capsule-2026-09-20`
> （static.zip + pet_paradise.dump 都在里面；胶囊文件夹是同一份的本地拷贝，二选一）

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
# 一键恢复 (scripts/bootstrap_mac.sh: 工具链/容器/依赖/胶囊/数据/素材全自动):
git clone https://github.com/Vikingboat5/heaven.git heaven && cd heaven
bash scripts/bootstrap_mac.sh
# 中途可能弹两次人工动作: ①Homebrew 装 Docker Desktop 首次启动 ②gh 浏览器授权(下载私有 release 附件)
# 最后一步如提示缺 backend/.env: 把密钥内容放进去, 重跑一次脚本即可 (幂等)

# 完成后启动:
cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --port 8000 &
cd frontend && npm run dev
# 打开 http://localhost:5173
```

## 休假期间的节奏建议

- 每次收工：`git push`（代码）+ 有重大生成时 `python3 scripts/export_capsule.py`（胶囊是 Mac 本地的，回程时带回）
- 回 Windows 时反向操作：git pull + 导一次胶囊灌回来
- AI 会话历史不迁移（新机器新会话），但项目记忆都在仓库里：`CLAUDE.md` / `docs/spec/` / git log
