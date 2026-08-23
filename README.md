# 宠物乐园 (Pet Paradise)

以宠物 Agent 为核心的游戏化 AI 应用：孵化宠物蛋，养育有性格、会对话、能自主探险的 AI 宠物。

MVP (V1.0) 定调为**单机版「它活着」**：一人一宠，养成 + 对话 + 离线探险；社交/多宠移至 V1.1。
产品方向以《产品终态蓝图》为准绳，需求范围以《MVP 需求规格说明书》为唯一依据。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue3 + Vite + TypeScript + Pinia + vue-router + vite-plugin-pwa |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.0 |
| 数据 | PostgreSQL 16 + Redis 7 (docker-compose) |
| LLM | 火山引擎 Ark (OpenAI 兼容协议)，分层路由：对话=pro 档 / 润色抽取=lite 档 |
| 生图 | 火山 Ark Agent Plan 端点 (doubao-seedream)：单图精灵表一次出 8 帧 → 网格切帧 + QC → PNG 序列动画 |
| 图像后处理 | numpy + scipy + Pillow（防吃白毛三件套 / 对齐 / 空洞质检，纯本地可离线重跑） |

## 快速开始

```bash
# 1. 启动数据库 (需先启动 Docker Desktop)
docker compose up -d

# 2. 后端 (http://localhost:8000)
cd backend
pip install -r requirements.txt
cp .env.example .env   # 填入 ARK_API_KEY 等配置
# 生图套餐不可用时: .env 里设 PETGEN_MODE=reuse (孵化复用素材库已有形象, 跳过生图 API)
python -m uvicorn app.main:app --reload --port 8000

# 3. 前端 (http://localhost:5173)
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 即可完整体验核心流程：
注册 → 领蛋 → 诞生问答(6 题) → 照料蛋(2-3 天) → 孵化(后台生成专属动态形象) → 对话 / 旅行(离线自动出门，归来带纪念品和旅行日记)。

## 目录结构

```
├── backend/
│   ├── app/
│   │   ├── api/         # 路由: auth/eggs/pets/dialogue/adventure/quiz/health
│   │   ├── core/        # persona(性格→prompt)/gamedata(数值+题库+事件库)/behavior(旅行行为引擎)/safety
│   │   ├── llm/         # LLM网关: 分层路由 + 预算熔断 + 用量审计
│   │   ├── models/      # SQLAlchemy 模型 (User/Egg/Pet/ChatMessage/FactMemory/AdventureLog)
│   │   └── services/    # 业务服务: egg/generation/quiz/memory/state(经验+背包)/adventure(旅行状态机)/
│   │                    #   petgen(生图管线: 精灵表→切帧→QC→manifest, 原始图落盘可离线 reprocess)
│   ├── static/pets/{id}/  # 生成产物: raw_sheet + gen_params + frames/ + manifest.json
│   └── tests/           # pytest (auth/生成/问答/行为/孵化/生图/API 流程)
├── frontend/src/
│   ├── views/           # Home(家园)/Chat(对话)/Adventure(旅行日记)/Quiz(诞生问答)/Login
│   ├── components/      # PetSprite(序列帧动画, SVG 降级)
│   ├── stores/          # Pinia auth
│   └── api/             # REST + SSE 流式客户端
├── scripts/             # POC: 性格对话验证 / 成本模拟
├── docs/                # 蓝图 / Spec / PRD / 架构 / Sprint / POC / demo 素材
└── docker-compose.yml   # PostgreSQL + Redis
```

## 文档

- [产品终态蓝图 v1.0](docs/vision/product-vision-v1.0.md) — 项目最高准绳
- [MVP 需求规格](docs/spec/mvp-spec.md) — V1.0 开发的唯一需求依据（当前 v1.1，版本演进见文末变更记录，历史用 `git tag spec-vX.Y` 锚定）
- [种子与物品体系 Spec](docs/spec/seed-item-system-spec.md) — v1.2 草案：旅行内容化/物品/图鉴/行囊（含页面操作验收表）
- [决策记录 ADR](docs/decisions/) — 方向性决策的"为什么"（如 ADR-001 极简重构）
- [PRD](docs/prd/pet-paradise-prd-v0.1.md)
- [技术选型](docs/architecture/tech-selection-v0.1.md)
- [Sprint 规划](docs/sprint/sprint-plan-v0.1.md)
- [性格对话 POC 结果](docs/poc/poc-dialogue-results.md)
- [成本基线报告](docs/poc/cost-baseline-report.md)

## 当前状态: Sprint 3 进行中 (v0.4.0)

- [x] **v0.4.0 极简重构 (2026-08-17)**: 删除喂食/休息/任务/心情三状态; 离线探险升级为旅行青蛙式「旅行」(自动出门/空房等待/归来带纪念品+旅行日记); 主页 = 宠物形象 + 对话入口。详见 [ADR-001](docs/decisions/ADR-001-simplification-v1.1.md)
- [x] Sprint 0 技术验证: 脚手架 / 性格对话 POC / 成本实测 / LLM 网关 v1
- [x] Sprint 1 宠物生命周期: 注册送蛋 / 照料孵化 / 种子化生成 / SSE 对话
- [x] Sprint 2 互动与探险: 任务 / 情绪状态机 / 事实记忆 / 离线探险 / 内容安全 (任务/情绪状态机已于 v0.4.0 移除)
- [x] Sprint 3 诞生体验: 问答引导(6 题) + 精灵表生图管线 (真实产物已过质检)
- [x] Sprint 3 生图降级: 生图套餐不可用时 PETGEN_MODE=reuse 复用素材库形象 (2026-08-15)
- [x] Sprint 3 回归通知: 回端检测 + 首页回归卡片
- [x] Sprint 3 成本熔断: 单宠/全局日配额 BudgetGuard
- [ ] 宠物主动搭话 (D6)
- [ ] 对话 10 轮/日限制 + 超限友好提示 (D3)
- [ ] 用量日报统计脚本
- [ ] pytest 全量挂起修复 / 代码推远程仓库
- [ ] Sprint 4: 档案页 / 新手引导 / 埋点 / 换标准 key / 安全加固 / 内测
