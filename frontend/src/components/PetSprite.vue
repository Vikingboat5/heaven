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
  breathing?: boolean   // CSS 呼吸浮动 (视频帧自带微动, 已废弃——叠加会漂)
}>(), { action: 'idle', breathing: false })

const emit = defineEmits<{ (e: 'error'): void; (e: 'ready'): void }>()

const manifest = ref<Manifest | null>(null)
// 交叉淡化 v3: 底层常驻当前帧(全程不透明), 顶层只淡入新帧;
// 淡入完成后底层同步、顶层淡出(底下已是同一张图, 无感)。
// (v2 两层各半透会透底 = 每帧暗一下的"诡异闪烁"; v1 :key重建动画卡 0)
const baseSrc = ref('')
const topSrc = ref('')
const topOn = ref(false)
const dipping = ref(false)        // 跨动作 dip 过渡: 旧帧淡出→换新→淡入 (绝不两帧重叠)
const fadeMs = ref(90)           // 淡化时长 = 帧间隔的 60%
const failed = ref(false)
// 缓存破坏: manifest 的 Last-Modified 作版本号, 重新生成形象后帧 URL 自动更新
// (否则浏览器缓存会把新旧两套帧混着播, 看起来"两个形象交替闪烁")
const version = ref('')
let timer: ReturnType<typeof setInterval> | null = null
let flipTimer: ReturnType<typeof setTimeout> | null = null
let tick = 0

const frameUrl = (action: string, i: number) =>
  `/static/pets/${props.petId}/frames/${action}_${i}.png${version.value ? `?v=${version.value}` : ''}`

function stop() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  if (flipTimer) {
    clearTimeout(flipTimer)
    flipTimer = null
  }
}

/** 新帧在顶层淡入 (底层旧帧全程不透明垫底); 完成后底层同步, 顶层淡出 */
function advance(url: string) {
  if (fadeMs.value <= 0) {   // 帧间隔密的动作(视频采帧)直接硬切, 不淡化
    // 必须取消过渡淡入挂的同步定时器——否则它到点会把画面拉回旧帧(瞬移+闪的真凶)
    if (flipTimer) { clearTimeout(flipTimer); flipTimer = null }
    baseSrc.value = url
    topOn.value = false
    return
  }
  if (flipTimer) clearTimeout(flipTimer)
  topSrc.value = url
  topOn.value = true
  flipTimer = setTimeout(() => {
    baseSrc.value = url
    topOn.value = false
    flipTimer = null
  }, fadeMs.value + 30)
}

/** 淡化策略: 稀疏帧(精灵表≥120ms)给短淡化; 密集帧(视频采帧)硬切 */
function fadeFor(frameMs: number): number {
  if (frameMs < 120) return 0
  return Math.min(60, Math.max(25, Math.round(frameMs * 0.35)))
}

function play(actionName: string) {
  if (timer) { clearInterval(timer); timer = null }   // 只停帧定时器, 保留过渡 flipTimer
  const meta = manifest.value?.actions[actionName]
  if (!meta) {
    // 动作不存在: 回退 idle; idle 也没有则报降级
    if (actionName !== 'idle') return play('idle')
    failed.value = true
    emit('error')
    return
  }
  tick = 0
  const first = frameUrl(actionName, meta.sequence[0])
  const startLoop = () => {
    fadeMs.value = fadeFor(meta.frame_ms)
    timer = setInterval(() => {
      tick++
      advance(frameUrl(actionName, meta.sequence[tick % meta.sequence.length]))
    }, meta.frame_ms)
  }
  if (!baseSrc.value) {
    baseSrc.value = first
    startLoop()
  } else if (baseSrc.value !== first) {
    // 跨动作过渡 = dip: 旧帧淡出→换新→淡入 (不重叠; 2026-09-20 修"两个动画重叠")
    dipping.value = true
    setTimeout(() => {
      baseSrc.value = first
      dipping.value = false
      startLoop()
    }, 95)
  } else {
    startLoop()
  }
}

/** 单次播放某动作后回默认动作 (H6 生活动作编排用); 动作缺失则静默跳过 */
function playOnce(actionName: string) {
  const meta = manifest.value?.actions[actionName]
  if (!meta || actionName === props.action) return
  if (timer) { clearInterval(timer); timer = null }
  tick = 0
  const first = frameUrl(actionName, meta.sequence[0])
  const startLoop = () => {
    fadeMs.value = fadeFor(meta.frame_ms)
    timer = setInterval(() => {
      tick++
      if (tick >= meta.sequence.length) {
        play(props.action)   // 回到配置的默认动作 (不一定是 idle)
        return
      }
      advance(frameUrl(actionName, meta.sequence[tick]))
    }, meta.frame_ms)
  }
  if (!baseSrc.value) {
    baseSrc.value = first
    startLoop()
  } else if (baseSrc.value !== first) {
    dipping.value = true
    setTimeout(() => {
      baseSrc.value = first
      dipping.value = false
      startLoop()
    }, 95)
  } else {
    startLoop()
  }
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
    // 预加载当前动作全部帧 + 其余所有动作的首帧 (跨动作切换不闪)
    const meta = manifest.value!.actions[props.action]
    if (!meta) throw new Error('no action')
    meta.sequence.forEach((i) => { new Image().src = frameUrl(props.action, i) })
    for (const [name, m] of Object.entries(manifest.value!.actions)) {
      if (name !== props.action && m.sequence.length) new Image().src = frameUrl(name, m.sequence[0])
    }
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
  <!-- 双层交叉淡化: 底层当前帧全程不透明, 顶层新帧淡入; 完成后底层同步顶层淡出 -->
  <div v-if="!failed && baseSrc" class="sprite-stack" :class="{ breathing }">
    <img
      class="pet-sprite"
      :class="{ pixelated: manifest?.style === 'pixel' }"
      :src="baseSrc"
      :style="{ opacity: dipping ? 0 : 1 }"
      alt="宠物"
      draggable="false"
    />
    <img
      v-if="topSrc"
      class="pet-sprite layer-top"
      :class="{ pixelated: manifest?.style === 'pixel' }"
      :src="topSrc"
      :style="{ opacity: topOn ? 1 : 0, transitionDuration: `${fadeMs}ms` }"
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
  transition: opacity 90ms var(--ease-out);   /* dip 过渡用 (跨动作) */
}
.layer-top {
  transition: opacity var(--motion-fast) var(--ease-out);
}
.pixelated { image-rendering: pixelated; }
.breathing { animation: sprite-breathe 2.8s ease-in-out infinite; }
@keyframes sprite-breathe {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}
</style>
