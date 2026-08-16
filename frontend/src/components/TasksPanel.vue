<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, ApiError, type TaskOut } from '../api/client'

const emit = defineEmits<{ close: [] }>()

const tasks = ref<TaskOut[]>([])
const loading = ref(true)
const claiming = ref('')
const toast = ref('')

const daily = computed(() => tasks.value.filter((t) => t.kind === 'daily' || t.code.startsWith('daily')))
const achievements = computed(() => tasks.value.filter((t) => !daily.value.includes(t)))

function rewardText(t: TaskOut): string {
  const r = t.reward
  if (r.type === 'exp') return `${r.value} 经验`
  if (r.type === 'hatch_value') return `孵化值 +${r.value}`
  if (r.type === 'item') return `${r.item_name} ×${r.value}`
  return `${r.value}`
}

function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => (toast.value = ''), 2400)
}

async function load() {
  loading.value = true
  try {
    const r = await api.getTasks()
    tasks.value = r.tasks
  } catch (e) {
    showToast(e instanceof ApiError ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function claim(t: TaskOut) {
  if (claiming.value || t.claimed || t.progress < t.target) return
  claiming.value = t.code
  try {
    const r = await api.claimTask(t.code)
    showToast(`领取成功：${rewardText(t)}`)
    await load()
    void r
  } catch (e) {
    showToast(e instanceof ApiError ? e.message : '领取失败')
  } finally {
    claiming.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="mask" @click.self="emit('close')">
    <div class="drawer">
      <header class="drawer-head">
        <h3>任务</h3>
        <button class="close" @click="emit('close')">✕</button>
      </header>

      <p v-if="loading" class="empty">加载中…</p>
      <template v-else>
        <p v-if="daily.length" class="group-title">每日</p>
        <div v-for="t in daily" :key="t.code" class="task" :class="{ done: t.claimed }">
          <div class="task-info">
            <p class="task-name">{{ t.name }}</p>
            <p class="task-desc">{{ t.desc }}</p>
            <div class="task-track">
              <div class="task-fill" :style="{ width: Math.min(100, (t.progress / t.target) * 100) + '%' }"></div>
            </div>
            <p class="task-progress">{{ Math.min(t.progress, t.target) }}/{{ t.target }} · 奖励：{{ rewardText(t) }}</p>
          </div>
          <button
            class="claim"
            :disabled="t.claimed || t.progress < t.target || claiming === t.code"
            @click="claim(t)"
          >
            {{ t.claimed ? '已领取' : t.progress >= t.target ? '领取' : '进行中' }}
          </button>
        </div>

        <p v-if="achievements.length" class="group-title">成就</p>
        <div v-for="t in achievements" :key="t.code" class="task" :class="{ done: t.claimed }">
          <div class="task-info">
            <p class="task-name">{{ t.name }}</p>
            <p class="task-desc">{{ t.desc }}</p>
            <div class="task-track">
              <div class="task-fill" :style="{ width: Math.min(100, (t.progress / t.target) * 100) + '%' }"></div>
            </div>
            <p class="task-progress">{{ Math.min(t.progress, t.target) }}/{{ t.target }} · 奖励：{{ rewardText(t) }}</p>
          </div>
          <button
            class="claim"
            :disabled="t.claimed || t.progress < t.target || claiming === t.code"
            @click="claim(t)"
          >
            {{ t.claimed ? '已领取' : t.progress >= t.target ? '领取' : '进行中' }}
          </button>
        </div>
      </template>

      <div v-if="toast" class="panel-toast">{{ toast }}</div>
    </div>
  </div>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  background: rgba(10, 5, 26, 0.6);
  backdrop-filter: blur(3px);
  z-index: 50;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.drawer {
  position: relative;
  width: 100%;
  max-width: 480px;
  max-height: 76vh;
  overflow-y: auto;
  background: linear-gradient(180deg, #241645, #1a0f38);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-bottom: none;
  border-radius: 22px 22px 0 0;
  padding: 18px 18px 28px;
  animation: slide-up 0.28s ease;
}
@keyframes slide-up {
  from { transform: translateY(40px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.drawer-head h3 {
  margin: 0;
  font-size: 17px;
  letter-spacing: 3px;
  color: var(--color-gold);
}
.close {
  border: none;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(253, 240, 220, 0.7);
  width: 30px;
  height: 30px;
  border-radius: 50%;
  cursor: pointer;
}
.group-title {
  margin: 14px 2px 8px;
  font-size: 12px;
  letter-spacing: 2px;
  color: var(--color-text-faint);
}
.task {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 10px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.task.done {
  opacity: 0.55;
}
.task-info {
  flex: 1;
  min-width: 0;
}
.task-name {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}
.task-desc {
  margin: 3px 0 8px;
  font-size: 12px;
  color: var(--color-text-dim);
}
.task-track {
  height: 5px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  overflow: hidden;
}
.task-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #f2b06e, #ec8fa8);
  transition: width 0.4s;
}
.task-progress {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--color-text-faint);
}
.claim {
  flex-shrink: 0;
  padding: 8px 16px;
  border: none;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  background: linear-gradient(135deg, #f2a56e, #e77fa2);
  color: #fff;
  box-shadow: 0 4px 12px rgba(231, 127, 162, 0.3);
}
.claim:disabled {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(253, 240, 220, 0.4);
  box-shadow: none;
  cursor: not-allowed;
}
.empty {
  text-align: center;
  color: var(--color-text-faint);
  padding: 30px 0;
}
.panel-toast {
  position: sticky;
  bottom: 8px;
  margin: 10px auto 0;
  width: fit-content;
  padding: 9px 18px;
  border-radius: 999px;
  background: rgba(242, 165, 110, 0.92);
  color: #2b1743;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
}
</style>
