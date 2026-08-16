import { readFileSync } from 'node:fs'
import { parseMiniYaml } from './lib/yaml-mini.js'

const raw = readFileSync('../../.repair.yaml', 'utf8')
// 逐行打印 tokens
const lines = raw.split(/\r?\n/)
lines.forEach((l, i) => {
  if (l.trim()) console.log(`${String(i).padStart(3)} indent=${l.match(/^ */)[0].length} | ${l.trim().slice(0, 60)}`)
})
console.log('--- 尝试解析前 12 行 (截取 targets 之前) ---')
const head = lines.slice(0, 9).join('\n')
try {
  console.log(JSON.stringify(parseMiniYaml(head), null, 2))
} catch (e) {
  console.log('ERROR:', e.message)
}
