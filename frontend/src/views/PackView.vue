<script setup lang="ts">
/**
 * 打包页 (spec §11.2): 三槽位行囊 + 背包网格
 * B1 三个槽位(口粮/伴手礼/护身符)+背包网格
 * B2 点物品入槽(属性匹配), 点槽位取下
 * B3 送它出门 → POST /api/adventure/leave → 回主页(旅行中)
 * B4 空手出门合法, 不弹警告
 * B5 旅行中: 行囊只读, 隐藏背包网格和出门按钮
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  api,
  ApiError,
  ATTR_LABELS,
  itemImageUrl,
  RARITY_LABELS,
  type InventoryItemOut,
  type LoadoutOut,
  type PetOut,
} from '../api/client'

const router = useRouter()

const pet = ref<PetOut | null>(null)
const loading = ref(true)
const error = ref('')
const busy = ref(false)

const SLOT_DEFS = [
  { key: 'food' as const, label: '口粮', hint: '路上吃掉, 补充体力' },
  { key: 'gift' as const, label: '伴手礼', hint: '送给遇到的朋友, 可能换回好东西' },
  { key: 'charm' as const, label: '护身符', hint: '带着它, 更容易遇见宝物' },
]
const loadout = ref<Record<'food' | 'gift' | 'charm', string | null>>({ food: null, gift: null, charm: null })
const awayLoadout = ref<LoadoutOut | null>(null)

onMounted(async () => {
  try {
    const p = await api.getMyPet()
    if (!p) {
      router.replace('/') // 还没宠物(蛋阶段) → 回主页
      return
    }
    pet.value = p
    if (p.away) awayLoadout.value = await api.getLoadout()
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})

/** 背包网格: 排除数量为 0 的 (后端已过滤), 按品级排序展示 */
const bagItems = computed<InventoryItemOut[]>(() => {
  const rank: Record<string, number> = { epic: 0, rare: 1, common: 2 }
  return [...(pet.value?.inventory ?? [])].sort((a, b) => rank[a.rarity] - rank[b.rarity])
})

function itemById(itemId: string | null | undefined): InventoryItemOut | undefined {
  if (!itemId) return undefined
  return (pet.value?.inventory ?? []).find((e) => e.item_id === itemId)
}

/** B2: 点背包物品 → 属性匹配则入槽/替换; 古董等无槽属性给轻提示 */
const notice = ref('')
function pick(item: InventoryItemOut) {
  const slot = item.attr as 'food' | 'gift' | 'charm'
  if (!SLOT_DEFS.some((s) => s.key === slot)) {
    notice.value = `「${item.name}」是${ATTR_LABELS[item.attr]}，放不进行囊，留在背包里收藏就好`
    return
  }
  notice.value = ''
  loadout.value[slot] = loadout.value[slot] === item.item_id ? null : item.item_id
}

/** B2: 点槽位 → 取下 */
function unpick(slot: 'food' | 'gift' | 'charm') {
  loadout.value[slot] = null
}

