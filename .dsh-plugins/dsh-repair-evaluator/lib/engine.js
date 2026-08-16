/**
 * 修复验证引擎 — 读取 .repair.yaml, 按 target 逐层执行验证, 返回结构化证据。
 * 层级: unit / build / state / api-e2e / browser
 * 原则: 只收集客观证据 (退出码/HTTP 状态/文本断言), 不做任何主观判断。
 */

import { exec } from 'node:child_process'
import { readFileSync, existsSync } from 'node:fs'
import path from 'node:path'
import { parseMiniYaml } from './yaml-mini.js'
import { McpStdioClient, resultText } from './mcp-stdio.js'

const DEFAULT_CMD_TIMEOUT = 300000

function tail(s, n = 3000) {
  const str = String(s ?? '')
  return str.length > n ? '...(截断)\n' + str.slice(-n) : str
}

/** 运行一条 shell 命令, 返回 { exitCode, killed, output } */
function runCmd(cmd, { cwd, timeoutMs }) {
  return new Promise((resolve) => {
    exec(cmd, {
      cwd,
      timeout: timeoutMs ?? DEFAULT_CMD_TIMEOUT,
      windowsHide: true,
      maxBuffer: 16 * 1024 * 1024,
    }, (err, stdout, stderr) => {
      if (err) {
        resolve({
          exitCode: typeof err.code === 'number' ? err.code : -1,
          killed: Boolean(err.killed),
          output: tail(`${stdout}\n${stderr}\n[错误] ${err.message}`),
        })
      } else {
        resolve({ exitCode: 0, killed: false, output: tail(`${stdout}\n${stderr}`) })
      }
    })
  })
}

/** HTTP 探测: 支持 expect_status / expect_contains */
async function runProbe(probe) {
  const started = Date.now()
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), probe.timeoutMs ?? 10000)
    const resp = await fetch(probe.url, { signal: controller.signal, redirect: 'follow' })
    clearTimeout(timer)
    const body = await resp.text()
    const statusOk = probe.expect_status === undefined || resp.status === probe.expect_status
    const containsOk = probe.expect_contains === undefined || body.includes(probe.expect_contains)
    const pass = statusOk && containsOk
    return {
      pass,
      detail: `GET ${probe.url} → ${resp.status}${probe.expect_status !== undefined ? ` (期望 ${probe.expect_status})` : ''}` +
        (probe.expect_contains !== undefined ? `, 含 "${probe.expect_contains}": ${containsOk}` : ''),
      durationMs: Date.now() - started,
    }
  } catch (err) {
    return {
      pass: false,
      detail: `GET ${probe.url} → 失败: ${err.message}`,
      durationMs: Date.now() - started,
    }
  }
}

/** 模板替换: {{read:相对路径}} → 文件内容 (相对 workspaceRoot) */
function applyTemplate(value, workspaceRoot) {
  const re = /\{\{read:([^}]+)\}\}/g
  if (typeof value === 'string') {
    return value.replace(re, (_m, p) => {
      const abs = path.resolve(workspaceRoot, p.trim())
      return existsSync(abs) ? readFileSync(abs, 'utf8').trim() : `(文件不存在: ${p.trim()})`
    })
  }
  if (Array.isArray(value)) return value.map((v) => applyTemplate(v, workspaceRoot))
  if (value && typeof value === 'object') {
    const out = {}
    for (const [k, v] of Object.entries(value)) out[k] = applyTemplate(v, workspaceRoot)
    return out
  }
  return value
}

/** 运行 browser 层: MCP 连接 chrome-devtools-mcp, 逐步执行 + 断言 */
async function runBrowserLevel(level, cfg, workspaceRoot) {
  const server = cfg.browser_server
  if (!server) {
    return { pass: false, evidence: 'browser 层需要 .repair.yaml 顶层 browser_server 配置' }
  }
  let client
  try {
    client = await McpStdioClient.start(server)
    const steps = level.steps ?? []
    const details = []
    let allPass = true
    for (const step of steps) {
      const started = Date.now()
      // 内置步骤: sleep — 不经过 MCP
      if (step.tool === 'sleep') {
        const ms = Number(step.args?.ms ?? 1000)
        await new Promise((r) => setTimeout(r, ms))
        details.push(`[sleep] ${ms}ms`)
        continue
      }
      const args = applyTemplate(step.args ?? {}, workspaceRoot)
      let text = ''
      try {
        const result = await client.callTool(step.tool, args, step.timeoutMs ?? 60000)
        text = resultText(result)
        // 服务端把工具错误当文本返回(MCP error/Unknown argument/validation error 等): 视为步骤失败
        if (/^(MCP error|Unknown argument|Input validation error|Error[: ])/i.test(text.trim())) {
          details.push(`[${step.tool}] 服务端错误: ${text.slice(0, 300)}`)
          return { pass: false, evidence: details.join('\n') }
        }
        const detail = `[${step.tool}] ${text.slice(0, 200).replace(/\s+/g, ' ')}`
        details.push(detail)
      } catch (err) {
        details.push(`[${step.tool}] 失败: ${err.message}`)
        return { pass: false, evidence: details.join('\n') }
      }
      // 断言
      const assert = step.assert
      if (assert) {
        let ok = true
        let why = ''
        if (assert.text_contains !== undefined) {
          ok = text.includes(assert.text_contains)
          why = `文本含 "${assert.text_contains}": ${ok}`
        }
        if (ok && assert.console_errors !== undefined) {
          try {
            const consoleResult = await client.callTool('list_console_messages', {}, 30000)
            const consoleText = resultText(consoleResult)
            const errors = countConsoleErrors(consoleResult)
            ok = errors <= assert.console_errors
            why = `控制台错误数 ${errors} (阈值 ${assert.console_errors}): ${ok}`
          } catch (err) {
            ok = false
            why = `list_console_messages 失败: ${err.message}`
          }
        }
        details.push(`  → 断言 [${step.tool}] ${why}`)
        if (!ok) allPass = false
      }
    }
    return { pass: allPass, evidence: details.join('\n') }
  } catch (err) {
    return { pass: false, evidence: `browser 层失败: ${err.message}` }
  } finally {
    if (client) client.close()
  }
}

