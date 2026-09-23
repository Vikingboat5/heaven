#!/usr/bin/env bash
# 宠物乐园 Mac 一键环境恢复 (休假迁移用)
# 用法: git clone <repo> && cd heaven && bash scripts/bootstrap_mac.sh
# 幂等: 可重复运行; 每步已装/已做就跳过
set -e
cd "$(dirname "$0")/.."

echo "== 1/7 工具链 (Homebrew) =="
if ! command -v brew >/dev/null; then
  echo "安装 Homebrew (需要你输一次开机密码)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Apple Silicon 的 brew 路径
  [ -f /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
fi
for pkg in git python@3.11 node gh; do
  command -v "${pkg%%@*}" >/dev/null 2>&1 || brew install "$pkg"
done
if ! command -v docker >/dev/null; then
  brew install --cask docker
  echo "Docker Desktop 已装, 正在启动 (首次启动较慢)..."
  open -a Docker
  echo "等 Docker 就绪..."
  until docker info >/dev/null 2>&1; do sleep 3; done
fi

echo "== 2/7 数据库容器 (docker compose) =="
docker compose up -d
echo "等 PostgreSQL 就绪..."
until docker exec pet-paradise-db pg_isready -U postgres -d pet_paradise >/dev/null 2>&1; do sleep 2; done

echo "== 3/7 后端依赖 =="
cd backend
python3.11 -m venv .venv 2>/dev/null || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt imageio imageio-ffmpeg
cd ..

echo "== 4/7 前端依赖 =="
cd frontend && npm install --silent && cd ..

echo "== 5/7 迁移胶囊 (release 附件) =="
mkdir -p migration_capsule
if [ ! -f migration_capsule/static.zip ]; then
  # 私有仓库 release 附件需要 gh 登录 (会弹浏览器授权, 点一下即可)
  gh auth status >/dev/null 2>&1 || gh auth login --web --git-protocol https
  gh release download vacation-capsule-2026-09-20 --repo Vikingboat5/heaven --dir migration_capsule --clobber
fi

echo "== 6/7 恢复数据 + 素材 =="
cat migration_capsule/pet_paradise.dump | docker exec -i pet-paradise-db pg_restore -U postgres -d pet_paradise --clean --if-exists 2>/dev/null || true
unzip -oq migration_capsule/static.zip -d backend/

echo "== 7/7 检查 .env =="
if [ ! -f backend/.env ]; then
  echo ""
  echo "⚠️  缺 backend/.env (密钥不进任何仓库, 需要你手动放):"
  echo "   内容含: ARK_API_KEY / ATLASCLOUD_API_KEY / DATABASE_URL / REDIS_URL / JWT_SECRET"
  echo "   放好后重跑本脚本即可 (幂等)"
  exit 1
fi

echo ""
echo "✅ 环境就绪。启动:"
echo "   后端: cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --port 8000"
echo "   前端: cd frontend && npm run dev"
echo "   打开: http://localhost:5173"
