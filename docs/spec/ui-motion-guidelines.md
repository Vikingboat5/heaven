# UI 与动效规范 (v1.0, 2026-08-29 拍板)

> **地位**: 所有前端页面/组件的实现与验收依据之一（与 seed-item-system-spec §11 操作预期表并列）。
> 新功能拓展时必须先读本规范；规范没覆盖的样式决策，先在本文档补条目再动手（对齐 CLAUDE.md C2）。
> 落地位置：tokens 在 `frontend/src/style.css`，本文件是"为什么这么定 + 怎么用"。

## 0. 设计原则

1. **宠物是主角**（布局红线，2026-08-23 拍板）：任何 UI 元素不得遮挡宠物形象。底部 UI 一律用紧凑半透明坞；弹层优先底部抽屉（bottom sheet），不做全屏居中卡
2. **温暖绘本感**：黄昏夜景 + 圆角 + 柔和光晕；拒绝锐利直角、高对比硬边、纯黑纯白
3. **动静有度**：动效服务于"它活着"的感觉（呼吸、漂浮、错峰入场），不做炫技式动画；所有动效可降级（`prefers-reduced-motion`）
4. **一致性优先于个性**：新组件必须复用 tokens 与既有模式；禁止引入"只此一处"的颜色/字号/时长

## 1. 色彩

tokens（`style.css` `:root`）：

| token | 值 | 用途 |
|-------|-----|------|
| `--color-night` | #150c2e | 全局底色 |
| `--color-primary` | #f2a56e | 主行动（渐变起点） |
| `--color-accent` | #e77fa2 | 点缀（少用） |
| `--color-gold` | #f7c98a | 标题/数字/强调文字 |
| `--color-text` | #fdf6ec | 主文字 |
| `--color-text-dim` / `--color-text-faint` | 60% / 40% 透明度 | 次要/弱化文字 |
| `--color-glass` / `--color-glass-border` | 半透明深紫 | 玻璃卡片底/边 |

**品级色**（图鉴/背包/信件共用，禁止另造）：
- 常见 common：中性灰边 `rgba(255,255,255,0.12)`
- 稀有 rare：蓝 `#78aaff`（描边 55-60% 透明度 + 微光晕）
- 传说 epic：金 `#f7c964`（描边 65-80% + **旋转流金边框** `.epic-glow`）

规则：渐变按钮统一 `linear-gradient(135deg, #ffd9a0, #f2b06e)`；错误/提示红用 `#ff7a7a` / `#ffb3b3`；不新增品牌色。

## 2. 字体与排版

- **标题/宠物名/大数字**：得意黑 Smiley Sans（`--font-display`，npm 包 `cn-fontsource-smiley-sans-oblique-regular`，按需分包 woff2，`font-display: swap`）
- **正文/日记**：圆体栈（`--font-body`: Yuanti SC → YouYuan → PingFang SC → Microsoft YaHei → system-ui）
- 字号阶梯（只能用这几档）：

| token | 值 | 用途 |
|-------|-----|------|
| `--fs-xs` | 11px | 角标/辅助说明 |
| `--fs-sm` | 12px | 次要信息/提示 |
| `--fs-md` | 13px | 按钮/表格 |
| `--fs-lg` | 14px | 正文/日记 |
| `--fs-xl` | 17-18px | 卡片标题 |
| `--fs-xxl` | 22px | 页面大标题 |

- 标题字距：`letter-spacing: 3-6px`（大标题）/ `1-2px`（卡片标题）；正文不加字距
- 数字（经验/数量/倒计时）一律 `font-variant-numeric: tabular-nums`

## 3. 布局

- 外层 shell：max-width 480px 居中（手机优先），顶部 sticky 导航（家园/收藏/用户）
- 主页：场景层（SVG 插画）→ 宠物层 → UI 层（操作坞贴底，`bottom: 14px`；占屏比红线：宠物在家 ≤15%，旅行中（含状态/行囊信息）≤20%，以 1221px 高视口实测为准）
- 内容页（打包/收藏）：统一页面骨架 `.page`（深色渐变底 + 双星闪烁 + 顶部返回+标题区 + 内容区）

### 3.1 主页场景层构成（2026-08-29 场景升级拍板）

画家算法自下而上，**新元素必须插入正确层级**，且全部走 `prefers-reduced-motion` 降级：

