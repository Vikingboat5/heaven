<script setup lang="ts">
/**
 * 明信片墙 (规范 v1.3.1): 夜空下挂在麻绳上的照片
 * 夜晚渐变 + 星星 + 两根微垂麻绳 + 小木夹 + 照片轻摇 + 暖光晕
 * (替代软木板方案——与整体梦幻夜景调性统一)
 */
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api, ApiError, type AdventureLogOut } from '../api/client'

const router = useRouter()
const logs = ref<AdventureLogOut[]>([])
const loading = ref(true)
const error = ref('')

const postcards = computed(() => logs.value.filter((l) => l.rewards?.postcard))

/** 分成挂绳排 (每排 3 张, 2026-09-12 拍板) */
const PER_ROW = 3
const rows = computed(() => {
  const out: AdventureLogOut[][] = []
  for (let i = 0; i < postcards.value.length; i += PER_ROW) {
    out.push(postcards.value.slice(i, i + PER_ROW))
  }
  return out
})

/** 点照片看详情 (大图+目的地+日期+当趟的信) */
const selected = ref<AdventureLogOut | null>(null)

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
    <!-- 夜空点缀 -->
    <span v-for="n in 8" :key="n" class="twinkle" :style="{ left: `${(n * 41) % 90 + 5}%`, top: `${(n * 23) % 55 + 4}%`, animationDelay: `${(n % 3) * 0.9}s` }"></span>

    <header class="wall-head">
      <button class="back" @click="router.push('/')">‹ 回家</button>
      <h2>明信片墙</h2>
    </header>
    <p class="wall-sub">它去过的每个地方，都挂了一张照片</p>

    <p v-if="loading" class="state-text">加载中…</p>
    <p v-else-if="error" class="state-text">{{ error }}</p>
    <div v-else-if="postcards.length === 0" class="state-empty">
      <p class="state-title">绳上还空空的</p>
      <p class="state-text">它第一次去一个新地方时，就会挂上一张</p>
    </div>

    <template v-else>
      <!-- 挂绳排: 每排 3 张 -->
      <div v-for="(row, ri) in rows" :key="ri" class="string-row">
        <svg class="string-line" viewBox="0 0 480 30" preserveAspectRatio="none">
          <path d="M0,6 Q240,30 480,6" stroke="rgba(230,210,180,0.5)" stroke-width="1.6" fill="none" />
        </svg>
        <div class="photos stagger">
          <figure
            v-for="(p, i) in row"
            :key="p.id"
            class="photo"
            :style="{ rotate: `${((i * 53) % 5) - 2.4}deg`, animationDelay: `${(i % 3) * 1.1}s` }"
            @click="selected = p"
          >
            <span class="clip"></span>
            <img :src="p.rewards!.postcard!" :alt="`来自${p.dest}的明信片`" />
            <figcaption>{{ p.dest || '远方' }} · {{ fmtDay(p.ended_at) }}</figcaption>
          </figure>
        </div>
      </div>
    </template>

    <!-- 明信片详情 (底部抽屉: 大图+目的地+日期+当趟的信) -->
    <div v-if="selected" class="mask" @click.self="selected = null">
      <div class="detail-card">
        <p class="detail-title">📮 来自{{ selected.dest || '远方' }}的明信片</p>
        <p class="detail-date">{{ fmtDay(selected.ended_at) }}</p>
        <img class="detail-img" :src="selected.rewards!.postcard!" :alt="`来自${selected.dest}的明信片`" />
        <p class="detail-text">{{ selected.narrative }}</p>
        <button class="wood-btn detail-close" @click="selected = null">收好啦</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wall-page {
  position: relative;
  flex: 1;
  padding: 18px 20px 40px;
  overflow: hidden;
  /* 梦幻底图 (scripts/gen_wall_bg.py 生成, 与主页同画风) */
  background:
    linear-gradient(rgba(21, 12, 46, 0.18), rgba(21, 12, 46, 0.30)),
    url('/static/scenes/wall_dream/bg.jpg') center / cover no-repeat,
    linear-gradient(180deg, #150c2e 0%, #2a1850 55%, #3d2358 100%);
}
/* 星星 */
.twinkle {
  position: absolute;
  width: 2.5px;
  height: 2.5px;
  border-radius: 50%;
  background: #fff;
  animation: tw 3.2s ease-in-out infinite;
  pointer-events: none;
}
@keyframes tw {
  0%, 100% { opacity: 0.2; }
  50% { opacity: 0.85; }
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
  text-shadow: 0 1px 8px rgba(255, 200, 140, 0.25);
}
.wall-sub {
  margin: 4px 0 10px;
  font-size: var(--fs-xs);
  color: var(--color-text-faint);
  letter-spacing: 1px;
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

/* 挂绳排 */
.string-row {
  position: relative;
  margin-top: 6px;
}
.string-line {
  display: block;
  width: 100%;
  height: 30px;
}
.photos {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 14px;
  justify-content: center;
  margin-top: -26px;      /* 照片顶部贴着绳子的弧度 */
  padding-bottom: 12px;
}

/* 挂着的照片: 木夹 + 拍立得 + 暖光晕 + 轻摇 */
.photo {
  position: relative;
  width: 31%;              /* 每排 3 张 (2026-09-12 拍板) */
  margin: 0;
  background: #fbf6ea;
  padding: 6px 6px 8px;
  border-radius: 4px;
  box-shadow:
    0 6px 16px rgba(10, 6, 20, 0.5),
    0 0 26px rgba(255, 214, 150, 0.18);   /* 梦幻暖光晕 */
  animation: photo-sway 4.6s ease-in-out infinite;
  transform-origin: top center;
  cursor: pointer;
  transition: transform var(--motion-med) var(--ease-spring);
}
@keyframes photo-sway {
  0%, 100% { transform: rotate(-1.4deg); }
  50% { transform: rotate(1.4deg); }
}
.clip {
  position: absolute;
  top: -8px;
  left: 50%;
  margin-left: -7px;
  width: 14px;
  height: 18px;
  border-radius: 3px;
  background: linear-gradient(160deg, #b8894f, #7d5530);
  box-shadow: 0 2px 4px rgba(10, 6, 20, 0.5);
}
.photo img {
  width: 100%;
  display: block;
  border-radius: 2px;
}
.photo figcaption {
  text-align: center;
  font-size: var(--fs-xs);
  color: #4a3320;
  margin-top: 6px;
  letter-spacing: 1px;
}

/* 详情抽屉 (底部信纸式) */
.mask {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: rgba(10, 5, 26, 0.5);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.detail-card {
  width: 100%;
  max-width: 480px;
  max-height: 80vh;
  overflow-y: auto;
  padding: 20px 22px 24px;
  border-radius: 24px 24px 0 0;
  background: linear-gradient(180deg, #f9efdb, #f0e0c2);
  border: 1px solid var(--color-paper-edge);
  border-bottom: none;
  box-shadow: 0 -12px 50px rgba(0, 0, 0, 0.5);
  color: var(--color-paper-text);
  animation: sheet-in var(--motion-slow) var(--ease-out);
}
@keyframes sheet-in {
  from { transform: translateY(60px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
.detail-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 700;
  letter-spacing: 2px;
  color: #7a4a1e;
  text-align: center;
}
.detail-date {
  text-align: center;
  margin: 4px 0 12px;
  font-size: var(--fs-xs);
  color: #a08a6a;
  letter-spacing: 1px;
}
.detail-img {
  display: block;
  width: 88%;
  margin: 0 auto 14px;
  border: 4px solid #fff;
  border-radius: 6px;
  box-shadow: 0 6px 18px rgba(60, 40, 20, 0.3);
  rotate: -0.8deg;
}
.detail-text {
  margin: 0;
  font-size: var(--fs-lg);
  line-height: 1.8;
  color: var(--color-paper-text);
  white-space: pre-line;
}
.detail-close {
  display: block;
  width: 100%;
  margin-top: 18px;
  padding: 12px 0;
}
</style>
