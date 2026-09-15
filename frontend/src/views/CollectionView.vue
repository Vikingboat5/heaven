<script setup lang="ts">
/**
 * 收藏页 (spec §11.3): 仅图鉴 (日记已拆分为独立页, 2026-09-06)
 * C1 图鉴: 按种子包分组格子矩阵, 未获得=剪影, 每组进度 n/N
 * C3 物品详情: 大图/品级/属性/描述/来源/数量/首发现; 打开即清 NEW!
 * C4 NEW! 角标, 点开详情后消除
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  api,
  ApiError,
  ATTR_LABELS,
  itemImageUrl,
  PACK_LABELS,
  RARITY_LABELS,
  type CatalogItemOut,
} from '../api/client'

const router = useRouter()
const myUsername = localStorage.getItem('pp_username') ?? ''

const loading = ref(true)
const error = ref('')

/** 分类筛选 (2026-09-12 拍板): 全部/已解锁/待解锁 */
type Filter = 'all' | 'unlocked' | 'locked'
const filter = ref<Filter>('all')
const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'unlocked', label: '已解锁' },
  { key: 'locked', label: '待解锁' },
]
/** 品级排序: 普通 > 稀有 > 传说 (拍板) */
const RARITY_ORDER: Record<string, number> = { common: 0, rare: 1, epic: 2 }

const items = ref<CatalogItemOut[]>([])
const detail = ref<CatalogItemOut | null>(null)

