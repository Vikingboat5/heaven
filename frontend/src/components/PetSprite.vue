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
const currentSrc = ref('')
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
  currentSrc.value = frameUrl(actionName, meta.sequence[0])
  timer = setInterval(() => {
    tick++
    currentSrc.value = frameUrl(actionName, meta.sequence[tick % meta.sequence.length])
  }, meta.frame_ms)
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

defineExpose({ play })
</script>

<template>
  <img
    v-if="!failed && currentSrc"
    class="pet-sprite"
    :class="{ pixelated: manifest?.style === 'pixel', breathing }"
    :src="currentSrc"
    alt="宠物"
    draggable="false"
  />
</template>

<style scoped>
.pet-sprite {
  width: 100%; height: 100%; object-fit: contain;
  user-select: none; pointer-events: none;
}
.pixelated { image-rendering: pixelated; }
.breathing { animation: sprite-breathe 2.8s ease-in-out infinite; }
@keyframes sprite-breathe {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}
</style>
