<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
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
  scheduleAmbient()
})

/* ---- H6: 生活动作随机编排 (待机为主, 每 18-40s 随机做一个生活动作) ---- */
const AMBIENT_ACTIONS = ['stretch', 'groom', 'doze']
const spriteRef = ref<InstanceType<typeof PetSprite> | null>(null)
let ambientTimer: ReturnType<typeof setTimeout> | null = null

function scheduleAmbient() {
  if (ambientTimer) clearTimeout(ambientTimer)
  const delay = 18000 + Math.random() * 22000
  ambientTimer = setTimeout(() => {
    // 仅在家、形象就绪、页面可见时播放; 动作以 manifest 实际可用为准 (QC 失败的动作会被管线跳过)
    if (pet.value && !pet.value.away && spriteReady.value && !document.hidden) {
      const available = AMBIENT_ACTIONS.filter((a) => spriteRef.value?.availableActions().includes(a))
      if (available.length > 0) {
        spriteRef.value?.playOnce(available[Math.floor(Math.random() * available.length)])
      }
    }
    scheduleAmbient()
  }, delay)
}

onBeforeUnmount(() => {
  if (ambientTimer) clearTimeout(ambientTimer)
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
        <!-- 黄昏天空 (8 档消色带, 规范方向四) -->
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#0d0722" />
          <stop offset="18%" stop-color="#1a0f38" />
          <stop offset="36%" stop-color="#3d2358" />
          <stop offset="52%" stop-color="#5c3270" />
          <stop offset="66%" stop-color="#8a4f7e" />
          <stop offset="80%" stop-color="#c96f6e" />
          <stop offset="92%" stop-color="#e89a6e" />
          <stop offset="100%" stop-color="#f3c489" />
        </linearGradient>
        <!-- 地平线暖雾光带 -->
        <linearGradient id="horizon-mist" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#ffcf9a" stop-opacity="0" />
          <stop offset="50%" stop-color="#ffcf9a" stop-opacity="0.28" />
          <stop offset="100%" stop-color="#ffcf9a" stop-opacity="0" />
        </linearGradient>
        <!-- 山间冷雾带 -->
        <linearGradient id="mountain-fog" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#cbb4e0" stop-opacity="0" />
          <stop offset="50%" stop-color="#cbb4e0" stop-opacity="0.14" />
          <stop offset="100%" stop-color="#cbb4e0" stop-opacity="0" />
        </linearGradient>
        <!-- 月牙与银辉 -->
        <radialGradient id="moon-halo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#dfe6ff" stop-opacity="0.55" />
          <stop offset="55%" stop-color="#b9c6f2" stop-opacity="0.16" />
          <stop offset="100%" stop-color="#b9c6f2" stop-opacity="0" />
        </radialGradient>
        <mask id="crescent-mask">
          <rect width="480" height="900" fill="white" />
          <circle cx="414" cy="106" r="15" fill="black" />
        </mask>
        <!-- 流星尾迹 -->
        <linearGradient id="meteor-grad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="0.9" />
          <stop offset="100%" stop-color="#ffffff" stop-opacity="0" />
        </linearGradient>
        <!-- 水洼映空 -->
        <linearGradient id="pond-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#8a5f9e" />
          <stop offset="100%" stop-color="#2b1743" />
        </linearGradient>
        <!-- 暗角 (聚焦巢区) -->
        <radialGradient id="vignette" cx="50%" cy="58%" r="72%">
          <stop offset="0%" stop-color="#0a041a" stop-opacity="0" />
          <stop offset="62%" stop-color="#0a041a" stop-opacity="0" />
          <stop offset="100%" stop-color="#0a041a" stop-opacity="0.5" />
        </radialGradient>
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
        <filter id="blur12" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="12" />
        </filter>
        <filter id="blur24" x="-90%" y="-90%" width="280%" height="280%">
          <feGaussianBlur stdDeviation="24" />
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
        <path
          class="tw d3"
          d="M240,52 L241.2,56.3 L245.5,57.5 L241.2,58.7 L240,63 L238.8,58.7 L234.5,57.5 L238.8,56.3 Z"
        />
        <path
          class="tw"
          d="M430,236 L430.9,239.7 L434,240.6 L430.9,241.5 L430,245 L429.1,241.5 L426,240.6 L429.1,239.7 Z"
        />
        <path
          class="tw d2"
          d="M60,140 L60.9,143.7 L64,144.6 L60.9,145.5 L60,149 L59.1,145.5 L56,144.6 L59.1,143.7 Z"
        />
      </g>
      <!-- 补星: 色温分层 (白/暖黄/淡蓝) -->
      <g>
        <circle class="tw d1" cx="150" cy="40" r="0.9" fill="#cfe0ff" />
        <circle class="tw d3" cx="260" cy="150" r="0.8" fill="#ffe9c8" />
        <circle class="tw d2" cx="330" cy="45" r="1" fill="#cfe0ff" />
        <circle class="tw" cx="390" cy="170" r="0.9" fill="#ffe9c8" />
        <circle class="tw d1" cx="85" cy="105" r="0.8" fill="#ffffff" />
        <circle class="tw d3" cx="180" cy="205" r="1" fill="#cfe0ff" />
        <circle class="tw d2" cx="455" cy="120" r="0.8" fill="#ffffff" />
        <circle class="tw" cx="15" cy="150" r="1" fill="#ffe9c8" />
        <circle class="tw d1" cx="285" cy="240" r="0.7" fill="#ffffff" />
        <circle class="tw d3" cx="120" cy="290" r="0.8" fill="#cfe0ff" />
        <circle class="tw d2" cx="370" cy="300" r="0.9" fill="#ffe9c8" />
        <circle class="tw" cx="215" cy="90" r="0.7" fill="#ffffff" />
      </g>

      <!-- 银河带: 斜向碎星 + 柔光带 -->
      <g opacity="0.55">
        <ellipse cx="250" cy="170" rx="200" ry="34" fill="#b9c6f2" opacity="0.07"
                 transform="rotate(-24 250 170)" filter="url(#blur24)" />
        <g fill="#e8e4ff" opacity="0.5">
          <circle cx="96" cy="266" r="0.7" /><circle cx="118" cy="252" r="0.9" />
          <circle cx="140" cy="240" r="0.6" /><circle cx="158" cy="228" r="1" />
          <circle cx="176" cy="214" r="0.7" /><circle cx="196" cy="204" r="0.9" />
          <circle cx="214" cy="190" r="0.6" /><circle cx="232" cy="182" r="1" />
          <circle cx="250" cy="168" r="0.7" /><circle cx="270" cy="158" r="0.9" />
          <circle cx="288" cy="146" r="0.6" /><circle cx="306" cy="136" r="1" />
          <circle cx="324" cy="122" r="0.7" /><circle cx="344" cy="112" r="0.8" />
          <circle cx="362" cy="100" r="0.6" /><circle cx="382" cy="90" r="0.9" />
          <circle cx="150" cy="252" r="0.6" /><circle cx="240" cy="176" r="0.6" />
        </g>
      </g>

      <!-- 月牙与银辉 (与落日冷暖对望) -->
      <circle cx="404" cy="118" r="46" fill="url(#moon-halo)" />
      <circle cx="404" cy="118" r="17" fill="#f2f0ff" mask="url(#crescent-mask)" />

      <!-- 流星 (错峰划过, 克制而惊艳) -->
      <g class="meteor m1">
        <line x1="360" y1="60" x2="410" y2="32" stroke="url(#meteor-grad)" stroke-width="1.6" stroke-linecap="round" />
      </g>
      <g class="meteor m2">
        <line x1="150" y1="90" x2="196" y2="66" stroke="url(#meteor-grad)" stroke-width="1.3" stroke-linecap="round" />
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

      <!-- 落日（藏于远山之后, 加超大柔光层） -->
      <circle cx="130" cy="440" r="190" fill="url(#sun-halo)" filter="url(#blur24)" opacity="0.7" />
      <circle cx="130" cy="440" r="118" fill="url(#sun-halo)" />
      <circle cx="130" cy="440" r="44" fill="#ffe3b0" />
      <circle cx="130" cy="440" r="44" fill="#ffffff" opacity="0.22" filter="url(#blur2)" />

      <!-- 地平线暖雾光带 -->
      <rect x="0" y="420" width="480" height="70" fill="url(#horizon-mist)" />

      <!-- 最远山脊 (淡紫, 空气透视最外层) -->
      <path
        d="M0,452 C70,428 160,444 250,452 C330,460 420,436 480,448 L480,900 L0,900 Z"
        fill="#6e4a8a"
        opacity="0.28"
      />

      <!-- 三层远山（空气透视） + 山间雾带 -->
      <path
        d="M0,468 C80,432 152,452 232,468 C320,486 402,442 480,460 L480,900 L0,900 Z"
        fill="#5e3a7d"
        opacity="0.42"
      />
      <rect x="0" y="446" width="480" height="46" fill="url(#mountain-fog)" />
      <path
        d="M0,506 C92,470 182,498 262,510 C352,524 424,486 480,502 L480,900 L0,900 Z"
        fill="#472a63"
        opacity="0.62"
      />
      <!-- 山谷灯火: 远处村庄的暖光 (呼应蘑菇村) -->
      <g fill="#ffd9a0">
        <circle class="tw d1" cx="292" cy="500" r="1.6" filter="url(#blur2)" />
        <circle class="tw d3" cx="310" cy="505" r="1.2" filter="url(#blur2)" />
        <circle class="tw d2" cx="326" cy="498" r="1.4" filter="url(#blur2)" />
        <circle class="tw" cx="342" cy="506" r="1.1" filter="url(#blur2)" />
        <circle class="tw d2" cx="360" cy="500" r="1.5" filter="url(#blur2)" />
        <circle class="tw d3" cx="376" cy="507" r="1.1" filter="url(#blur2)" />
      </g>
      <rect x="0" y="490" width="480" height="42" fill="url(#mountain-fog)" />
      <!-- 山脊剪影树丛 -->
      <g fill="#3d2458" opacity="0.8">
        <circle cx="60" cy="498" r="5" /><circle cx="74" cy="501" r="4" />
        <circle cx="420" cy="492" r="5" /><circle cx="434" cy="496" r="4" />
        <circle cx="448" cy="493" r="4.5" />
      </g>
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

      <!-- 小水洼: 映着天光与月影, 偶有涟漪 -->
      <g>
        <ellipse cx="92" cy="668" rx="52" ry="11" fill="url(#pond-grad)" opacity="0.9" />
        <ellipse cx="92" cy="666" rx="34" ry="6" fill="#c9b8e8" opacity="0.18" filter="url(#blur2)" />
        <!-- 月牙倒影 -->
        <ellipse cx="86" cy="666" rx="7" ry="2" fill="#f2f0ff" opacity="0.4" filter="url(#blur2)" />
        <ellipse class="ripple r1" cx="92" cy="668" rx="30" ry="6" fill="none"
                 stroke="#d8c8f0" stroke-width="1" opacity="0" />
        <ellipse class="ripple r2" cx="92" cy="668" rx="30" ry="6" fill="none"
                 stroke="#d8c8f0" stroke-width="0.8" opacity="0" />
      </g>

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
        <!-- 木漏光斑: 透过树冠洒落的柔光 -->
        <g fill="#ffe9c8" filter="url(#blur6)">
          <circle cx="372" cy="520" r="7" opacity="0.14" />
          <circle cx="410" cy="540" r="5" opacity="0.12" />
          <circle cx="350" cy="556" r="4" opacity="0.1" />
          <circle cx="428" cy="516" r="4.5" opacity="0.12" />
        </g>
        <!-- 树上挂灯: 灯核+大光晕, 微风摆动 -->
        <g class="lantern-swing">
          <line x1="428" y1="470" x2="428" y2="502" stroke="rgba(255,233,168,0.35)" stroke-width="1" />
          <circle cx="428" cy="506" r="10" fill="#ffdf9e" opacity="0.3" filter="url(#blur6)" />
          <circle class="glow-dot" cx="428" cy="506" r="3.4" fill="#ffe9a8" filter="url(#blur2)" />
        </g>
        <g class="lantern-swing ls2">
          <line x1="356" y1="506" x2="356" y2="532" stroke="rgba(255,233,168,0.35)" stroke-width="1" />
          <circle cx="356" cy="536" r="8" fill="#ffdf9e" opacity="0.28" filter="url(#blur6)" />
          <circle class="glow-dot gd2" cx="356" cy="536" r="2.6" fill="#ffe9a8" filter="url(#blur2)" />
        </g>
      </g>

      <!-- 飘落花瓣: 从树的方向随风飘来 -->
      <g fill="#f6c9d8">
        <path class="petal p1" d="M420,470 q3,-2 5,1 q-1,3 -4,2 q-2,-1 -1,-3 Z" opacity="0.85" />
        <path class="petal p2" d="M390,500 q3,-2 5,1 q-1,3 -4,2 q-2,-1 -1,-3 Z" opacity="0.75" />
        <path class="petal p3" d="M440,530 q3,-2 5,1 q-1,3 -4,2 q-2,-1 -1,-3 Z" opacity="0.8" />
        <path class="petal p4" d="M370,560 q2.6,-1.8 4.4,0.9 q-0.9,2.6 -3.5,1.8 q-1.8,-0.9 -0.9,-2.7 Z" opacity="0.7" />
        <path class="petal p5" d="M410,600 q2.6,-1.8 4.4,0.9 q-0.9,2.6 -3.5,1.8 q-1.8,-0.9 -0.9,-2.7 Z" opacity="0.75" />
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

      <!-- 宠物周尘埃光粒: 缓缓升起 -->
      <g fill="#ffe9c8">
        <circle class="mote mt1" cx="196" cy="560" r="1" opacity="0.5" />
        <circle class="mote mt2" cx="252" cy="548" r="0.8" opacity="0.4" />
        <circle class="mote mt3" cx="216" cy="596" r="0.9" opacity="0.45" />
        <circle class="mote mt4" cx="268" cy="580" r="0.7" opacity="0.35" />
      </g>

      <!-- 萤火虫: 双层光晕 (柔光晕 + 实心核) -->
      <g>
        <g class="ff f1"><circle cx="118" cy="636" r="6" fill="#ffdf9e" opacity="0.3" filter="url(#blur6)" /><circle cx="118" cy="636" r="2.2" fill="#fff6d8" /></g>
        <g class="ff f2"><circle cx="168" cy="700" r="5.5" fill="#ffdf9e" opacity="0.28" filter="url(#blur6)" /><circle cx="168" cy="700" r="1.8" fill="#fff6d8" /></g>
        <g class="ff f3"><circle cx="282" cy="656" r="6.5" fill="#ffdf9e" opacity="0.3" filter="url(#blur6)" /><circle cx="282" cy="656" r="2.4" fill="#fff6d8" /></g>
        <g class="ff f4"><circle cx="322" cy="716" r="5" fill="#ffdf9e" opacity="0.26" filter="url(#blur6)" /><circle cx="322" cy="716" r="1.7" fill="#fff6d8" /></g>
        <g class="ff f5"><circle cx="88" cy="742" r="5.5" fill="#ffdf9e" opacity="0.28" filter="url(#blur6)" /><circle cx="88" cy="742" r="2" fill="#fff6d8" /></g>
        <g class="ff f6"><circle cx="152" cy="588" r="5" fill="#ffdf9e" opacity="0.26" filter="url(#blur6)" /><circle cx="152" cy="588" r="1.6" fill="#fff6d8" /></g>
        <g class="ff f7"><circle cx="296" cy="588" r="5.5" fill="#ffdf9e" opacity="0.28" filter="url(#blur6)" /><circle cx="296" cy="588" r="1.9" fill="#fff6d8" /></g>
        <g class="ff f8"><circle cx="330" cy="560" r="5" fill="#ffdf9e" opacity="0.25" filter="url(#blur6)" /><circle cx="330" cy="560" r="1.5" fill="#fff6d8" /></g>
        <g class="ff f9"><circle cx="60" cy="600" r="5" fill="#ffdf9e" opacity="0.26" filter="url(#blur6)" /><circle cx="60" cy="600" r="1.6" fill="#fff6d8" /></g>
        <g class="ff f10"><circle cx="390" cy="640" r="5.5" fill="#ffdf9e" opacity="0.27" filter="url(#blur6)" /><circle cx="390" cy="640" r="1.8" fill="#fff6d8" /></g>
        <g class="ff f11"><circle cx="200" cy="740" r="5" fill="#ffdf9e" opacity="0.25" filter="url(#blur6)" /><circle cx="200" cy="740" r="1.6" fill="#fff6d8" /></g>
        <g class="ff f12"><circle cx="420" cy="700" r="5" fill="#ffdf9e" opacity="0.24" filter="url(#blur6)" /><circle cx="420" cy="700" r="1.5" fill="#fff6d8" /></g>
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

      <!-- 暗角: 视线聚焦巢区 -->
      <rect width="480" height="900" fill="url(#vignette)" />

      <!-- 纸感噪点 -->
      <rect width="480" height="900" filter="url(#noise)" opacity="0.045" />
    </svg>

    <!-- 生成形象层: 帧动画宠物 (巢穴位置); H2: 旅行中不显示 (空房) -->
    <div v-if="phase === 'pet' && spriteReady && pet && !pet.away" class="sprite-layer">
      <PetSprite ref="spriteRef" :pet-id="pet.id" action="idle" />
    </div>

    <!-- H3: 归来便签信 —— 钉在树上的纸便签 (规范 v1.1: 功能物=场景实物), 点击才拆开 -->
    <button
      v-if="letter && !letterOpen"
      class="pinned-note"
      aria-label="拆开旅行信件"
      @click="openLetter"
    >
      <span class="pin"></span>
      <span class="pinned-note-icon">✉️</span>
      <span class="pinned-note-label">{{ pet?.name }}的信</span>
    </button>

    <!-- ================= UI 层 ================= -->
    <!-- 品牌标题: 宠物出现后隐去 (规范 v1.1 §3.2: 场景中心留给宠物) -->
    <header v-if="phase !== 'pet'" class="hero">
      <p class="eyebrow">PET PARADISE</p>
      <h1 class="title">宠物乐园</h1>
      <p class="subtitle">每一颗蛋里，都住着一个等待遇见你的小灵魂</p>
    </header>

    <!-- 蛋期/孵化期: 底部紧凑玻璃坞 (过渡阶段) -->
    <section v-if="phase !== 'pet'" class="panel">
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
    </section>

    <!-- ===== 宠物阶段: 环形贴边 UI (规范 v1.1 §3.2) ===== -->
    <template v-else-if="pet">
      <!-- 顶左: 宠物信息木牌 (头像 + 名字/标签, 学农场左上信息区) -->
      <div class="pet-plaque">
        <img class="plaque-avatar" :src="`/static/pets/${pet.id}/frames/idle_0.png`" :alt="pet.name" />
        <div class="plaque-info">
          <p class="pet-name">{{ pet.name }}</p>
          <p class="pet-species">{{ pet.color }}{{ pet.species }} · Lv.{{ pet.level }}</p>
          <div class="chips">
            <span v-for="tag in pet.personality.tags" :key="tag" class="chip">{{ tag }}</span>
          </div>
          <p v-if="spritePending" class="plaque-hint">✨ {{ pet.name }}的专属形象正在成形中…</p>
          <p v-if="!pet.away" class="plaque-hint">
            天赋：{{ pet.talents.map((t) => t.name).join('、') }} ｜ 技能：{{ pet.skills.map((s) => s.name).join('、') }}
          </p>
        </div>
      </div>

      <!-- 旅行中: 底部纸张细横幅 (H2), 不占主动作位 -->
      <div v-if="pet.away" class="away-banner">
        <span class="away-line">
          🏕️ 「{{ pet.name }}」去了{{ pet.travel?.dest ?? '远方' }}<template v-if="backAtText"> · 预计 {{ backAtText }} 归来</template>
        </span>
        <span v-if="awayLoadout" class="away-pack">
          🎒
          <template v-for="slot in LOADOUT_SLOTS" :key="slot.key">
            <span v-if="loadoutItemName(awayLoadout[slot.key])" class="away-loadout-item">
              {{ slot.label }}·{{ loadoutItemName(awayLoadout[slot.key]) }}
            </span>
          </template>
          <span v-if="!awayLoadout.food && !awayLoadout.gift && !awayLoadout.charm">什么也没带</span>
        </span>
      </div>
      <template v-else>
        <!-- 左下: 主动作大木牌 (学旅行青蛙「准备」, 插画+文字) -->
        <router-link to="/pack" class="wood-btn wood-primary">
          <span class="wood-icon">🎒</span>
          <span>打包行李</span>
        </router-link>
      </template>
      <!-- 右下: 次导航木牌 (插画+文字) -->
      <router-link to="/collection" class="wood-btn wood-side">
        <span class="wood-icon">🧺</span>
        <span>收藏</span>
      </router-link>
    </template>

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
            :class="`rarity-${it.rarity}`"
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
        <button class="wood-btn letter-close" @click="closeLetter">收好啦</button>
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
.f8 { animation-delay: -2s; animation-duration: 7.2s; }
.f9 { animation-delay: -3.8s; animation-duration: 8.8s; }
.f10 { animation-delay: -5.6s; animation-duration: 7s; }
.f11 { animation-delay: -1.6s; animation-duration: 9.4s; }
.f12 { animation-delay: -4.9s; animation-duration: 8.2s; }
@keyframes firefly {
  0%, 100% { opacity: 0.12; transform: translate(0, 0); }
  30% { opacity: 0.95; }
  55% { opacity: 0.3; transform: translate(12px, -16px); }
  80% { opacity: 0.85; transform: translate(4px, -26px); }
}

/* 流星: 12s/17s 周期, 只在短暂窗口划过 (规范 §4: 克制) */
.meteor {
  opacity: 0;
  transform-box: fill-box;
}
.m1 { animation: meteor-fly 12s linear infinite; animation-delay: 2s; }
.m2 { animation: meteor-fly 17s linear infinite; animation-delay: 9s; }
@keyframes meteor-fly {
  0% { opacity: 0; transform: translate(0, 0); }
  2% { opacity: 0.9; }
  8% { opacity: 0; transform: translate(-140px, 82px); }
  100% { opacity: 0; transform: translate(-140px, 82px); }
}

/* 水洼涟漪: 扩散+淡出 */
.ripple {
  transform-box: fill-box;
  transform-origin: center;
  animation: ripple-spread 5.2s var(--ease-out) infinite;
}
.r2 { animation-delay: 2.6s; }
@keyframes ripple-spread {
  0% { opacity: 0; transform: scale(0.35); }
  18% { opacity: 0.4; }
  100% { opacity: 0; transform: scale(1.5); }
}

/* 飘落花瓣: 下落 + 左右飘摆 + 自转 */
.petal {
  transform-box: fill-box;
  transform-origin: center;
  animation: petal-fall 11s linear infinite;
}
.p1 { animation-delay: 0s; }
.p2 { animation-delay: -2.6s; animation-duration: 13s; }
.p3 { animation-delay: -5.2s; animation-duration: 10s; }
.p4 { animation-delay: -7.4s; animation-duration: 12s; }
.p5 { animation-delay: -9.6s; animation-duration: 14s; }
@keyframes petal-fall {
  0% { opacity: 0; transform: translate(0, 0) rotate(0deg); }
  8% { opacity: 0.85; }
  50% { transform: translate(-46px, 90px) rotate(200deg); }
  92% { opacity: 0.7; }
  100% { opacity: 0; transform: translate(-90px, 190px) rotate(420deg); }
}

/* 尘埃光粒: 缓升 + 呼吸 */
.mote {
  transform-box: fill-box;
  animation: mote-rise 6s ease-in-out infinite;
}
.mt2 { animation-delay: -1.5s; animation-duration: 7s; }
.mt3 { animation-delay: -3s; animation-duration: 5.4s; }
.mt4 { animation-delay: -4.5s; animation-duration: 6.6s; }
@keyframes mote-rise {
  0%, 100% { opacity: 0.15; transform: translateY(0); }
  50% { opacity: 0.6; transform: translateY(-14px); }
}

/* 挂灯微风摆动 (挂点为原点) */
.lantern-swing {
  transform-box: fill-box;
  transform-origin: top center;
  animation: lantern-sway 4.6s ease-in-out infinite;
}
.ls2 { animation-delay: 2.3s; }
@keyframes lantern-sway {
  0%, 100% { transform: rotate(-2.4deg); }
  50% { transform: rotate(2.4deg); }
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

/* 宠物木牌上的文字 (规范 v1.1 §1: 木牌用奶白文字) */
.pet-name {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-xxl);
  font-weight: 700;
  letter-spacing: 2px;
  color: #ffedc9;
  text-shadow: 0 1px 2px rgba(60, 30, 10, 0.6);
}
.pet-species {
  margin: 2px 0 0;
  font-size: var(--fs-sm);
  color: rgba(255, 237, 201, 0.8);
}
.chips {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.chip {
  padding: 3px 11px;
  border-radius: 999px;
  font-size: var(--fs-xs);
  letter-spacing: 1px;
  color: #ffe3b3;
  background: rgba(60, 35, 15, 0.35);
  border: 1px solid rgba(255, 235, 200, 0.3);
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

/* ===== 宠物阶段环形贴边 UI (规范 v1.1 §3.2) ===== */
/* 顶左: 宠物信息木牌 */
.pet-plaque {
  position: absolute;
  z-index: 2;
  top: 14px;
  left: 14px;
  max-width: 72%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px 9px 9px;
  border: 2px solid var(--color-wood-edge);
  border-radius: 14px;
  background:
    repeating-linear-gradient(90deg, rgba(60, 35, 15, 0.07) 0 2px, transparent 2px 8px),
    var(--gradient-wood);
  box-shadow: 0 6px 18px rgba(10, 6, 20, 0.45), inset 0 1px 0 rgba(255, 235, 200, 0.3);
  rotate: -1.2deg;
}
.plaque-avatar {
  width: 52px;
  height: 52px;
  flex: none;
  border-radius: 10px;
  border: 2px solid rgba(255, 237, 201, 0.5);
  background: rgba(60, 35, 15, 0.35);
  object-fit: cover;
}
.plaque-info {
  min-width: 0;
}
.plaque-hint {
  margin: 6px 0 0;
  font-size: var(--fs-xs);
  color: rgba(255, 237, 201, 0.75);
  letter-spacing: 0.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* 左下/右下木牌定位 (rotate 用独立属性, 不与按压 scale 冲突) */
.wood-primary {
  position: absolute;
  z-index: 2;
  left: 16px;
  bottom: 16px;
  padding: 13px 26px;
  font-size: var(--fs-xl);
  rotate: -1.5deg;
}
.wood-side {
  position: absolute;
  z-index: 2;
  right: 16px;
  bottom: 16px;
  padding: 10px 18px;
  font-size: var(--fs-md);
  rotate: 1.2deg;
}
/* 旅行中: 底部纸张细横幅 (H2, 学农场任务条) */
.away-banner {
  position: absolute;
  z-index: 2;
  left: 50%;
  bottom: 16px;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  max-width: 88%;
  padding: 8px 18px;
  border: 1px solid var(--color-paper-edge);
  border-radius: 12px;
  background: linear-gradient(180deg, #f9efdb, #efdfbe);
  box-shadow: 0 6px 18px rgba(10, 6, 20, 0.45);
  font-size: var(--fs-sm);
  color: var(--color-paper-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.away-pack {
  font-size: var(--fs-xs);
  color: #7a5c3a;
}
.away-loadout-item {
  margin: 0 3px;
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(122, 85, 48, 0.12);
  border: 1px solid rgba(122, 85, 48, 0.3);
}

/* ===== 归来便签信 (H3, 规范 v1.1): 钉在树上的纸便签, 不遮挡宠物 ===== */
.pinned-note {
  position: absolute;
  right: 12%;
  top: 45%;
  z-index: 12;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 15px 16px 9px;
  border: 1px solid var(--color-paper-edge);
  border-radius: 6px;
  background: linear-gradient(175deg, #f9efdb, #efdfbe);
  box-shadow: 0 6px 18px rgba(10, 6, 20, 0.5), 0 0 24px rgba(255, 230, 170, 0.22);
  cursor: pointer;
  rotate: -3deg;
  animation: note-bob 1.6s ease-in-out infinite;
}
@keyframes note-bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-7px); }
}
.pin {
  position: absolute;
  top: -5px;
  left: 50%;
  margin-left: -5px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #ff9d7a, #d44a3c);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
}
.pinned-note-icon {
  font-size: 24px;
}
.pinned-note-label {
  font-size: var(--fs-xs);
  letter-spacing: 1px;
  font-weight: 600;
  color: var(--color-paper-text);
}

/* ===== 拆开的信件 (H4, 规范 v1.1): 信纸抽屉(纸张质感), 上方宠物保持可见 ===== */
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
.letter-title {
  margin: 0 0 12px;
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 700;
  letter-spacing: 2px;
  color: #7a4a1e;
  text-align: center;
}
.letter-text {
  margin: 0;
  font-size: var(--fs-lg);
  line-height: 1.8;
  color: var(--color-paper-text);
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
  background: rgba(122, 85, 48, 0.07);
  border: 1px solid rgba(122, 85, 48, 0.25);
}
/* 纸上品级色: 压暗一档 (规范 v1.1 §1) */
.letter-item.rarity-rare {
  border-color: rgba(74, 111, 165, 0.65);
  box-shadow: 0 0 12px rgba(74, 111, 165, 0.25);
}
.letter-item.rarity-epic {
  border-color: rgba(184, 134, 46, 0.75);
  box-shadow: 0 0 14px rgba(184, 134, 46, 0.3);
}
.letter-item-img {
  width: 44px;
  height: 44px;
  border-radius: 8px;
}
.letter-item-name {
  font-size: var(--fs-xs);
  color: var(--color-paper-text);
  text-align: center;
}
.letter-item-rarity {
  font-size: 10px;
  color: #8a7a5f;
}
.letter-item.rarity-rare .letter-item-rarity { color: #4a6fa5; }
.letter-item.rarity-epic .letter-item-rarity { color: #b8862e; }
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
  font-size: var(--fs-md);
  color: #b8862e;
  font-variant-numeric: tabular-nums;
}
.letter-notes {
  margin-top: 8px;
}
.letter-note {
  margin: 4px 0 0;
  font-size: var(--fs-sm);
  color: #a08a6a;
}
.letter-close {
  display: block;
  width: 100%;
  margin-top: 18px;
  padding: 12px 0;
}
</style>
