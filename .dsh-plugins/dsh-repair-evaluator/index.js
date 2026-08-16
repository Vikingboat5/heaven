/**
 * dsh-repair-evaluator — 修复闭环验证器插件
 *
 * 注册模型工具 `repair_verify`: 读取会话工作区的 .repair.yaml, 按 target 逐层执行
 * unit/build/state/api-e2e/browser 验证, 返回结构化证据 (allPass/levels/evidence)。
 * 配合修复闭环协议: 验证未全绿时不得向用户宣布修复完成。
 *
 * 依赖: @deepseek-ai/dsh-tools (defineTool) — 由 profile node_modules 提供。
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { runRepair } from './lib/engine.js'

export const name = 'repair-evaluator'
export const inject = ['tools']

const DESCRIPTION = [
  '运行工作区修复验证清单 (.repair.yaml): 按 target 逐层执行 unit(单元测试)/build(构建检查)/state(服务端状态探测)/api-e2e(API 全链路探针)/browser(真实浏览器走查) 验证,',
  '收集客观证据并返回 allPass 判定。',
  '用法: 修复改动完成后、向用户宣布"修复完成"之前必须调用; 未全绿 (allPass=false) 时继续修复或回退, 禁止宣布完成。',
  '无 target 参数时取 .repair.yaml 中第一个 target; levels 参数可按层级过滤。',
].join(' ')

const LEVEL_RESULT = {
  type: 'object',
  additionalProperties: false,
  properties: {
    level: { type: 'string', required: true },
    name: { type: 'string', required: true },
    pass: { type: 'boolean', required: true },
    durationMs: { type: 'integer', required: true },
    evidence: { type: 'string', required: true },
  },
}

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: 'repair_verify',
    description: DESCRIPTION,
    parameters: {
      target: {
        type: 'string',
        required: false,
        description: '.repair.yaml 中的目标名; 省略时取第一个 target',
      },
      levels: {
        type: 'array',
        required: false,
        description: '按层级过滤执行 (unit/build/state/api-e2e/browser); 省略时执行全部',
        items: { type: 'string' },
      },
      cwd: {
        type: 'string',
        required: false,
        description: '工作区根目录(含 .repair.yaml); 省略时取会话 cwd',
      },
    },
    timeoutMs: 600000,
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          allPass: { type: 'boolean', required: true },
          target: { type: 'string', required: true },
          summary: { type: 'string', required: true },
          levels: { type: 'array', required: true, items: LEVEL_RESULT },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text: `修复验证 [${value.target}]: ${value.allPass ? '✅ 全部通过' : '❌ 未通过'} — ${value.summary}`,
      }],
    },
    async execute(args, exec) {
      const cwd = args.cwd
        ?? exec?.agent?.session?.header?.cwd
        ?? process.cwd()
      return runRepair({
        workspaceDir: cwd,
        target: args.target,
        filterLevels: args.levels && args.levels.length > 0 ? args.levels : null,
      })
    },
    presentCall: (args) => ({
      card: 'generic',
      title: '修复验证',
      kind: 'other',
      rawInput: args.target ?? '(默认 target)',
    }),
  }))
}