onMounted(async () => {
  try {
    const c = await api.getCatalog()
    items.value = c.items
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})

/** C1: 按 pack 分组 (保持目录顺序) + 分类筛选 + 组内按 普通>稀有>传说 排序 */
const packs = computed(() => {
  const groups: { pack: string; label: string; items: CatalogItemOut[] }[] = []
  const match = (it: CatalogItemOut) =>
    filter.value === 'all' || (filter.value === 'unlocked' ? it.obtained : !it.obtained)
  for (const it of items.value) {
    if (!match(it)) continue
    let g = groups.find((x) => x.pack === it.pack)
    if (!g) {
      g = { pack: it.pack, label: PACK_LABELS[it.pack] ?? it.pack, items: [] }
      groups.push(g)
    }
    g.items.push(it)
  }
  for (const g of groups) {
    g.items.sort((a, b) => (RARITY_ORDER[a.rarity] ?? 0) - (RARITY_ORDER[b.rarity] ?? 0))
  }
  return groups
})

function packProgress(g: { items: CatalogItemOut[] }): string {
  const n = g.items.filter((i) => i.obtained).length
  return `${n}/${g.items.length}`
}

/** C3: 打开详情 → C4: 清 NEW! 角标 */
async function openDetail(it: CatalogItemOut) {
  if (!it.obtained) return // 未获得: 剪影不可点
  detail.value = it
  if (it.is_new) {
    it.is_new = false // 本地即时反馈
    try {
      await api.markItemsSeen([it.item_id])
    } catch {
      // 清角标失败不打断浏览, 下次进入还会是 NEW
    }
  }
}

/** 详情弹层的获得时间格式化 */
function fmtTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${mi}`
}
</script>

<template>
  <div class="col">
    <div class="col-bg"></div>
    <span class="bg-star s1"></span>
    <span class="bg-star s2"></span>

    <header class="col-head">
      <button class="back" @click="router.push('/')">‹ 回家</button>
      <h2>背包</h2>
    </header>

    <!-- 分类筛选: 全部/已解锁/待解锁 -->
    <div class="filter-row">
      <button
        v-for="f in FILTERS"
        :key="f.key"
        class="filter-chip"
        :class="{ active: filter === f.key }"
        @click="filter = f.key"
      >{{ f.label }}</button>
    </div>

    <p v-if="loading" class="state-text">加载中…</p>
    <p v-else-if="error" class="state-text">{{ error }}</p>

    <!-- ===== 图鉴 (C1/C3/C4) ===== -->
    <template v-else>
      <p v-if="packs.length === 0" class="state-text">这个分类下还没有物品</p>
      <section v-for="g in packs" :key="g.pack" class="pack-group">
        <p class="pack-title">{{ g.label }} <span class="pack-progress">{{ packProgress(g) }}</span></p>
        <div class="grid stagger">
          <button
            v-for="it in g.items"
            :key="it.item_id"
            class="cell"
            :class="[`rarity-${it.rarity}`, { silhouette: !it.obtained, 'epic-glow': it.obtained && it.rarity === 'epic' }]"
            @click="openDetail(it)"
          >
            <span class="rarity-tag" :class="`tag-${it.rarity}`">{{ RARITY_LABELS[it.rarity] }}</span>
            <img :src="itemImageUrl(it.image)" :alt="it.obtained ? it.name : '???'" class="cell-img" />
            <span class="cell-name">{{ it.obtained ? it.name : '???' }}</span>
            <span v-if="it.obtained && it.is_new" class="new-badge badge-pulse">NEW!</span>
          </button>
        </div>
      </section>
    </template>

    <!-- C3: 物品详情弹层 -->
    <div v-if="detail" class="mask" @click.self="detail = null">
      <div class="detail-card">
        <img :src="itemImageUrl(detail.image)" :alt="detail.name" class="detail-img"
             :class="[`rarity-${detail.rarity}`, { 'epic-glow': detail.rarity === 'epic' }]" />
        <p class="detail-name">{{ detail.name }}</p>
        <p class="detail-meta">
          <span :class="`rarity-text-${detail.rarity}`">{{ RARITY_LABELS[detail.rarity] }}</span>
          · {{ ATTR_LABELS[detail.attr] }} · ×{{ detail.count }}
        </p>
        <p class="detail-desc">{{ detail.desc }}</p>
        <p class="detail-source">来自：{{ detail.seed_name || '未知之地' }}</p>
        <p v-if="detail.first_discovery" class="detail-first">
          ✨ 由
          {{ detail.first_discovery.by_username === myUsername ? '你的宠物' : `${detail.first_discovery.by_username} 的宠物` }}
          首次发现<template v-if="detail.first_discovery.at">（{{ fmtTime(detail.first_discovery.at) }}）</template>
        </p>
        <button class="cta" @click="detail = null">收好啦</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.col {
  position: relative;
  flex: 1;
  overflow-y: auto;
  padding: 22px 18px 40px;
}
.col-bg {
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

.col-head {
  position: relative;
  text-align: center;
  margin-bottom: 14px;
}
.col-head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-xxl);
  font-weight: 600;
  letter-spacing: 6px;
  color: var(--color-text);
}
.back {
  position: absolute;
  left: 0;
  top: 4px;
  border: none;
  background: none;
  color: var(--color-text-faint);
  font-size: var(--fs-lg);
  cursor: pointer;
}

.tabs {
  position: relative;
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 18px;
}
.tab {
  padding: 8px 22px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: var(--color-text-faint);
  font-size: var(--fs-lg);
  letter-spacing: 3px;
  cursor: pointer;
}
.tab.active {
  color: #3a1f10;
  background: linear-gradient(135deg, #ffd9a0, #f2b06e);
  border-color: transparent;
}

.state-text { position: relative; text-align: center; color: var(--color-text-faint); font-size: var(--fs-md); }
.state-empty { position: relative; text-align: center; margin-top: 60px; }
.state-title { font-size: var(--fs-xl); color: var(--color-text-dim); margin: 0 0 8px; }

/* C1: 图鉴分组 */
.pack-group { position: relative; margin-bottom: 22px; }
.pack-title {
  margin: 0 0 10px;
  font-size: var(--fs-lg);
  letter-spacing: 3px;
  color: var(--color-text);
}
.pack-progress { font-size: var(--fs-xs); color: var(--color-text-faint); margin-left: 8px; }
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.cell {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 16px 2px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--color-text);
  cursor: pointer;
}
/* 品级强化 (2026-09-12 拍板: 不只边框, 底色+品级标签) */
.cell.rarity-rare {
  border-color: rgba(120, 170, 255, 0.75);
  background: rgba(120, 170, 255, 0.10);
}
.cell.rarity-epic {
  border-color: rgba(247, 201, 100, 0.85);
  background: rgba(247, 201, 100, 0.12);
}
.rarity-tag {
  position: absolute;
  top: 4px;
  left: 5px;
  padding: 1px 6px;
  border-radius: 999px;
  font-size: var(--fs-micro);
  letter-spacing: 1px;
  line-height: 1.5;
}
.tag-common { color: rgba(253, 240, 220, 0.55); background: rgba(255, 255, 255, 0.07); }
.tag-rare { color: #9cc2ff; background: rgba(120, 170, 255, 0.18); }
.tag-epic { color: #ffd98a; background: rgba(247, 201, 100, 0.2); }
.cell.silhouette { cursor: default; opacity: 0.75; }
.cell.silhouette .rarity-tag { opacity: 0.5; }
.cell.silhouette .cell-img {
  filter: grayscale(1) brightness(0.35);
}
.cell-img { width: 44px; height: 44px; border-radius: 8px; }
.cell-name { font-size: var(--fs-xs); }

/* 分类筛选 chips */
.filter-row {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.filter-chip {
  padding: 5px 16px;
  border-radius: 999px;
  border: 1px solid var(--color-glass-border);
  background: var(--color-glass);
  color: var(--color-text-dim);
  font-size: var(--fs-md);
  letter-spacing: 1px;
  cursor: pointer;
}
.filter-chip.active {
  background: rgba(247, 201, 138, 0.18);
  border-color: rgba(247, 201, 138, 0.5);
  color: var(--color-gold);
  font-weight: 600;
}
.new-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  padding: 1px 6px;
  border-radius: 999px;
  font-size: var(--fs-micro);
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #ff8a5c, #ff5c8a);
  box-shadow: 0 2px 8px rgba(255, 92, 138, 0.5);
}

/* C2: 日记时间线 */
.timeline { position: relative; padding-left: 18px; }
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
  cursor: pointer;
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
  font-size: var(--fs-xs);
  letter-spacing: 1px;
  color: var(--color-text-faint);
}
.log-narrative { margin: 0; font-size: var(--fs-lg); line-height: 1.75; color: var(--color-text); }
.log-rewards { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; align-items: center; }
.reward-chip {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: var(--fs-xs);
  color: #f7c98a;
  background: rgba(247, 201, 138, 0.12);
  border: 1px solid rgba(247, 201, 138, 0.25);
}
.reward-thumb {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
}
.reward-thumb.rarity-rare { border-color: rgba(120, 170, 255, 0.6); }
.reward-thumb.rarity-epic { border-color: rgba(247, 201, 100, 0.7); }
.log-detail { margin-top: 10px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 8px; }
.log-event { margin: 4px 0; font-size: var(--fs-sm); color: var(--color-text-dim); line-height: 1.6; }
.log-event-time { color: var(--color-text-faint); font-variant-numeric: tabular-nums; }
.log-exchange { margin: 8px 0 0; font-size: var(--fs-sm); color: #f7c98a; }

/* C3: 详情弹层 */
.mask {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: rgba(10, 5, 26, 0.65);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.detail-card {
  width: 100%;
  max-width: 340px;
  padding: 24px 22px;
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(42, 24, 74, 0.96), rgba(26, 15, 56, 0.96));
  border: 1px solid rgba(247, 201, 138, 0.25);
  text-align: center;
}
.detail-img {
  width: 120px;
  height: 120px;
  border-radius: 20px;
  border: 2px solid rgba(255, 255, 255, 0.15);
}
.detail-img.rarity-rare { border-color: rgba(120, 170, 255, 0.7); box-shadow: 0 0 20px rgba(120, 170, 255, 0.35); }
.detail-img.rarity-epic { border-color: rgba(247, 201, 100, 0.8); box-shadow: 0 0 24px rgba(247, 201, 100, 0.4); }
.detail-name { margin: 14px 0 4px; font-size: var(--fs-xl); font-weight: 700; letter-spacing: 2px; color: var(--color-text); }
.detail-meta { margin: 0 0 10px; font-size: var(--fs-sm); color: var(--color-text-faint); }
.rarity-text-rare { color: #8ab4ff; }
.rarity-text-epic { color: #f7c964; }
.detail-desc { margin: 0 0 10px; font-size: var(--fs-md); line-height: 1.7; color: var(--color-text); }
.detail-source { margin: 0 0 6px; font-size: var(--fs-xs); color: var(--color-text-faint); }
.detail-first { margin: 0 0 6px; font-size: var(--fs-sm); color: #f7c98a; }
.cta {
  width: 100%;
  margin-top: 14px;
  padding: 12px;
  border: none;
  border-radius: 999px;
  font-size: var(--fs-lg);
  letter-spacing: 4px;
  color: #3a1f10;
  background: linear-gradient(135deg, #ffd9a0, #f2b06e);
  cursor: pointer;
}
</style>
