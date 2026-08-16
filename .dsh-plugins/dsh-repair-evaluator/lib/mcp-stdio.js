/**
 * MCP stdio 客户端 (JSON-RPC 2.0, 换行分隔帧) — 最小实现, 只服务 browser 层验证:
 * spawn MCP server (如 chrome-devtools-mcp), initialize, callTool, close。
 */

import { spawn } from 'node:child_process'

export class McpStdioClient {
  /**
   * @param {{command:string, args?:string[], cwd?:string, env?:Record<string,string>, startupTimeoutMs?:number}} cfg
   */
  static async start(cfg) {
    const child = spawn(cfg.command, cfg.args ?? [], {
      cwd: cfg.cwd,
      env: { ...process.env, ...(cfg.env ?? {}) },
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true,
      // Windows 上 npx 是 .cmd shim, 无 shell 的 spawn 会 ENOENT
      shell: process.platform === 'win32',
    })
    const client = new McpStdioClient(child)

    // 竞争: spawn 错误 (ENOENT 等) vs initialize 响应
    const spawnError = new Promise((_, reject) => child.once('error', reject))
    spawnError.catch(() => {}) // 竞争失败方静默, 避免 unhandled rejection

    const init = client.request('initialize', {
      protocolVersion: cfg.protocolVersion ?? '2025-03-26',
      capabilities: {},
      clientInfo: { name: 'dsh-repair-evaluator', version: '0.1.0' },
    }, cfg.startupTimeoutMs ?? 60000).then(() => {
      client._send({ jsonrpc: '2.0', method: 'notifications/initialized' })
      return client
    })

    return Promise.race([init, spawnError])
  }

  constructor(child) {
    this.child = child
    this._nextId = 1
    this._pending = new Map()
    this._buffer = ''
    this._closed = false
    this._onExit = null
    child.stdout.on('data', (chunk) => this._onData(chunk))
    child.stderr.on('data', (chunk) => {
      // 保留最近 stderr 用于诊断
      this._stderrTail = (this._stderrTail ?? '' + chunk.toString()).slice(-2000)
    })
  }

  _fail(err) {
    for (const [, p] of this._pending) p.reject(err)
    this._pending.clear()
  }

  _onData(chunk) {
    this._buffer += chunk.toString('utf8')
    let idx
    while ((idx = this._buffer.indexOf('\n')) >= 0) {
      const line = this._buffer.slice(0, idx).trim()
      this._buffer = this._buffer.slice(idx + 1)
      if (!line) continue
      let msg
      try { msg = JSON.parse(line) } catch { continue }
      if (msg.id !== undefined && this._pending.has(msg.id)) {
        const { resolve, reject } = this._pending.get(msg.id)
        this._pending.delete(msg.id)
        if (msg.error) reject(new Error(`MCP 错误 ${msg.error.code}: ${msg.error.message}`))
        else resolve(msg.result)
      }
    }
  }

  _send(obj) {
    this.child.stdin.write(JSON.stringify(obj) + '\n')
  }

  request(method, params, timeoutMs = 60000) {
    if (this._closed) return Promise.reject(new Error('MCP 客户端已关闭'))
    const id = this._nextId++
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this._pending.delete(id)
        reject(new Error(`MCP 请求超时: ${method}`))
      }, timeoutMs)
      this._pending.set(id, {
        resolve: (v) => { clearTimeout(timer); resolve(v) },
        reject: (e) => { clearTimeout(timer); reject(e) },
      })
      this._send({ jsonrpc: '2.0', id, method, params })
    })
  }

  async callTool(name, args, timeoutMs = 60000) {
    return this.request('tools/call', { name, arguments: args ?? {} }, timeoutMs)
  }

  async listTools(timeoutMs = 60000) {
    return this.request('tools/list', {}, timeoutMs)
  }

  close() {
    this._closed = true
    this._onExit = null
    try { this.child.stdin.end() } catch { /* noop */ }
    try { this.child.kill() } catch { /* noop */ }
  }
}

/** 从 MCP 结果中提取文本 (content[].text 拼接) */
export function resultText(result) {
  const content = result?.content ?? []
  return content
    .filter((b) => b && b.type === 'text' && typeof b.text === 'string')
    .map((b) => b.text)
    .join('\n')
}
