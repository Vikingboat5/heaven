/**
 * 迷你 YAML 子集解析器 — 只服务于 .repair.yaml 的受限 schema:
 * 2 空格缩进、key: value 标量、- 列表、'...'/"..." 引号串、行内 JSON 流式值 ([...]/{...})、# 注释。
 * 零依赖, 避免在插件加载环境中做包解析。不支持的语法会抛错(宁错勿猜)。
 */

function stripComment(line) {
  // 引号内不剥注释: 扫描引号状态
  let quote = null
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (quote) {
      if (ch === quote && line[i - 1] !== '\\') quote = null
      continue
    }
    if (ch === "'" || ch === '"') { quote = ch; continue }
    if (ch === '#' && (i === 0 || line[i - 1] === ' ' || line[i - 1] === '\t')) {
      return line.slice(0, i)
    }
  }
  return line
}

function parseScalar(raw) {
  const s = raw.trim()
  if (s === '' ) return null
  if (s === 'true') return true
  if (s === 'false') return false
  if (s === 'null' || s === '~') return null
  if (/^-?\d+$/.test(s)) return parseInt(s, 10)
  if (/^-?\d+\.\d+$/.test(s)) return parseFloat(s)
  if ((s.startsWith('[') && s.endsWith(']')) || (s.startsWith('{') && s.endsWith('}'))) {
    // YAML 流式值 ≈ JSON, 但允许单引号串; 受控 schema 下直接替换后解析
    return JSON.parse(s.replace(/'/g, '"'))
  }
  if ((s.startsWith("'") && s.endsWith("'")) || (s.startsWith('"') && s.endsWith('"'))) {
    return s.slice(1, -1)
  }
  return s
}

function indentOf(line) {
  const m = /^ */.exec(line)
  return m ? m[0].length : 0
}

/**
 * @param {string} text
 * @returns {object}
 */
export function parseMiniYaml(text) {
  const lines = text.split(/\r?\n/)
  const tokens = []
  for (const raw of lines) {
    const line = stripComment(raw)
    if (line.trim() === '') continue
    tokens.push({ indent: indentOf(line), text: line.trim() })
  }
  if (tokens.length === 0) return {}

  function parseBlock(i, baseIndent) {
    // 解析从 i 开始、缩进为 baseIndent 的连续块, 返回 [value, nextIndex]
    if (i >= tokens.length || tokens[i].indent < baseIndent) return [null, i]
    const first = tokens[i]
    if (first.text.startsWith('- ')) return parseList(i, baseIndent)
    if (first.text.startsWith('-')) return parseList(i, baseIndent)
    return parseMap(i, baseIndent)
  }

  function parseMap(i, indent) {
    const out = {}
    while (i < tokens.length && tokens[i].indent === indent) {
      const t = tokens[i]
      if (t.text.startsWith('-')) break // 列表项不归 map
      const colon = t.text.indexOf(':')
      if (colon < 0) throw new Error(`YAML: 期望 key: value, 得到 "${t.text}"`)
      const key = t.text.slice(0, colon).trim()
      const rest = t.text.slice(colon + 1).trim()
      if (rest === '') {
        // 子块
        if (i + 1 < tokens.length && tokens[i + 1].indent > indent) {
          const [child, next] = parseBlock(i + 1, tokens[i + 1].indent)
          out[key] = child
          i = next
        } else {
          out[key] = null
          i++
        }
      } else {
        out[key] = parseScalar(rest)
        i++
      }
    }
    return [out, i]
  }

  function parseList(i, indent) {
    const out = []
    while (i < tokens.length && tokens[i].indent === indent && tokens[i].text.startsWith('-')) {
      const t = tokens[i]
      const rest = t.text.replace(/^-/, '').trim()
      if (rest === '') {
        // 子块
        if (i + 1 < tokens.length && tokens[i + 1].indent > indent) {
          const [child, next] = parseBlock(i + 1, tokens[i + 1].indent)
          out.push(child)
          i = next
        } else {
          out.push(null)
          i++
        }
      } else {
        const colon = rest.indexOf(':')
        // 行内 map: "- key: value", 更深缩进处的延续键归入同一 map
        if (colon > 0 && !rest.startsWith('{') && !rest.startsWith('[')) {
          const key = rest.slice(0, colon).trim()
          const val = rest.slice(colon + 1).trim()
          const item = { [key]: val === '' ? null : parseScalar(val) }
          i++
          if (i < tokens.length && tokens[i].indent > indent && !tokens[i].text.startsWith('-')) {
            const [cont, next] = parseMap(i, tokens[i].indent)
            Object.assign(item, cont)
            i = next
          }
          out.push(item)
        } else {
          out.push(parseScalar(rest))
          i++
        }
      }
    }
    return [out, i]
  }

  const [root, next] = parseBlock(0, tokens[0].indent)
  if (next < tokens.length) throw new Error(`YAML: 无法解析的行 "${tokens[next].text}"`)
  return root ?? {}
}
