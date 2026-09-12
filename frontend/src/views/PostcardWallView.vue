<script setup lang="ts">
/**
 * 明信片墙 (规范 v1.3): 它去过的每个地方都钉一张照片
 * 软木墙质感 + 拍立得纸框 + 红图钉 + 错落倾斜
 */
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api, ApiError, type AdventureLogOut } from '../api/client'

const router = useRouter()
const logs = ref<AdventureLogOut[]>([])
const loading = ref(true)
const error = ref('')

const postcards = computed(() => logs.value.filter((l) => l.rewards?.postcard))

onMounted(async () => {
  try {
    const r = await api.getAdventureLogs(30)
    logs.value = r.logs
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})

function fmtDay(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
</script>

<template>
  <div class="wall-page">
    <header class="wall-head">
      <button class="back" @click="router.push('/')">‹ 回家</button>
      <h2>明信片墙</h2>
    </header>
    <p class="wall-sub">它去过的每个地方，都钉了一张照片</p>

    <p v-if="loading" class="state-text">加载中…</p>
    <p v-else-if="error" class="state-text">{{ error }}</p>
    <div v-else-if="postcards.length === 0" class="state-empty">
      <p class="state-title">墙上还空空的</p>
      <p class="state-text">它第一次去一个新地方时，就会钉上一张</p>
    </div>

    <div v-else class="wall-grid stagger">
      <figure
        v-for="(p, i) in postcards"
        :key="p.id"
        class="wall-item"
        :style="{ rotate: `${((i * 37) % 5) - 2.4}deg` }"
      >
        <span class="pin"></span>
        <img :src="p.rewards!.postcard!" :alt="`来自${p.dest}的明信片`" />
        <figcaption>{{ p.dest || '远方' }} · {{ fmtDay(p.ended_at) }}</figcaption>
      </figure>
    </div>
  </div>
</template>

<style scoped>
.wall-page {
  flex: 1;
  padding: 18px 20px 40px;
  background:
    linear-gradient(rgba(21, 12, 46, 0.55), rgba(21, 12, 46, 0.72)),
    url('/static/ui/cork_board.png') center / 560px repeat;
}
.wall-head {
  display: flex;
  align-items: center;
  gap: 14px;
}
.wall-head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-xxl);
  font-weight: 600;
  letter-spacing: 6px;
  color: var(--color-text);
  text-shadow: 0 1px 6px rgba(10, 6, 20, 0.7);
}
.wall-sub {
  margin: 4px 0 16px;
  font-size: var(--fs-xs);
  color: var(--color-text-dim);
  letter-spacing: 1px;
  text-shadow: 0 1px 4px rgba(10, 6, 20, 0.7);
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
.state-text { text-align: center; color: var(--color-text-dim); font-size: var(--fs-md); margin-top: 40px; }
.state-empty { text-align: center; margin-top: 60px; }
.state-title { font-size: var(--fs-xl); color: var(--color-text-dim); margin: 0 0 8px; }

/* 钉在墙上的拍立得 */
.wall-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px 14px;
}
.wall-item {
  position: relative;
  margin: 0;
  background: #fbf6ea;
  padding: 8px 8px 10px;
  border-radius: 4px;
  box-shadow: 0 8px 18px rgba(10, 6, 20, 0.55);
  transition: transform var(--motion-med) var(--ease-spring);
}
.wall-item:active { transform: scale(0.96); }
.pin {
  position: absolute;
  top: -6px;
  left: 50%;
  margin-left: -6px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #ff9d7a, #d44a3c);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
  z-index: 1;
}
.wall-item img {
  width: 100%;
  display: block;
  border-radius: 2px;
}
.wall-item figcaption {
  text-align: center;
  font-size: var(--fs-xs);
  color: #4a3320;
  margin-top: 6px;
  letter-spacing: 1px;
}
</style>
