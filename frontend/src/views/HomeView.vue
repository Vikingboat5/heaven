<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, ApiError, type AdventureLogOut, type EggOut, type PetOut } from '../api/client'
import PetSprite from '../components/PetSprite.vue'

const router = useRouter()

type Phase = 'loading' | 'egg' | 'ready' | 'pet'

const phase = ref<Phase>('loading')
const egg = ref<EggOut | null>(null)
const pet = ref<PetOut | null>(null)
const hatchName = ref('')
const busy = ref(false)
const toast = ref('')
const returnLog = ref<AdventureLogOut | null>(null)

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

/** 回端检测: 离线超阈值会触发一次冒险, 有新日志则展示回归卡片 */
async function checkReturn() {
  try {
    const r = await api.checkAdventure()
    if (r.new_log) {
      returnLog.value = r.new_log
      // 冒险结算可能改变宠物状态, 重新拉取
      const p = await api.getMyPet()
      if (p) pet.value = p
    }
  } catch {
    // 静默: 检测失败不影响主页
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
  if (spritePending.value) pollSprite()
})
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
        <p v-else class="hint center">暂时没有正在孵化的蛋，未来完成任务可获得新蛋</p>
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

        <p class="hint">
          天赋：{{ pet.talents.map((t) => t.name).join('、') }} ｜ 技能：{{ pet.skills.map((s) => s.name).join('、') }}
        </p>

        <router-link to="/chat" class="cta">和「{{ pet.name }}」聊聊</router-link>

        <div class="action-row">
          <router-link to="/adventure" class="action-btn">冒险日志</router-link>
        </div>
      </template>
    </section>

    <!-- 冒险回归卡片 -->
    <div v-if="returnLog" class="mask" @click.self="returnLog = null">
      <div class="return-card">
        <p class="return-title">{{ pet?.name }}回来了！</p>
        <p class="return-text">{{ returnLog.narrative }}</p>
        <div v-if="returnLog.rewards" class="return-rewards">
          <span v-if="returnLog.rewards.exp" class="reward-chip">经验 +{{ returnLog.rewards.exp }}</span>
          <span v-for="item in returnLog.rewards.items ?? []" :key="item" class="reward-chip">
            获得「{{ item }}」
          </span>
        </div>
        <button class="cta" @click="returnLog = null">太好啦</button>
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

/* 生成形象层: 覆盖在巢穴位置 (巢中心 x≈47%, 巢面 y≈64%) */
.sprite-layer {
  position: absolute;
  left: 47%;
  top: 46%;
  width: 44%;
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
.hero {
  position: relative;
  z-index: 2;
  text-align: center;
  margin-top: 58px;
  pointer-events: none;
}
.eyebrow {
  margin: 0 0 10px;
  font-size: 11px;
  letter-spacing: 5px;
  color: rgba(255, 233, 200, 0.55);
}
.title {
  margin: 0;
  font-size: 36px;
  font-weight: 600;
  letter-spacing: 10px;
  text-indent: 10px; /* 视觉居中补偿字间距 */
  color: #fdf6ec;
  text-shadow: 0 2px 24px rgba(255, 200, 140, 0.35), 0 1px 2px rgba(40, 16, 60, 0.6);
}
.subtitle {
  margin: 12px 0 0;
  font-size: 13px;
  letter-spacing: 1px;
  color: rgba(253, 240, 220, 0.6);
}

/* ---------- 底部面板 ---------- */
.panel {
  position: absolute;
  z-index: 2;
  left: 22px;
  right: 22px;
  bottom: 32px;
  padding: 18px 20px 20px;
  border-radius: 20px;
  background: rgba(22, 12, 44, 0.55);
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

/* 宠物卡片 */
.pet-name {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #fdf6ec;
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

/* 状态条 */
.state-bars {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.state-bar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.state-label {
  width: 34px;
  font-size: 12px;
  letter-spacing: 1px;
  color: rgba(255, 240, 220, 0.65);
}
.state-track {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  overflow: hidden;
}
.state-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.5s ease;
  opacity: 0.9;
}
.state-value {
  width: 26px;
  text-align: right;
  font-size: 12px;
  color: rgba(255, 240, 220, 0.65);
  font-variant-numeric: tabular-nums;
}

/* 操作按钮组 */
.action-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 14px;
}
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

/* 冒险回归卡片 */
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
.return-card {
  width: 100%;
  max-width: 380px;
  padding: 24px 22px;
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(42, 24, 74, 0.96), rgba(26, 15, 56, 0.96));
  border: 1px solid rgba(247, 201, 138, 0.25);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 40px rgba(247, 201, 138, 0.08);
  animation: card-in 0.35s ease;
}
@keyframes card-in {
  from { transform: translateY(20px) scale(0.96); opacity: 0; }
  to { transform: translateY(0) scale(1); opacity: 1; }
}
.return-title {
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--color-gold);
  text-align: center;
}
.return-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: var(--color-text);
}
.return-rewards {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}
.reward-chip {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  color: #f7c98a;
  background: rgba(247, 201, 138, 0.12);
  border: 1px solid rgba(247, 201, 138, 0.25);
}
.return-card .cta {
  margin-top: 18px;
}
</style>