/** 从 list_console_messages 结果中数 error 级消息 (text 里含 'error' 级别标记) */
function countConsoleErrors(mcpResult) {
  // chrome-devtools-mcp 返回 content[].text, 每行形如 "[error] ..." 或 JSON; 保守统计
  const text = resultText(mcpResult)
  const lines = text.split('\n')
  return lines.filter((l) => /^\[error\]/i.test(l.trim()) || /"level"\s*:\s*"error"/i.test(l)).length
}

/** 执行单个 level, 返回 { level, name, pass, durationMs, evidence } */
async function runLevel(level, cfg, workspaceRoot) {
  const started = Date.now()
  try {
    switch (level.level) {
      case 'unit':
      case 'build':
      case 'api-e2e': {
        const cwd = level.cwd ? path.resolve(workspaceRoot, level.cwd) : workspaceRoot
        const r = await runCmd(level.cmd, { cwd, timeoutMs: level.timeout_ms })
        const pass = r.exitCode === 0
        return {
          level: level.level,
          name: level.name ?? level.cmd,
          pass,
          durationMs: Date.now() - started,
          evidence: r.output + (pass ? '' : `\n[退出码 ${r.exitCode}${r.killed ? ', 超时被杀' : ''}]`),
        }
      }
      case 'state': {
        const probes = level.probes ?? []
        const results = []
        let pass = true
        for (const probe of probes) {
          const r = await runProbe(probe)
          results.push(r.detail)
          if (!r.pass) pass = false
        }
        return {
          level: 'state',
          name: level.name ?? '服务端状态探测',
          pass,
          durationMs: Date.now() - started,
          evidence: results.join('\n'),
        }
      }
      case 'browser': {
        const r = await runBrowserLevel(level, cfg, workspaceRoot)
        return {
          level: 'browser',
          name: level.name ?? '浏览器走查',
          pass: r.pass,
          durationMs: Date.now() - started,
          evidence: r.evidence,
        }
      }
      default:
        return {
          level: level.level ?? 'unknown',
          name: level.name ?? '?',
          pass: false,
          durationMs: Date.now() - started,
          evidence: `未知层级: ${level.level}`,
        }
    }
  } catch (err) {
    return {
      level: level.level ?? 'unknown',
      name: level.name ?? '?',
      pass: false,
      durationMs: Date.now() - started,
      evidence: `层级执行异常: ${err.message}`,
    }
  }
}

/**
 * @param {{workspaceDir:string, target?:string, filterLevels?:string[]|null}} opts
 * @returns {Promise<{allPass:boolean, target:string, summary:string, levels:Array}>}
 */
export async function runRepair(opts) {
  const { workspaceDir, target, filterLevels = null } = opts
  const cfgPath = path.join(workspaceDir, '.repair.yaml')
  if (!existsSync(cfgPath)) {
    return {
      allPass: false,
      target: target ?? '(无)',
      summary: `未找到验证清单: ${cfgPath}`,
      levels: [],
    }
  }
  const cfg = parseMiniYaml(readFileSync(cfgPath, 'utf8'))
  const targets = cfg.targets ?? {}
  const chosen = target ?? Object.keys(targets)[0]
  const t = targets[chosen]
  if (!t) {
    return {
      allPass: false,
      target: chosen,
      summary: `target 不存在: ${chosen} (可用: ${Object.keys(targets).join(', ') || '无'})`,
      levels: [],
    }
  }

  const results = []
  for (const level of t.levels ?? []) {
    if (filterLevels && !filterLevels.includes(level.level)) continue
    results.push(await runLevel(level, cfg, workspaceDir))
  }

  const allPass = results.length > 0 && results.every((r) => r.pass)
  const failed = results.filter((r) => !r.pass).map((r) => r.level)
  return {
    allPass,
    target: chosen,
    summary: allPass
      ? `${results.length} 层验证全部通过`
      : `验证未通过 (失败层: ${failed.join(', ') || '无'})`,
    levels: results,
  }
}
