<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError, type AdventureLogOut } from '../api/client'

const logs = ref<AdventureLogOut[]>([])
const loading = ref(true)
const error = ref('')

function fmtTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${mi}`
}

function rewardChips(log: AdventureLogOut): string[] {
  const chips: string[] = []
  if (log.rewards?.exp) chips.push(`经验 +${log.rewards.exp}`)
  for (const item of log.rewards?.items ?? []) chips.push(`获得「${item}」`)
  return chips
}

onMounted(async () => {
  try {
    const r = await api.getAdventureLogs()
    logs.value = r.logs
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="adv">
    <div class="adv-bg"></div>
    <span class="bg-star s1"></span>
    <span class="bg-star s2"></span>

    <header class="adv-head">
      <h2>冒险日志</h2>
      <p class="sub">你不在的时候，小家伙都在认真生活</p>
    </header>

    <p v-if="loading" class="state-text">加载中…</p>
    <p v-else-if="error" class="state-text">{{ error }}</p>
    <div v-else-if="logs.length === 0" class="state-empty">
      <p class="state-title">还没有冒险记录</p>
      <p class="state-text">离开一段时间再回来，宠物就会出门探险啦</p>
    </div>

    <div v-else class="timeline">
      <article v-for="log in logs" :key="log.id" class="log-card">
        <div class="log-dot"></div>
        <p class="log-time">{{ fmtTime(log.started_at) }} ~ {{ fmtTime(log.ended_at)?.slice(6) }}</p>
        <p class="log-narrative">{{ log.narrative }}</p>
        <div v-if="rewardChips(log).length" class="log-rewards">
          <span v-for="c in rewardChips(log)" :key="c" class="reward-chip">{{ c }}</span>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.adv {
  position: relative;
  flex: 1;
  overflow-y: auto;
  padding: 22px 18px 40px;
}
.adv-bg {
  position: fixed;
  inset: 0;
  background: linear-gradient(180deg, #1b1040 0%, #2c1a4e 55%, #3d2358 100%);
  pointer-events: none;
}
.bg-star {
  position: fixed;
  width: 2px;
  height: 2px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 0 6px 1px rgba(255, 255, 255, 0.7);
  animation: twinkle 3s ease-in-out infinite;
  pointer-events: none;
}
.s1 { top: 90px; left: 34px; }
.s2 { top: 180px; right: 44px; animation-delay: 1.2s; }
@keyframes twinkle {
  0%, 100% { opacity: 0.2; }
  50% { opacity: 0.9; }
}

.adv-head {
  position: relative;
  text-align: center;
  margin-bottom: 22px;
}
.adv-head h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 6px;
  color: var(--color-text);
  text-shadow: 0 2px 16px rgba(255, 200, 140, 0.25);
}
.sub {
  margin: 8px 0 0;
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--color-text-faint);
}

.state-text {
  position: relative;
  text-align: center;
  color: var(--color-text-faint);
  font-size: 13px;
}
.state-empty {
  position: relative;
  text-align: center;
  margin-top: 60px;
}
.state-title {
  font-size: 16px;
  color: var(--color-text-dim);
  margin: 0 0 8px;
}

/* 时间线 */
.timeline {
  position: relative;
  padding-left: 18px;
}
.timeline::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 6px;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, rgba(242, 176, 110, 0.5), rgba(236, 143, 168, 0.15));
}
.log-card {
  position: relative;
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.09);
  backdrop-filter: blur(8px);
}
.log-dot {
  position: absolute;
  left: -18px;
  top: 20px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #f2b06e;
  box-shadow: 0 0 8px rgba(242, 176, 110, 0.8);
}
.log-time {
  margin: 0 0 8px;
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--color-text-faint);
  font-variant-numeric: tabular-nums;
}
.log-narrative {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  color: var(--color-text);
}
.log-rewards {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.reward-chip {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  color: #f7c98a;
  background: rgba(247, 201, 138, 0.12);
  border: 1px solid rgba(247, 201, 138, 0.25);
}
</style>