| 层 | 元素 | 动效 |
|----|------|------|
| 天空 | 8 档黄昏渐变 / 38 星（白·暖黄·淡蓝三色温）+ 5 十字星芒 / 银河带（18 碎星+柔光带）/ 月牙+银辉 / 流星 ×2（12s、17s 错峰） | twinkle / meteor-fly |
| 远景 | 落日（blur24 大柔光）/ 地平线暖雾带 / 4 层远山 + 2 条山雾带 / 山谷灯火 ×6（远处村庄）/ 山脊剪影树丛 | 灯火 twinkle |
| 中景 | 孤独的树 + 木漏光斑 ×4 / 挂灯 ×2（灯核+大光晕, 摆动）/ 飘落花瓣 ×5 / 小水洼（映月+涟漪 ×2） | lantern-sway / petal-fall / ripple-spread |
| 巢区 | 巢 + 呼吸光晕 + 地面反光 + 尘埃光粒 ×4 + 宠物 | halo-breathe / mote-rise |
| 氛围 | 萤火虫 ×12（双层光晕：blur6 晕 + 实心核）/ 前景草叶（微风摆动） | firefly / grass-sway |
| 收尾 | 暗角 vignette（聚焦巢区）+ 纸感噪点 | — |

约束：氛围元素（流星/花瓣/萤火虫）必须"克制"——长周期、低占空比；场景永远服务于宠物，不在宠物身上叠加任何场景元素。
- 弹层：底部抽屉（贴底、顶部圆角 24px、max-height 62vh、遮罩 45% 透明度）；详情小卡可居中（图鉴物品详情等"对单物聚焦"场景例外）

## 4. 动效规范

tokens：

| token | 值 | 用途 |
|-------|-----|------|
| `--motion-fast` | 150ms | 按压/hover |
| `--motion-med` | 250ms | 入场/徽章 |
| `--motion-slow` | 400ms | 抽屉/弹层 |
| `--ease-out` | cubic-bezier(0.22, 1, 0.36, 1) | 默认出场 |
| `--ease-spring` | cubic-bezier(0.34, 1.56, 0.64, 1) | 回弹感（徽章/信封/入槽） |

**标准模式**（复用，别新造）：
1. **按压反馈**：所有可点元素 `:active { transform: scale(0.96) }`，过渡 `--motion-fast`
2. **错峰入场**：列表/网格容器加 `.stagger`，子元素 fade+上移 12px，`--motion-med`，每个延迟 40ms（CSS nth-child 到 12 个）
3. **页面转场**：router-view fade + 上移 8px，180ms `--ease-out`
4. **徽章脉冲**：NEW! 角标 `.badge-pulse`，1.6s 缩放 1→1.12→1 + 光晕
5. **信封**：`envelope-bob` 1.6s 上下浮动 8px（无限）
6. **信件抽屉**：`sheet-in` 从底部上移 60px 淡入，`--motion-slow`
7. **传说流金**：`.epic-glow` 用 `@property --angle` + conic-gradient 旋转 6s
8. **降级**：`@media (prefers-reduced-motion: reduce)` 下所有动画关闭（全局兜底已含）

禁止：无限大幅位移动画（除信封/萤火虫等氛围元素）；超过 500ms 的交互动效；`transition: all`（写明确属性）。

## 5. 组件模式

- **玻璃卡**：`--color-glass` 底 + blur(14-18px) + `--color-glass-border` 边 + 圆角 16-20px
- **主按钮 CTA**：金色渐变胶囊（`border-radius: 999px`），字距 4px
- **次按钮 action-btn**：玻璃底 + 细边，圆角 12px
- **物品格**：图（44px 圆角 8px）+ 名 + 品级色描边；未获得=剪影 `grayscale(1) brightness(0.35)` + 名称 "???"
- **空态**：emoji/插画 + 一句标题 + 一句引导（禁纯文字报错感）
- **加载态**：爪印/圆点 loader，禁裸 "加载中…" 大字（短期可先用文字，迭代时换插画）

## 6. 验收 checklist（每个新页面/组件过一遍）

- [ ] 只用了规范内的色/字号/时长（无硬编码新值）
- [ ] 可点元素有按压反馈；列表有错峰入场
- [ ] 不遮挡宠物（涉及主页时，几何验证：sprite 矩形与 UI 矩形无交集）
- [ ] 品级色一致；数字 tabular-nums
- [ ] `prefers-reduced-motion` 下不闪烁不位移
- [ ] console 零错误
