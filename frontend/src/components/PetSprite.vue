<script setup lang="ts">
/** 宠物精灵动画组件 (S3.3): 按 manifest 播放 PNG 序列帧
 *
 * 素材由后端 petgen 管线生成: /static/pets/{id}/manifest.json + frames/{action}_{i}.png
 * manifest 缺动作/加载失败 → emit('error'), 由父组件降级预制 SVG
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

interface ActionMeta {
  frames: number
  sequence: number[]
  frame_ms: number
}
interface Manifest {
  pet_id: number
  style: string
  actions: Record<string, ActionMeta>
}

const props = withDefaults(defineProps<{
  petId: number
  action?: string
  breathing?: boolean   // CSS 呼吸浮动
}>(), { action: 'idle', breathing: true })

const emit = defineEmits<{ (e: 'error'): void; (e: 'ready'): void }>()

const manifest = ref<Manifest | null>(null)
// 双层交叉淡化 v2: 两个常驻 img 交替切换 opacity (transition),
// 不用 :key 重建元素+animation —— 实测后者透明度会卡在 0 (元素反复重建动画不前进)
const srcA = ref('')
const srcB = ref('')
const aVisible = ref(true)
const fadeMs = ref(90)           // 淡化时长 = 帧间隔的 60%
const failed = ref(false)
// 缓存破坏: manifest 的 Last-Modified 作版本号, 重新生成形象后帧 URL 自动更新
// (否则浏览器缓存会把新旧两套帧混着播, 看起来"两个形象交替闪烁")
const version = ref('')
let timer: ReturnType<typeof setInterval> | null = null
let tick = 0

const frameUrl = (action: string, i: number) =>
  `/static/pets/${props.petId}/frames/${action}_${i}.png${version.value ? `?v=${version.value}` : ''}`

function stop() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

/** 新帧进入隐藏层 → 翻转可见性, CSS transition 完成交叉淡化 */
function advance(url: string) {
  if (aVisible.value) {
    srcB.value = url
    aVisible.value = false
  } else {
    srcA.value = url
    aVisible.value = true
  }
}

function play(actionName: string) {
  stop()
  const meta = manifest.value?.actions[actionName]
  if (!meta) {
    // 动作不存在: 回退 idle; idle 也没有则报降级
    if (actionName !== 'idle') return play('idle')
    failed.value = true
    emit('error')
    return
  }
  tick = 0
  fadeMs.value = Math.max(60, Math.round(meta.frame_ms * 0.6))
  srcA.value = frameUrl(actionName, meta.sequence[0])
  srcB.value = ''
  aVisible.value = true
  timer = setInterval(() => {
    tick++
    advance(frameUrl(actionName, meta.sequence[tick % meta.sequence.length]))
  }, meta.frame_ms)
}

/** 单次播放某动作后回 idle (H6 生活动作编排用); 动作缺失则静默跳过 */
function playOnce(actionName: string) {
  const meta = manifest.value?.actions[actionName]
  if (!meta || actionName === 'idle') return
  stop()
  tick = 0
  fadeMs.value = Math.max(60, Math.round(meta.frame_ms * 0.6))
  srcA.value = frameUrl(actionName, meta.sequence[0])
  srcB.value = ''
  aVisible.value = true
  timer = setInterval(() => {
    tick++
    if (tick >= meta.sequence.length) {
      play('idle')
      return
    }
    advance(frameUrl(actionName, meta.sequence[tick]))
  }, meta.frame_ms)
}

/** 当前 manifest 实际可用的动作 (生活动作可能因 QC 失败被跳过) */
function availableActions(): string[] {
  return Object.keys(manifest.value?.actions ?? {})
}

onMounted(async () => {
  try {
    const resp = await fetch(`/static/pets/${props.petId}/manifest.json`, { cache: 'no-cache' })
    if (!resp.ok) throw new Error(String(resp.status))
    version.value = encodeURIComponent(resp.headers.get('last-modified') ?? String(Date.now()))
    manifest.value = await resp.json()
    // 预加载当前动作全部帧, 避免播放时闪烁
    const meta = manifest.value!.actions[props.action]
    if (!meta) throw new Error('no action')
    meta.sequence.forEach((i) => { new Image().src = frameUrl(props.action, i) })
    play(props.action)
    emit('ready')
  } catch {
    failed.value = true
    emit('error')
  }
})

watch(() => props.action, (a) => { if (manifest.value) play(a) })
onBeforeUnmount(stop)

defineExpose({ play, playOnce, availableActions })
</script>

<template>
  <!-- 双层交叉淡化: 两个常驻 img 交替淡入淡出 (transition 驱动, 无元素重建) -->
  <div v-if="!failed && srcA" class="sprite-stack" :class="{ breathing }">
    <img
      class="pet-sprite"
      :class="{ pixelated: manifest?.style === 'pixel' }"
      :src="srcA"
      :style="{ opacity: aVisible ? 1 : 0, transitionDuration: `${fadeMs}ms` }"
      alt="宠物"
      draggable="false"
    />
    <img
      v-if="srcB"
      class="pet-sprite"
      :class="{ pixelated: manifest?.style === 'pixel' }"
      :src="srcB"
      :style="{ opacity: aVisible ? 0 : 1, transitionDuration: `${fadeMs}ms` }"
      alt=""
      draggable="false"
    />
  </div>
</template>

<style scoped>
.sprite-stack {
  position: relative;
  width: 100%;
  height: 100%;
}
.pet-sprite {
  position: absolute;
  inset: 0;
  width: 100%; height: 100%; object-fit: contain;
  user-select: none; pointer-events: none;
  transition: opacity var(--motion-fast) var(--ease-out);
}
.pixelated { image-rendering: pixelated; }
.breathing { animation: sprite-breathe 2.8s ease-in-out infinite; }
@keyframes sprite-breathe {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}
</style>
