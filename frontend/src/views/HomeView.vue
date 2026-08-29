<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  api,
  ApiError,
  itemImageUrl,
  RARITY_LABELS,
  type AdventureLogOut,
  type EggOut,
  type LoadoutOut,
  type PetOut,
} from '../api/client'
import PetSprite from '../components/PetSprite.vue'

const router = useRouter()

type Phase = 'loading' | 'egg' | 'ready' | 'pet'

const phase = ref<Phase>('loading')
const egg = ref<EggOut | null>(null)
const pet = ref<PetOut | null>(null)
const hatchName = ref('')
const busy = ref(false)
const toast = ref('')

// 归来信件 (spec §11.1 H3-H5): returned 时只出现信封, 点击才拆开
const letter = ref<AdventureLogOut | null>(null)
const letterOpen = ref(false)
const awayLoadout = ref<LoadoutOut | null>(null)

// 孵化进度驱动蛋的摇晃动画 (保留原交互: >30 开始摇晃)
const hatchProgress = computed(() => egg.value?.hatch_value ?? 0)

// 生成形象就绪 → 用 PetSprite 帧动画替换预制 SVG
const spriteReady = computed(() => pet.value?.sprite_status === 'ready')
const spritePending = computed(() => pet.value?.sprite_status === 'pending')
let spritePollTimer: ReturnType<typeof setInterval> | null = null

/** 诞生形象后台生成中: 轮询直到 ready/failed */
function pollSprite() {
  if (spritePollTimer) return
  let attempts = 0
  spritePollTimer = setInterval(async () => {
    attempts++
    try {
      const p = await api.getMyPet()
      if (p) pet.value = p
      if (p && p.sprite_status !== 'pending') {
        clearInterval(spritePollTimer!)
        spritePollTimer = null
        if (p.sprite_status === 'ready') showToast(`${p.name}的形象诞生啦！`)
      }
    } catch { /* 静默, 下轮再试 */ }
    if (attempts >= 40) {  // ~2 分钟仍未完成则放弃轮询(保持 pending 显示预制形象)
      clearInterval(spritePollTimer!)
      spritePollTimer = null
    }
  }, 3000)
}

function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => (toast.value = ''), 2600)
}

async function load() {
  try {
    const p = await api.getMyPet()
    if (p) {
      pet.value = p
      phase.value = 'pet'
      return
    }
    const e = await api.getCurrentEgg()
    egg.value = e
    // 有蛋但未答诞生问答 → 先答问(蛋"感应"主人, 影响宠物性格/物种/画风)
    if (e && !e.quiz_done) {
      router.push('/quiz')
      return
    }
    phase.value = e && e.hatch_value >= e.hatch_target ? 'ready' : 'egg'
  } catch (err) {
    phase.value = 'egg'
    showToast(err instanceof ApiError ? err.message : '加载失败, 请刷新重试')
  }
}

/** 回端检测: 推进旅行状态机 (归来→信封 / 出门→提示 / 旅行中→空房) */
async function checkReturn() {
  try {
    const r = await api.checkAdventure()
    if (r.event === 'returned' && r.log) {
      letter.value = r.log // H3: 只出现信封, 不自动弹窗
      letterOpen.value = false
    } else if (r.event === 'left') {
      showToast(`${pet.value?.name ?? '它'}出门旅行啦`)
    }
    // 旅行状态可能变化, 重新拉取宠物
    const p = await api.getMyPet()
    if (p) pet.value = p
  } catch {
    // 静默: 检测失败不影响主页
  }
}

/** H4: 拆开信封 */
function openLetter() {
  letterOpen.value = true
}

/** H5: 关闭信件 → 信封消失, 收获已入包/图鉴 */
function closeLetter() {
  letter.value = null
  letterOpen.value = false
}

/** 旅行中的行囊只读展示 (H2 补充) */
async function loadAwayLoadout() {
  try {
    awayLoadout.value = await api.getLoadout()
  } catch {
    awayLoadout.value = null
  }
}

async function care() {
  if (busy.value) return
  busy.value = true
  try {
    egg.value = await api.careEgg()
    if (egg.value.hatch_value >= egg.value.hatch_target) {
      phase.value = 'ready'
    }
  } catch (err) {
    showToast(err instanceof ApiError ? err.message : '照料失败')
  } finally {
    busy.value = false
  }
}

