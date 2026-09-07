<script setup lang="ts">
/**
 * 日记页 (spec §11.3 拆分为独立页, 2026-09-06): 旅行日记列表(时间倒序)
 * C2 日记列表; C5 收获明细含交换留痕; H8 首到某地的明信片展示
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, ApiError, itemImageUrl, type AdventureLogOut, type CatalogItemOut } from '../api/client'

const router = useRouter()

const logs = ref<AdventureLogOut[]>([])
const items = ref<CatalogItemOut[]>([])
const expandedLog = ref<number | null>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const [l, c] = await Promise.all([api.getAdventureLogs(), api.getCatalog()])
    logs.value = l.logs
    items.value = c.items
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})

function fmtTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${mi}`
}

/** 日记条目里按 id 取物品名 (消耗/交换的 id 可能不在收获列表) */
function logItemName(log: AdventureLogOut, itemId: string): string {
  const inRewards = (log.rewards?.items ?? []).find((i) => i.item_id === itemId)
  if (inRewards) return inRewards.name
  const inCatalog = items.value.find((i) => i.item_id === itemId)
  return inCatalog?.name ?? itemId
}
</script>

<template>
  <div class="diary">
    <div class="diary-bg"></div>
    <span class="bg-star s1"></span>
    <span class="bg-star s2"></span>

    <header class="diary-head">
      <button class="back" @click="router.push('/')">‹ 回家</button>
      <h2>日记</h2>
    </header>

    <p v-if="loading" class="state-text">加载中…</p>
    <p v-else-if="error" class="state-text">{{ error }}</p>

    <div v-else-if="logs.length === 0" class="state-empty">
      <p class="state-title">还没有旅行日记</p>
      <p class="state-text">离开一段时间再回来，小家伙就会出门探险啦</p>
    </div>

    <div v-else class="timeline stagger">
      <article v-for="log in logs" :key="log.id" class="log-card" @click="expandedLog = expandedLog === log.id ? null : log.id">
        <div class="log-dot"></div>
        <p class="log-time">{{ fmtTime(log.started_at) }} · {{ log.dest || '远方' }}</p>
        <!-- H8: 明信片 (首到某地的打卡照) -->
        <img
          v-if="log.rewards?.postcard"
          :src="log.rewards.postcard"
          :alt="`来自${log.dest}的明信片`"
          class="postcard"
        />
        <p v-else-if="log.rewards?.postcard_pending" class="postcard-pending">📮 明信片还在路上…</p>
        <p class="log-narrative">{{ log.narrative }}</p>
        <div class="log-rewards">
          <span v-if="log.rewards?.exp" class="reward-chip">经验 +{{ log.rewards.exp }}</span>
          <img
            v-for="(it, idx) in log.rewards?.items ?? []"
            :key="idx"
            :src="itemImageUrl(it.image)"
            :alt="it.name"
            :title="it.count > 1 ? `${it.name} ×${it.count}` : it.name"
            class="reward-thumb"
            :class="`rarity-${it.rarity}`"
          />
        </div>
        <!-- 展开: 事件时间线 + 收获明细 + 交换留痕 (C5) -->
        <div v-if="expandedLog === log.id" class="log-detail">
          <p v-for="(ev, i) in log.events ?? []" :key="i" class="log-event">
            <span class="log-event-time">{{ ev.time?.slice(11, 16) }}</span> {{ ev.text }}
          </p>
          <p v-if="log.rewards?.exchanged" class="log-exchange">
            用「{{ logItemName(log, log.rewards.exchanged.gave) }}」换到了「{{ logItemName(log, log.rewards.exchanged.got) }}」
          </p>
          <p v-else-if="log.rewards?.gift_returned" class="log-exchange">把伴手礼又抱回来了（有点害羞）</p>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.diary {
  position: relative;
  flex: 1;
  padding: 20px 20px 40px;
  background: linear-gradient(180deg, #1a1038 0%, #150c2e 60%, #1e1242 100%);
  overflow: hidden;
}
.diary-bg { display: none; }
.bg-star {
  position: absolute;
  width: 3px; height: 3px; border-radius: 50%;
  background: #fff; opacity: 0.5;
  animation: twinkle 3.2s ease-in-out infinite;
}
.bg-star.s1 { top: 18%; left: 20%; }
.bg-star.s2 { top: 12%; right: 22%; animation-delay: 1.6s; }
@keyframes twinkle { 0%, 100% { opacity: 0.2; } 50% { opacity: 0.7; } }

.diary-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
}
.diary-head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-xxl);
  font-weight: 600;
  letter-spacing: 6px;
  color: var(--color-text);
}
.back {
  padding: 6px 12px;
  border: 1px solid var(--color-glass-border);
  border-radius: 999px;
  background: var(--color-glass);
  color: var(--color-text-dim);
  font-size: var(--fs-md);
  cursor: pointer;
}

.state-text { text-align: center; color: var(--color-text-faint); font-size: var(--fs-md); }
.state-empty { text-align: center; margin-top: 60px; }
.state-title { font-size: var(--fs-xl); color: var(--color-text-dim); margin: 0 0 8px; }

.timeline { display: flex; flex-direction: column; gap: 14px; }
.log-card {
  position: relative;
  padding: 14px 16px 14px 26px;
  background: var(--color-glass);
  border: 1px solid var(--color-glass-border);
  border-radius: 16px;
  cursor: pointer;
  backdrop-filter: blur(14px);
}
.log-dot {
  position: absolute;
  left: 10px; top: 18px;
  width: 7px; height: 7px; border-radius: 50%;
  background: #f2a56e;
  box-shadow: 0 0 8px rgba(242, 165, 110, 0.8);
}
.log-time { margin: 0 0 6px; font-size: var(--fs-xs); color: var(--color-text-faint); letter-spacing: 1px; }
.log-narrative { margin: 0; font-size: var(--fs-lg); line-height: 1.75; color: var(--color-text); white-space: pre-line; }

.postcard {
  width: 100%;
  border-radius: 10px;
  margin: 4px 0 10px;
  border: 3px solid #f7ecd4;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.4);
  rotate: -0.6deg;
}
.postcard-pending {
  margin: 4px 0 10px;
  font-size: var(--fs-sm);
  color: var(--color-text-faint);
}

.log-rewards { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; align-items: center; }
.reward-chip {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: var(--fs-xs);
  color: #f7c98a;
  background: rgba(247, 201, 138, 0.1);
  border: 1px solid rgba(247, 201, 138, 0.25);
}
.reward-thumb { width: 30px; height: 30px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.12); }
.reward-thumb.rarity-rare { border-color: rgba(120, 170, 255, 0.55); }
.reward-thumb.rarity-epic { border-color: rgba(247, 201, 100, 0.65); }

.log-detail { margin-top: 10px; border-top: 1px dashed rgba(255, 255, 255, 0.12); padding-top: 8px; }
.log-event { margin: 4px 0; font-size: var(--fs-sm); color: var(--color-text-dim); line-height: 1.6; }
.log-event-time { color: var(--color-text-faint); font-variant-numeric: tabular-nums; }
.log-exchange { margin: 8px 0 0; font-size: var(--fs-sm); color: #f7c98a; }
</style>