/** B3/B4: 送它出门 (空手也合法) */
async function leave() {
  if (busy.value) return
  busy.value = true
  try {
    const r = await api.leaveAdventure({
      food: loadout.value.food,
      gift: loadout.value.gift,
      charm: loadout.value.charm,
    })
    if (r.ok) router.replace('/')
  } catch (e) {
    notice.value = e instanceof ApiError ? e.message : '出门失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="pack">
    <div class="pack-bg"></div>
    <span class="bg-star s1"></span>
    <span class="bg-star s2"></span>

    <header class="pack-head">
      <button class="back" @click="router.push('/')">‹ 回家</button>
      <h2>打包行李</h2>
      <p class="sub">给{{ pet?.name ?? '小家伙' }}准备出门的小包袱</p>
    </header>

    <p v-if="loading" class="state-text">加载中…</p>
    <p v-else-if="error" class="state-text">{{ error }}</p>

    <template v-else-if="pet">
      <!-- B5: 旅行中 → 行囊只读 -->
      <div v-if="pet.away" class="away-box">
        <p class="away-title">🏕️ 它在旅行中</p>
        <p class="state-text">去了{{ pet.travel?.dest ?? '远方' }}，玩够了就会自己回来</p>
        <div class="slots readonly">
          <div v-for="s in SLOT_DEFS" :key="s.key" class="slot filled-or-empty">
            <template v-if="itemById(awayLoadout?.[s.key])">
              <img :src="itemImageUrl(itemById(awayLoadout?.[s.key])!.image)" class="slot-img" />
              <span class="slot-item-name">{{ itemById(awayLoadout?.[s.key])!.name }}</span>
            </template>
            <span v-else class="slot-empty">没带{{ s.label }}</span>
            <span class="slot-label">{{ s.label }}</span>
          </div>
        </div>
      </div>

      <template v-else>
        <!-- B1: 三槽位 -->
        <div class="slots">
          <button
            v-for="s in SLOT_DEFS"
            :key="s.key"
            class="slot"
            :class="{ filled: loadout[s.key] }"
            @click="unpick(s.key)"
          >
            <template v-if="itemById(loadout[s.key])">
              <img :src="itemImageUrl(itemById(loadout[s.key])!.image)" class="slot-img" />
              <span class="slot-item-name">{{ itemById(loadout[s.key])!.name }}</span>
            </template>
            <span v-else class="slot-empty">＋</span>
            <span class="slot-label">{{ s.label }}</span>
            <span class="slot-hint">{{ s.hint }}</span>
          </button>
        </div>

        <p v-if="notice" class="notice">{{ notice }}</p>

        <!-- B1: 背包网格 -->
        <p class="grid-title">背包</p>
        <div v-if="bagItems.length === 0" class="state-text">背包空空如也，先让它空着爪子出门也可以</div>
        <div v-else class="grid stagger">
          <button
            v-for="item in bagItems"
            :key="item.item_id"
            class="cell"
            :class="[`rarity-${item.rarity}`, { inSlot: Object.values(loadout).includes(item.item_id), 'epic-glow': item.rarity === 'epic' }]"
            @click="pick(item)"
          >
            <img :src="itemImageUrl(item.image)" :alt="item.name" class="cell-img" />
            <span class="cell-name">{{ item.name }}</span>
            <span class="cell-meta">{{ ATTR_LABELS[item.attr] }} ×{{ item.count }}</span>
            <span class="cell-rarity">{{ RARITY_LABELS[item.rarity] }}</span>
          </button>
        </div>

        <!-- B3/B4: 出门按钮 (空手合法); 规范 v1.1: 主动作=木牌 -->
        <button class="wood-btn pack-leave" :disabled="busy" @click="leave">
          {{ busy ? '打包中…' : '送它出门' }}
        </button>
        <p class="state-text small">什么都不带也能出门，它自己会找乐子</p>
      </template>
    </template>
  </div>
</template>

<style scoped>
.pack {
  position: relative;
  flex: 1;
  overflow-y: auto;
  padding: 22px 18px 40px;
}
.pack-bg {
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

.pack-head {
  position: relative;
  text-align: center;
  margin-bottom: 20px;
}
.pack-head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-xxl);
  font-weight: 600;
  letter-spacing: 6px;
  color: var(--color-text);
}
.sub {
  margin: 8px 0 0;
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--color-text-faint);
}
.back {
  position: absolute;
  left: 0;
  top: 4px;
  border: none;
  background: none;
  color: var(--color-text-faint);
  font-size: 14px;
  cursor: pointer;
}

.state-text {
  position: relative;
  text-align: center;
  color: var(--color-text-faint);
  font-size: 13px;
}
.state-text.small { font-size: 11px; margin-top: 8px; }

/* B1: 槽位 */
.slots {
  position: relative;
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.slot {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 14px 6px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px dashed rgba(255, 255, 255, 0.25);
  color: var(--color-text);
  cursor: pointer;
}
.slot.filled {
  border-style: solid;
  border-color: rgba(247, 201, 138, 0.5);
  background: rgba(247, 201, 138, 0.08);
}
.slots.readonly .slot { cursor: default; }
.slot-img {
  width: 44px;
  height: 44px;
  border-radius: 8px;
}
.slot-empty {
  font-size: 22px;
  color: var(--color-text-faint);
  line-height: 44px;
}
.slot-item-name { font-size: 11px; }
.slot-label {
  font-size: 12px;
  letter-spacing: 2px;
  color: var(--color-gold);
}
.slot-hint {
  font-size: 10px;
  color: var(--color-text-faint);
  text-align: center;
}

.notice {
  position: relative;
  text-align: center;
  font-size: 12px;
  color: #ffb3b3;
}

/* B1: 背包网格 */
.grid-title {
  position: relative;
  margin: 0 0 10px;
  font-size: 13px;
  letter-spacing: 3px;
  color: var(--color-text-dim);
}
.grid {
  position: relative;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 20px;
}
.cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 2px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--color-text);
  cursor: pointer;
}
.cell.rarity-rare { border-color: rgba(120, 170, 255, 0.55); }
.cell.rarity-epic { border-color: rgba(247, 201, 100, 0.65); }
.cell.inSlot { outline: 2px solid var(--color-gold); }
.cell-img {
  width: 40px;
  height: 40px;
  border-radius: 8px;
}
.cell-name { font-size: 11px; }
.cell-meta { font-size: 9px; color: var(--color-text-faint); }
.cell-rarity { font-size: 9px; color: var(--color-text-faint); }
.cell.rarity-rare .cell-rarity { color: #8ab4ff; }
.cell.rarity-epic .cell-rarity { color: #f7c964; }

.pack-leave {
  display: block;
  width: 100%;
  padding: 13px 0;
  font-size: var(--fs-xl);
}

/* B5: 旅行中 */
.away-box {
  position: relative;
  text-align: center;
}
.away-title {
  font-size: 18px;
  color: var(--color-text);
  margin: 20px 0 4px;
}
</style>