async function hatch() {
  if (busy.value) return
  busy.value = true
  try {
    pet.value = await api.hatchEgg(hatchName.value.trim() || undefined)
    phase.value = 'pet'
    if (pet.value.sprite_status === 'pending') pollSprite()
  } catch (err) {
    showToast(err instanceof ApiError ? err.message : '孵化失败')
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await load()
  if (phase.value === 'pet') await checkReturn()
  if (pet.value?.away) await loadAwayLoadout()
  if (spritePending.value) pollSprite()
})

/** H2: 预计回来时间 (旅行中展示) */
const backAtText = computed(() => {
  const raw = pet.value?.travel?.back_at
  if (!raw) return ''
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return ''
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

/** 行囊槽位的中文名+物品名 (旅行中只读展示用) */
const LOADOUT_SLOTS = [
  { key: 'food' as const, label: '口粮' },
  { key: 'gift' as const, label: '伴手礼' },
  { key: 'charm' as const, label: '护身符' },
]
function loadoutItemName(itemId: string | null | undefined): string {
  if (!itemId) return ''
  const entry = (pet.value?.inventory ?? []).find((e) => e.item_id === itemId)
  return entry?.name ?? ''
}

/** 按 item_id 取名称: 信件收获 → 背包 → 原样 id (消耗品可能已不在背包) */
function itemNameById(itemId: string): string {
  const fromLetter = (letter.value?.rewards?.items ?? []).find((i) => i.item_id === itemId)
  if (fromLetter) return fromLetter.name
  const fromBag = (pet.value?.inventory ?? []).find((e) => e.item_id === itemId)
  return fromBag?.name ?? itemId
}
</script>

<template>
  <div class="scene">
    <!-- ================= 插画层 ================= -->
    <svg
      class="scene-svg"
      viewBox="0 0 480 900"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <defs>
        <!-- 黄昏天空 -->
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#150c2e" />
          <stop offset="30%" stop-color="#3d2358" />
          <stop offset="55%" stop-color="#7a4478" />
          <stop offset="76%" stop-color="#c96f6e" />
          <stop offset="100%" stop-color="#eeb27f" />
        </linearGradient>
        <!-- 夕阳光晕 -->
        <radialGradient id="sun-halo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#ffe7bd" stop-opacity="0.85" />
          <stop offset="45%" stop-color="#ffce8f" stop-opacity="0.3" />
          <stop offset="100%" stop-color="#ffce8f" stop-opacity="0" />
        </radialGradient>
        <!-- 蛋光晕 -->
        <radialGradient id="egg-halo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#ffe9b8" stop-opacity="0.7" />
          <stop offset="55%" stop-color="#ffdf9e" stop-opacity="0.2" />
          <stop offset="100%" stop-color="#ffdf9e" stop-opacity="0" />
        </radialGradient>
        <!-- 蛋体 -->
        <linearGradient id="egg-body" x1="0" y1="0" x2="0.4" y2="1">
          <stop offset="0%" stop-color="#fff9ec" />
          <stop offset="100%" stop-color="#f0cda0" />
        </linearGradient>
        <filter id="blur6" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="6" />
        </filter>
        <filter id="blur2" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="2" />
        </filter>
        <!-- 纸感噪点 -->
        <filter id="noise" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
      </defs>

      <!-- 天空 -->
      <rect width="480" height="900" fill="url(#sky)" />

      <!-- 星群 -->
      <g fill="#ffffff">
        <circle class="tw" cx="48" cy="80" r="1.5" />
        <circle class="tw d1" cx="98" cy="140" r="1.2" />
        <circle class="tw d2" cx="160" cy="60" r="1.7" />
        <circle class="tw d3" cx="222" cy="110" r="1.1" />
        <circle class="tw d1" cx="300" cy="70" r="1.5" />
        <circle class="tw d2" cx="360" cy="130" r="1.2" />
        <circle class="tw" cx="420" cy="80" r="1.6" />
        <circle class="tw d3" cx="450" cy="180" r="1.1" />
        <circle class="tw d2" cx="30" cy="220" r="1.3" />
        <circle class="tw d1" cx="200" cy="170" r="1" />
        <circle class="tw d3" cx="262" cy="222" r="1.2" />
        <circle class="tw" cx="340" cy="190" r="1" />
        <circle class="tw d2" cx="402" cy="262" r="1.2" />
        <circle class="tw d1" cx="130" cy="250" r="1" />
        <circle class="tw d3" cx="70" cy="300" r="1.1" />
        <!-- 十字星芒 -->
        <path
          class="tw d2"
          d="M350,84 L351.6,89.4 L357,91 L351.6,92.6 L350,98 L348.4,92.6 L343,91 L348.4,89.4 Z"
        />
        <path
          class="tw d1"
          d="M108,196 L109.2,200.3 L113.5,201.5 L109.2,202.7 L108,207 L106.8,202.7 L102.5,201.5 L106.8,200.3 Z"
        />
      </g>

      <!-- 云（远山之前） -->
      <g fill="#ffffff" filter="url(#blur6)">
        <g class="cloud c1" opacity="0.14">
          <ellipse cx="70" cy="200" rx="52" ry="11" />
          <ellipse cx="106" cy="192" rx="34" ry="9" />
        </g>
        <g class="cloud c2" opacity="0.11">
          <ellipse cx="300" cy="262" rx="60" ry="10" />
          <ellipse cx="342" cy="254" rx="36" ry="8" />
        </g>
        <g class="cloud c3" opacity="0.16">
          <ellipse cx="190" cy="130" rx="42" ry="8" />
        </g>
      </g>

      <!-- 落日（藏于远山之后） -->
      <circle cx="130" cy="440" r="118" fill="url(#sun-halo)" />
      <circle cx="130" cy="440" r="44" fill="#ffe3b0" />
      <circle cx="130" cy="440" r="44" fill="#ffffff" opacity="0.22" filter="url(#blur2)" />

      <!-- 三层远山（空气透视） -->
      <path
        d="M0,468 C80,432 152,452 232,468 C320,486 402,442 480,460 L480,900 L0,900 Z"
        fill="#5e3a7d"
        opacity="0.42"
      />
      <path
        d="M0,506 C92,470 182,498 262,510 C352,524 424,486 480,502 L480,900 L0,900 Z"
        fill="#472a63"
        opacity="0.62"
      />
      <path
        d="M0,556 C110,522 220,552 310,562 C390,570 448,548 480,556 L480,900 L0,900 Z"
        fill="#35204e"
        opacity="0.9"
      />

      <!-- 地面 -->
      <path
        d="M0,610 C110,578 212,600 302,610 C382,618 442,600 480,608 L480,900 L0,900 Z"
        fill="#2b1743"
      />
      <path d="M0,720 C130,694 280,712 480,700 L480,900 L0,900 Z" fill="#22113a" />

      <!-- 孤独的树 -->
      <g>
        <!-- 枝干 -->
        <g stroke="#1c0e33" stroke-linecap="round" fill="none">
          <path d="M388,614 C394,562 384,528 398,478" stroke-width="13" />
          <path d="M392,532 C380,516 368,510 356,506" stroke-width="6" />
          <path d="M395,494 C405,480 416,474 428,470" stroke-width="5" />
        </g>
        <!-- 树冠 -->
        <g fill="#1c0e33">
          <circle cx="398" cy="436" r="46" />
          <circle cx="358" cy="452" r="31" />
          <circle cx="430" cy="458" r="32" />
          <circle cx="356" cy="496" r="24" />
          <circle cx="436" cy="494" r="23" />
          <circle cx="396" cy="472" r="34" />
        </g>
        <!-- 树上挂灯 -->
        <g stroke="rgba(255,233,168,0.35)" stroke-width="1">
          <line x1="428" y1="470" x2="428" y2="502" />
          <line x1="356" y1="506" x2="356" y2="532" />
        </g>
        <circle class="glow-dot" cx="428" cy="506" r="3.4" fill="#ffe9a8" filter="url(#blur2)" />
        <circle
          class="glow-dot gd2"
          cx="356"
          cy="536"
          r="2.6"
          fill="#ffe9a8"
          filter="url(#blur2)"
        />
      </g>

      <!-- 地面反光（蛋的光映在草地上） -->
      <ellipse cx="225" cy="626" rx="86" ry="12" fill="#ffdf9e" opacity="0.16" filter="url(#blur6)" />

      <!-- 蛋的光晕 -->
      <circle class="halo" cx="225" cy="576" r="94" fill="url(#egg-halo)" />

      <!-- 巢 -->
      <g fill="none" stroke-linecap="round">
        <path d="M166,618 Q225,598 284,618" stroke="#59371f" stroke-width="10" />
        <path d="M172,626 Q225,608 278,626" stroke="#6d4527" stroke-width="8" />
        <path d="M182,632 Q225,618 268,632" stroke="#472a16" stroke-width="7" />
        <path d="M188,612 L202,620 M214,606 L228,614 M246,608 L260,616" stroke="#7d5230" stroke-width="3" />
      </g>

      <!-- 魔法蛋（孵化后隐藏） -->
      <g v-if="phase !== 'pet'" class="egg" :class="{ shaking: hatchProgress > 30 }">
        <path
          d="M225,548 C237,548 247,568 247,584 C247,598 237,608 225,608 C213,608 203,598 203,584 C203,568 213,548 225,548 Z"
          fill="url(#egg-body)"
        />
        <!-- 花纹 -->
        <path
          d="M207,580 Q216,574 225,580 T243,580"
          stroke="#b48ac7"
          stroke-width="3"
          stroke-linecap="round"
          fill="none"
          opacity="0.85"
        />
        <circle cx="214" cy="590" r="2.2" fill="#b48ac7" opacity="0.85" />
        <circle cx="234" cy="592" r="2.2" fill="#b48ac7" opacity="0.85" />
        <!-- 高光 -->
        <ellipse
          cx="216"
          cy="564"
          rx="4.5"
          ry="9"
          fill="#ffffff"
          opacity="0.6"
          transform="rotate(-16 216 564)"
        />
        <!-- 孵化值满: 裂纹 -->
        <path
          v-if="phase === 'ready'"
          d="M225,552 L220,564 L228,574 L221,586 L226,598"
          stroke="#8a5a3a"
          stroke-width="2.5"
          stroke-linecap="round"
          fill="none"
        />
      </g>

      <!-- 孵化后的宠物（简约发光小生物, 漂浮在巢上; 生成形象就绪后由 PetSprite 替换） -->
      <g v-if="phase === 'pet' && !spriteReady" class="pet-creature">
        <circle cx="225" cy="576" r="58" fill="url(#egg-halo)" />
        <!-- 耳朵 -->
        <path d="M212,548 L206,528 L224,542 Z" fill="#fff3dd" />
        <path d="M238,548 L244,528 L226,542 Z" fill="#fff3dd" />
        <!-- 身体 -->
        <ellipse cx="225" cy="592" rx="27" ry="20" fill="#fff3dd" />
        <!-- 头 -->
        <circle cx="225" cy="562" r="18" fill="#fff3dd" />
        <!-- 眼睛 -->
        <circle cx="218" cy="560" r="2.2" fill="#3a2352" />
        <circle cx="232" cy="560" r="2.2" fill="#3a2352" />
        <!-- 腮红 -->
        <circle cx="212" cy="567" r="3" fill="#f2a0a8" opacity="0.55" />
        <circle cx="238" cy="567" r="3" fill="#f2a0a8" opacity="0.55" />
        <!-- 小尾巴 -->
        <circle cx="250" cy="596" r="6" fill="#fff3dd" />
      </g>

      <!-- 萤火虫 -->
      <g fill="#ffe9a8" filter="url(#blur2)">
        <circle class="ff f1" cx="118" cy="636" r="2.2" />
        <circle class="ff f2" cx="168" cy="700" r="1.8" />
        <circle class="ff f3" cx="282" cy="656" r="2.4" />
        <circle class="ff f4" cx="322" cy="716" r="1.7" />
        <circle class="ff f5" cx="88" cy="742" r="2" />
        <circle class="ff f6" cx="152" cy="588" r="1.6" />
        <circle class="ff f7" cx="296" cy="588" r="1.9" />
      </g>

      <!-- 前景草叶 -->
      <g fill="#150a29" class="grass gl">
        <path d="M6,900 C2,866 -6,846 8,820 C10,848 16,862 18,900 Z" />
        <path d="M30,900 C28,872 24,854 34,832 C38,856 42,872 44,900 Z" />
        <path d="M56,900 C54,880 52,862 62,844 C66,864 68,880 70,900 Z" />
        <path d="M82,900 C82,884 80,870 88,856 C92,872 94,886 94,900 Z" />
      </g>
      <g fill="#150a29" class="grass gr">
        <path d="M474,900 C478,868 486,850 474,824 C472,850 466,864 464,900 Z" />
        <path d="M448,900 C450,874 454,858 444,836 C440,858 436,874 434,900 Z" />
        <path d="M420,900 C422,882 424,866 414,848 C410,866 408,882 406,900 Z" />
      </g>

      <!-- 纸感噪点 -->
      <rect width="480" height="900" filter="url(#noise)" opacity="0.045" />
    </svg>

    <!-- 生成形象层: 帧动画宠物 (巢穴位置) -->
    <div v-if="phase === 'pet' && spriteReady && pet" class="sprite-layer">
      <PetSprite :pet-id="pet.id" action="idle" />
    </div>

    <!-- H3: 归来信封 —— 不自动弹窗, 点击才拆开 -->
    <button
      v-if="letter && !letterOpen"
      class="envelope"
      aria-label="拆开旅行信件"
      @click="openLetter"
    >
      <span class="envelope-icon">✉️</span>
      <span class="envelope-dot"></span>
      <span class="envelope-label">{{ pet?.name }}寄来的信</span>
    </button>

    <!-- ================= UI 层 ================= -->
    <header class="hero">
      <p class="eyebrow">PET PARADISE</p>
      <h1 class="title">宠物乐园</h1>
      <p class="subtitle">每一颗蛋里，都住着一个等待遇见你的小灵魂</p>
    </header>

    <section class="panel">
      <!-- 加载中 -->
      <p v-if="phase === 'loading'" class="hint center">加载中…</p>

      <!-- 孵化中 -->
      <template v-else-if="phase === 'egg'">
        <template v-if="egg">
          <div class="panel-row">
            <span class="panel-label">孵化值</span>
            <span class="panel-value">{{ egg.hatch_value }}<i>/{{ egg.hatch_target }}</i></span>
          </div>
          <div class="track">
            <div class="fill" :style="{ width: (egg.hatch_value / egg.hatch_target) * 100 + '%' }"></div>
          </div>
          <p class="hint">轻轻照料可以加速孵化</p>
          <button class="cta" :disabled="busy || egg.care_remaining === 0" @click="care">
            {{ egg.care_remaining > 0 ? `照料蛋宝宝（今日剩余 ${egg.care_remaining} 次）` : '今天的照料用完啦' }}
          </button>
        </template>
        <p v-else class="hint center">暂时没有正在孵化的蛋</p>
      </template>

      <!-- 可以孵化了 -->
      <template v-else-if="phase === 'ready'">
        <p class="ready-title">蛋壳裂开了，小家伙马上就要出来！</p>
        <input
          v-model="hatchName"
          class="name-input"
          placeholder="给它起个名字（留空随机）"
          maxlength="16"
        />
        <button class="cta" :disabled="busy" @click="hatch">
          {{ busy ? '孵化中…' : '见证诞生' }}
        </button>
      </template>

      <!-- 已有宠物 -->
      <template v-else-if="phase === 'pet' && pet">
        <div class="panel-row">
          <span class="pet-name">{{ pet.name }}</span>
          <span class="pet-species">{{ pet.color }}{{ pet.species }} · Lv.{{ pet.level }}</span>
        </div>
        <div class="chips">
          <span v-for="tag in pet.personality.tags" :key="tag" class="chip">{{ tag }}</span>
        </div>
        <p v-if="spritePending" class="hint">✨ {{ pet.name }}的专属形象正在成形中…</p>

        <!-- 旅行中: 空房 + 回来倒计时 + 行囊只读展示 -->
        <template v-if="pet.away">
          <div class="away-note">
            <p class="away-emoji">🏕️</p>
            <p class="away-text">「{{ pet.name }}」出门旅行啦</p>
            <p class="away-sub">
              去了{{ pet.travel?.dest ?? '远方' }}<template v-if="backAtText">，预计 {{ backAtText }} 左右回来</template>
            </p>
            <p v-if="awayLoadout" class="away-loadout">
              带着：
              <template v-for="slot in LOADOUT_SLOTS" :key="slot.key">
                <span v-if="loadoutItemName(awayLoadout[slot.key])" class="away-loadout-item">
                  {{ slot.label }}·{{ loadoutItemName(awayLoadout[slot.key]) }}
                </span>
              </template>
              <span v-if="!awayLoadout.food && !awayLoadout.gift && !awayLoadout.charm">什么也没带</span>
            </p>
          </div>
        </template>
        <template v-else>
          <!-- v1.3: 聊聊入口撤下(ADR-003); 操作坞保持紧凑不挡宠物 (spec §11.1 布局红线) -->
          <p class="hint small">
            天赋：{{ pet.talents.map((t) => t.name).join('、') }} ｜ 技能：{{ pet.skills.map((s) => s.name).join('、') }}
          </p>
          <div class="action-row">
            <router-link to="/pack" class="action-btn">打包行李</router-link>
            <router-link to="/collection" class="action-btn">收藏</router-link>
          </div>
        </template>
      </template>
    </section>

    <!-- H4/H5: 拆开的信件 —— 日记 + 收获(品级光效/NEW!) + 行囊结算留痕 -->
    <div v-if="letter && letterOpen" class="mask" @click.self="closeLetter">
      <div class="letter-card">
        <p class="letter-title">✉️ {{ pet?.name }}的信 · {{ letter.dest || '远方' }}</p>
        <p class="letter-text">{{ letter.narrative }}</p>
        <div v-if="letter.rewards?.items?.length" class="letter-items stagger">
          <div
            v-for="(it, idx) in letter.rewards.items"
            :key="idx"
            class="letter-item"
            :class="[`rarity-${it.rarity}`, { 'epic-glow': it.rarity === 'epic' }]"
          >
            <img :src="itemImageUrl(it.image)" :alt="it.name" class="letter-item-img" />
            <span class="letter-item-name">{{ it.name }}</span>
            <span class="letter-item-rarity">{{ RARITY_LABELS[it.rarity] }}</span>
            <span v-if="it.is_new" class="new-badge badge-pulse">NEW!</span>
          </div>
        </div>
        <p v-if="letter.rewards?.exp" class="letter-exp">经验 +{{ letter.rewards.exp }}</p>
        <div class="letter-notes">
          <p v-if="letter.rewards?.exchanged" class="letter-note">
            用「{{ itemNameById(letter.rewards.exchanged.gave) }}」换到了「{{ itemNameById(letter.rewards.exchanged.got) }}」
          </p>
          <p v-else-if="letter.rewards?.gift_returned" class="letter-note">把伴手礼又抱回来了（有点害羞）</p>
          <p v-for="cid in letter.rewards?.consumed ?? []" :key="cid" class="letter-note">
            路上吃掉了「{{ itemNameById(cid) }}」
          </p>
        </div>
        <button class="cta" @click="closeLetter">收好啦</button>
      </div>
    </div>

    <!-- 轻提示 -->
    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<style scoped>
.scene {
  position: relative;
  flex: 1;
  overflow: hidden;
}
.scene-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

/* 生成形象层: 覆盖在巢穴位置 (v1.3 布局红线: 上移+略缩, 完整露出不被操作坞遮挡) */
.sprite-layer {
  position: absolute;
  left: 47%;
  top: 33%;
  width: 40%;
  aspect-ratio: 1;
  transform: translateX(-50%);
  pointer-events: none;
}

/* ---------- SVG 动画 ---------- */
.tw {
  animation: twinkle 3.2s ease-in-out infinite;
}
.d1 { animation-delay: 0.7s; }
.d2 { animation-delay: 1.4s; }
.d3 { animation-delay: 2.1s; }
@keyframes twinkle {
  0%, 100% { opacity: 0.25; }
  50% { opacity: 0.95; }
}

.cloud {
  animation: cloud-drift 64s linear infinite;
}
.c2 { animation-duration: 82s; animation-delay: -30s; }
.c3 { animation-duration: 96s; animation-delay: -60s; }
@keyframes cloud-drift {
  from { transform: translateX(-140px); }
  to { transform: translateX(560px); }
}

.halo {
  animation: halo-breathe 3.6s ease-in-out infinite;
  transform-box: fill-box;
  transform-origin: center;
}
@keyframes halo-breathe {
  0%, 100% { opacity: 0.75; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.08); }
}

.egg {
  transform-box: fill-box;
  transform-origin: bottom center;
}
.egg.shaking {
  animation: egg-sway 2.8s ease-in-out infinite;
}
@keyframes egg-sway {
  0%, 100% { transform: rotate(-2.4deg); }
  50% { transform: rotate(2.4deg); }
}

.pet-creature {
  animation: pet-float 3.2s ease-in-out infinite;
  transform-box: fill-box;
  filter: drop-shadow(0 6px 18px rgba(255, 233, 184, 0.35));
}
@keyframes pet-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

.ff {
  animation: firefly 7s ease-in-out infinite;
  transform-box: fill-box;
}
.f2 { animation-delay: -1.2s; animation-duration: 8s; }
.f3 { animation-delay: -2.4s; animation-duration: 6.4s; }
.f4 { animation-delay: -3.1s; animation-duration: 9s; }
.f5 { animation-delay: -4.4s; animation-duration: 7.6s; }
.f6 { animation-delay: -5.2s; animation-duration: 8.4s; }
.f7 { animation-delay: -6s; animation-duration: 6.8s; }
@keyframes firefly {
  0%, 100% { opacity: 0.12; transform: translate(0, 0); }
  30% { opacity: 0.95; }
  55% { opacity: 0.3; transform: translate(12px, -16px); }
  80% { opacity: 0.85; transform: translate(4px, -26px); }
}

.glow-dot {
  animation: lamp 3s ease-in-out infinite;
}
.gd2 { animation-delay: 1.5s; }
@keyframes lamp {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.grass {
  transform-box: fill-box;
  transform-origin: bottom center;
  animation: grass-sway 5s ease-in-out infinite;
}
.gr { animation-delay: 2.5s; }
@keyframes grass-sway {
  0%, 100% { transform: rotate(-1.4deg); }
  50% { transform: rotate(1.4deg); }
}

/* ---------- 标题 ---------- */
/* hero 瘦身 (规范 §0: 空间让给宠物); 标题用得意黑 */
.hero {
  position: relative;
  z-index: 2;
  text-align: center;
  margin-top: 34px;
  pointer-events: none;
}
.eyebrow {
  margin: 0 0 6px;
  font-size: var(--fs-xs);
  letter-spacing: 5px;
  color: rgba(255, 233, 200, 0.55);
}
.title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 600;
  letter-spacing: 8px;
  text-indent: 8px; /* 视觉居中补偿字间距 */
  color: var(--color-text);
  text-shadow: 0 2px 24px rgba(255, 200, 140, 0.35), 0 1px 2px rgba(40, 16, 60, 0.6);
}
.subtitle {
  margin: 8px 0 0;
  font-size: var(--fs-xs);
  letter-spacing: 1px;
  color: var(--color-text-faint);
}

/* ---------- 底部操作坞 (v1.3: 紧凑半透明, 不遮挡宠物) ---------- */
.panel {
  position: absolute;
  z-index: 2;
  left: 16px;
  right: 16px;
  bottom: 14px;
  padding: 12px 16px 14px;
  border-radius: 20px;
  background: rgba(22, 12, 44, 0.42);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid rgba(255, 255, 255, 0.09);
  box-shadow: 0 12px 40px rgba(10, 4, 26, 0.45);
}
.panel-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.panel-label {
  font-size: 13px;
  letter-spacing: 2px;
  color: rgba(255, 240, 220, 0.65);
}
.panel-value {
  font-size: 24px;
  font-weight: 700;
  color: #f7c98a;
  font-variant-numeric: tabular-nums;
}
.panel-value i {
  font-style: normal;
  font-size: 13px;
  font-weight: 400;
  color: rgba(255, 240, 220, 0.45);
  margin-left: 2px;
}
.track {
  margin-top: 12px;
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #f2b06e, #ec8fa8);
  box-shadow: 0 0 10px rgba(242, 176, 110, 0.55);
  transition: width 0.5s ease;
}
.hint {
  margin: 10px 0 0;
  font-size: 12px;
  color: rgba(255, 240, 220, 0.45);
  letter-spacing: 1px;
}
.hint.small {
  margin-top: 6px;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hint.center {
  text-align: center;
  margin: 6px 0;
}
.cta {
  display: block;
  width: 100%;
  margin-top: 16px;
  padding: 13px 0;
  text-align: center;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, #f2a56e, #e77fa2);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 2px;
  text-decoration: none;
  font-family: inherit;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(231, 127, 162, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.35);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.cta:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 28px rgba(231, 127, 162, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.35);
}
.cta:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 孵化就绪 */
.ready-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 1px;
  color: #f7c98a;
  text-align: center;
}
.name-input {
  width: 100%;
  padding: 11px 14px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 12px;
  outline: none;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-text);
  font-family: inherit;
}
.name-input::placeholder {
  color: rgba(253, 240, 220, 0.35);
}
.name-input:focus {
  border-color: rgba(242, 165, 110, 0.55);
}

