# 宠物乐园 (Pet Paradise) — Agent 项目记忆

> 面向本仓库所有 AI 编程代理的常驻说明。保持精简：只放稳定规则与指针，详细内容放对应文档。
> 这些规则来源于实际事故复盘（2026-08-15），针对的是**通用的工作模式缺陷**，不是某一次具体问题。

## 项目速览

- 单机版 AI 宠物应用：Vue3 + Vite 前端（`frontend/`），FastAPI + SQLAlchemy 后端（`backend/`），PostgreSQL/Redis 本机运行（`docker compose up -d`）
- 文档入口：`README.md`；需求唯一依据 `docs/spec/mvp-spec.md`；最高准绳 `docs/vision/product-vision-v1.0.md`；方向性决策 `docs/decisions/`(ADR)；**UI/动效规范 `docs/spec/ui-motion-guidelines.md`（所有前端页面/组件的实现与验收依据，tokens 在 `frontend/src/style.css`）**
- **动画管道 spec：`docs/spec/pet-animation-pipeline-spec.md`（动作集/物种适配/首尾帧→视频→采帧全流程）**；内容设计表 `backend/app/content/animation_designs.json`（物种路由，铁律：鱼不招手）
- 常用开发脚本（`scripts/`）：`check_state.py`（只读查库）、`fastforward_hatch.py <username>`（孵化值快进）、`checkpoint.ps1`（留回退点）、`e2e_force_return.py [user] [seed]`（强制宠物回家）、`export_capsule.py`（迁移胶囊导出）、`gen_animation_frames.py <pet_id>`（动作首尾帧）、`gen_action_video.py <pet_id>`（视频生成+采帧）、`video_to_frames.py`（离线重切帧）
- 后端启动：`cd backend && python -m uvicorn app.main:app --port 8000`（受限环境禁用 `--reload`，子进程命名管道会被拦截）
- 前端启动：`cd frontend && npm run dev`；本机可能存在多个 dev server（5173/5174），排查前先确认用户实际在哪个端口

## 当前状态速览（2026-09-20，新会话从这里接上）

- **远端**：`https://github.com/Vikingboat5/heaven`（私有）；素材/密钥不在 git（见 `docs/dev/migration-guide.md`）
- **AI 供应商**：文本/生图=方舟 Agent Plan（`/api/plan` 端点，kimi-k3/seedream-5.0-lite）；**视频=AtlasCloud seedance-2.0-mini**（首尾帧 i2v；方舟不含视频模型已弃用）；key 全在 `backend/.env`（gitignore）
- **宠物动画**：视频采帧帧动画（24帧 ping-pong 播放）。管线关键工艺：**并集裁剪窗**（整动作共用注册窗，禁逐帧 re-anchor）、**解剖学锚点**（身长缩放+脚线对地，禁锚剪影指标）、**剔除第 0 帧**（参考图本体风格突变）、**白度压缩**（跨动作亮度一致）、**切换硬切**（位置对齐后任何淡化/过渡都是闪烁源）
- **内容系统**：种子冒险（seeds.json）+ 地点记忆卡（pet_seed_memories，重访信件连续性，token O(1)）+ 首到明信片（postcard_service）+ 图鉴（collection=曾经获得，非当前持有）
- **UI**：底部 tab（小窝/日记/背包）+ 场景实物入口 + 明信片墙（夜空挂绳）；规范 v1.3
- **探针账号**：`e2e_ui_probe / probe123456`（宠物=咿呀，狐），`postcard_probe`（宠物=片片）；清理用 `cleanup_probe.py`
- **信件基调**：宠物视角讲自己的见闻（修订 R6：主体是它的世界，想念只许自然流露，禁止"想你"模板结尾）

## 工作红线（通用行为约束）

### A. 修复必须走闭环：改 → 验证 → 才汇报

1. 任何修复在**向用户宣布完成前**，必须完成验证；验证优先 E2E（探针账号走完整链路），至少是针对性测试
2. 验证没过 → 继续修或回退，**禁止把"让用户试一下"当作验证手段**
3. 汇报必须附验证证据（测试输出、接口实测结果、日志记录），没有证据就说"还没验证完"
4. 给用户的操作指令（重启、刷新等）必须自己能闭环确认（如"你刷新，我看日志确认请求到达"）

### B. 排查必须证据先行

1. 症状与理论矛盾时，**先质疑前提**（用户在哪个端口？进程是哪个？服务端真的返回了新代码？），禁止跳过可见层去理论化不可见层
2. "日志里没有某请求" = 该代码没被执行——是定位信号，不是噪音
3. 改了 N 个文件就验证 N 个文件（开发服务器存在监听器漏改、模块图半新半旧状态）；抽查一个不代表整体
4. 拿不到证据就明说"我还需要 X 才能确认"，禁止用缓存/玄学类假设填空
5. 修复前先写失败场景的测试；兜底逻辑不允许静默（`catch {}` 必须留痕）

### C2. 需求与验收不产生偏差（负责人明确要求，2026-08-17）

1. 开发任何功能前，spec 中每个**用户操作/页面必须有明确的预期结果**（操作 → 预期结果表）
2. 开发以该表为实现目标，验收以该表为唯一准绳；表里没有的行为不允许擅自发挥
3. 发现预期结果有歧义/缺失时，先回 spec 补全拍板，再动手

### C. 动手前先留退路

1. 破坏性修改前先跑 `scripts/checkpoint.ps1` 留 git 回退点
2. 优先在隔离环境验证（测试用 SQLite + `noop_sprite_task` fixture，不碰真实服务；探针账号用完即清）
3. 重启服务后必须先确认新代码真正生效（如接口 404→401），再宣称"已重启"

## 按需加载的详细文档

- 修复协议（五步闭环）：`.dsh/skills/repair-loop.md`（DSH 技能）/ `.claude/skills/repair-loop.md`（Claude Code，同内容）— **任何修复/排障任务开始前先加载**
- 排查清单与案例复盘：`.dsh/skills/debug-playbook.md` / `.claude/skills/debug-playbook.md`（同内容）
