/** 注册级验证: 用真实 dsh-tools defineTool + mock ctx 走完整注册与干跑 */
import { defineTool } from '@deepseek-ai/dsh-tools'

const mod = await import('./index.js')
const defs = []
mod.apply({ tools: { register: (d) => defs.push(d) } })

console.log('[OK] 注册成功:', defs[0].name, '| 超时:', defs[0].timeoutMs)
const out = await defs[0].execute({ target: 'no-such-target' }, {})
console.log('[OK] 干跑 execute:', JSON.stringify({ allPass: out.allPass, summary: out.summary }))
if (out.allPass === false && (out.summary.includes('不存在') || out.summary.includes('未找到'))) {
  console.log('[PASS] 注册 + 执行链路全部通过')
  process.exit(0)
} else {
  console.error('[FAIL] 干跑结果不符合预期')
  process.exit(1)
}