/* 宠物卡片 */
.pet-name {
  font-family: var(--font-display);
  font-size: var(--fs-xxl);
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--color-text);
}
.pet-species {
  font-size: 12px;
  color: rgba(255, 240, 220, 0.55);
}
.chips {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.chip {
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  letter-spacing: 1px;
  color: #f7c98a;
  background: rgba(247, 201, 138, 0.12);
  border: 1px solid rgba(247, 201, 138, 0.28);
}

/* 轻提示 */
.toast {
  position: absolute;
  z-index: 3;
  left: 50%;
  bottom: 210px;
  transform: translateX(-50%);
  padding: 10px 18px;
  border-radius: 999px;
  background: rgba(22, 12, 44, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: #fdf6ec;
  font-size: 13px;
  letter-spacing: 1px;
  white-space: nowrap;
}

/* 操作按钮组 */
.action-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-top: 10px;
}
/* 旅行中提示 (规范 §3: 操作坞占屏 ≤15%, away-note 必须紧凑) */
.away-note {
  margin: 8px 0 2px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.06);
  text-align: center;
}
.away-emoji { font-size: 22px; margin: 0; }
.away-text { margin: 2px 0 2px; font-size: var(--fs-lg); color: var(--color-text); }
.away-sub { margin: 0; font-size: var(--fs-xs); color: var(--color-text-faint); }
.action-btn {
  padding: 9px 0;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.07);
  color: rgba(253, 240, 220, 0.85);
  font-size: 13px;
  letter-spacing: 1px;
  text-align: center;
  text-decoration: none;
  cursor: pointer;
  transition: background 0.2s, transform 0.15s;
  font-family: inherit;
}
.action-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.13);
  transform: translateY(-1px);
}
.action-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* ===== 归来信封 (H3): 位于宠物旁侧, 不遮挡宠物 (spec §11.1 布局红线) ===== */
.envelope {
  position: absolute;
  right: 6%;
  top: 34%;
  z-index: 12;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 18px;
  border: none;
  border-radius: 18px;
  background: rgba(255, 248, 230, 0.14);
  backdrop-filter: blur(6px);
  cursor: pointer;
  animation: envelope-bob 1.6s ease-in-out infinite;
}
.envelope-icon {
  font-size: 30px;
  filter: drop-shadow(0 0 10px rgba(255, 220, 160, 0.8));
}
.envelope-dot {
  position: absolute;
  top: 6px;
  right: 10px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #ff7a7a;
  box-shadow: 0 0 8px rgba(255, 122, 122, 0.9);
}
.envelope-label {
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--color-text);
}
@keyframes envelope-bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

