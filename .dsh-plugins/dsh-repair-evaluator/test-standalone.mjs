/**
 * dsh-repair-evaluator 独立自测 (不经 DSH 装载, 直接驱动引擎核心)
 * 用法: node test-standalone.mjs parse   # 只测 YAML 解析 (无子进程)
 *       node test-standalone.mjs full    # 按 .repair.yaml 全层级执行 (含 spawn/browser)
 * 退出码: 0 = 全部通过
 */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parseMiniYaml } from './lib/yaml-mini.js'
import { runRepair } from './lib/engine.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const workspace = path.resolve(here, '..', '..') // D:\heaven
const mode = process.argv[2] ?? 'parse'

function assert(cond, msg) {
  if (!cond) {
    console.error(`[FAIL] ${msg}`)
    process.exitCode = 1
    throw new Error(msg)
  }
  console.log(`[ok] ${msg}`)
}

async function testParse() {
  const raw = readFileSync(path.join(workspace, '.repair.yaml'), 'utf8')
  const cfg = parseMiniYaml(raw)
  assert(cfg.browser_server?.command === 'npx', 'browser_server.command 解析')
  assert(Array.isArray(cfg.browser_server.args) && cfg.browser_server.args[0] === '-y', 'browser_server.args 列表解析')
  assert(cfg.browser_server.startupTimeoutMs === 90000, '整数字面量解析')
  const t = cfg.targets['chat-history']
  assert(t && Array.isArray(t.levels), 'targets.chat-history.levels 存在')
  const byLevel = Object.fromEntries(t.levels.map((l) => [l.level, l]))
  assert(byLevel.unit?.cwd === 'backend' && byLevel.unit.timeout_ms === 300000, 'unit 层字段解析')
  assert(byLevel.state?.probes?.[0]?.expect_status === 401, 'state 层 probes 解析')
  assert(byLevel.state?.probes?.[1]?.expect_contains === 'getChatHistory', 'state 层 expect_contains 解析')
  const browser = byLevel.browser
  assert(Array.isArray(browser.steps) && browser.steps.length >= 5, 'browser 层 steps 解析')
  const fn = browser.steps[1]?.args?.function ?? ''
  assert(fn.includes("{{read:.e2e-token}}"), 'browser 层函数模板保留')
  assert(browser.steps[3]?.tool === 'wait_for', 'wait_for 步骤解析')
  assert(browser.steps[4]?.assert?.text_contains === '主人你好呀', 'browser 层断言解析')
  const e2eLevels = t.levels.filter((l) => l.level === 'api-e2e')
  assert(e2eLevels.length === 2, 'api-e2e 层共两段 (验证 + 清理)')
  assert(e2eLevels[0].cmd === 'python scripts/e2e_verify_chat_history.py', 'api-e2e 层 cmd 解析')
  assert(e2eLevels[1].cmd.endsWith('--cleanup'), '清理层 cmd 解析')
  // 边界: 嵌套 map 与标量共存
  const tricky = parseMiniYaml('a:\n  b: 1\n  c: true\n  d:\n    - x\n    - y: 2\nlist:\n  - key: val\n')
  assert(tricky.a.c === true && tricky.a.d[0] === 'x' && tricky.a.d[1].y === 2, '嵌套结构解析')
  assert(tricky.list[0].key === 'val', '行内 map 列表项解析')
  console.log('\n[PASS] YAML 解析自测全部通过')
}

async function testFull() {
  console.log(`工作区: ${workspace}`)
  const result = await runRepair({ workspaceDir: workspace, target: 'chat-history' })
  for (const l of result.levels) {
    console.log(`\n=== ${l.level} [${l.name}] ${l.pass ? 'PASS' : 'FAIL'} (${l.durationMs}ms) ===`)
    console.log(l.evidence.slice(0, 4000))
  }
  console.log(`\nallPass=${result.allPass} — ${result.summary}`)
  if (!result.allPass) process.exitCode = 1
}

if (mode === 'parse') {
  testParse()
} else if (mode === 'full') {
  await testFull()
} else {
  console.error(`用法: node test-standalone.mjs [parse|full]`)
  process.exitCode = 2
}