/* ===== 拆开的信件 (H4): 底部信纸抽屉, 上方宠物保持可见 (spec §11.1 布局红线) ===== */
.mask {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: rgba(10, 5, 26, 0.45);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.letter-card {
  width: 100%;
  max-width: 480px;
  max-height: 62vh;
  overflow-y: auto;
  padding: 22px 22px 26px;
  border-radius: 24px 24px 0 0;
  background: linear-gradient(180deg, rgba(42, 24, 74, 0.97), rgba(26, 15, 56, 0.97));
  border: 1px solid rgba(247, 201, 138, 0.25);
  border-bottom: none;
  box-shadow: 0 -12px 50px rgba(0, 0, 0, 0.5), 0 0 40px rgba(247, 201, 138, 0.08);
  animation: sheet-in 0.35s ease;
}
@keyframes sheet-in {
  from { transform: translateY(60px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
.letter-title {
  margin: 0 0 12px;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--color-gold);
  text-align: center;
}
.letter-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: var(--color-text);
}
.letter-items {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}
.letter-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  width: 72px;
  padding: 8px 4px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
}
.letter-item.rarity-rare {
  border-color: rgba(120, 170, 255, 0.6);
  box-shadow: 0 0 12px rgba(120, 170, 255, 0.3);
}
.letter-item.rarity-epic {
  border-color: rgba(247, 201, 100, 0.7);
  box-shadow: 0 0 14px rgba(247, 201, 100, 0.35);
}
.letter-item-img {
  width: 44px;
  height: 44px;
  border-radius: 8px;
}
.letter-item-name {
  font-size: 11px;
  color: var(--color-text);
  text-align: center;
}
.letter-item-rarity {
  font-size: 10px;
  color: var(--color-text-faint);
}
.letter-item.rarity-rare .letter-item-rarity { color: #8ab4ff; }
.letter-item.rarity-epic .letter-item-rarity { color: #f7c964; }
.new-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 9px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #ff8a5c, #ff5c8a);
  box-shadow: 0 2px 8px rgba(255, 92, 138, 0.5);
}
.letter-exp {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--color-gold);
}
.letter-notes {
  margin-top: 8px;
}
.letter-note {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-text-faint);
}
.letter-card .cta {
  margin-top: 18px;
}

/* 旅行中行囊只读展示 */
.away-loadout {
  margin: 4px 0 0;
  font-size: var(--fs-xs);
  color: var(--color-text-faint);
}
.away-loadout-item {
  margin: 0 4px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.14);
}
</style>
