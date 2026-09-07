<script setup lang="ts">
/**
 * 宠物详情页 (H7): 点击主页铭牌进入
 * 当前形象 / 改名 / 重新生成形象(异步) / 退出登录
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, ApiError, type PetOut } from '../api/client'
import { useAuthStore } from '../stores/auth'
import PetSprite from '../components/PetSprite.vue'

const router = useRouter()
const auth = useAuthStore()

const pet = ref<PetOut | null>(null)
const loading = ref(true)
const error = ref('')
const nameDraft = ref('')
const busy = ref(false)
const notice = ref('')

onMounted(async () => {
  try {
    pet.value = await api.getMyPet()
    nameDraft.value = pet.value?.name ?? ''
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})

async function saveName() {
  const name = nameDraft.value.trim()
  if (!name || name === pet.value?.name || busy.value) return
  busy.value = true
  try {
    const r = await api.renamePet(name)
    if (pet.value) pet.value.name = r.name
    notice.value = '名字改好啦'
  } catch (e) {
    notice.value = e instanceof ApiError ? e.message : '改名失败'
  } finally {
    busy.value = false
  }
}

async function regen() {
  if (busy.value) return
  busy.value = true
  try {
    const r = await api.regenSprite()
    notice.value = r.ok ? '形象重新生成中，过几分钟回来看看' : (r.detail ?? '稍后再试')
  } catch (e) {
    notice.value = e instanceof ApiError ? e.message : '操作失败'
  } finally {
    busy.value = false
  }
}

function logout() {
  auth.clearAuth()
  router.push('/login')
}
</script>

<template>
  <div class="page pet-page">
    <div class="stars"><i /><i /></div>
    <header class="pet-head">
      <button class="back" @click="router.back()">‹ 回家</button>
      <h2>{{ pet?.name ?? '小家伙' }}</h2>
    </header>

    <p v-if="loading" class="state-text">加载中…</p>
    <p v-else-if="error" class="state-text">{{ error }}</p>
    <template v-else-if="pet">
      <!-- 当前形象 -->
      <div class="sprite-box">
        <PetSprite v-if="pet.sprite_status === 'ready'" :pet-id="pet.id" action="idle" />
        <p v-else class="state-text">✨ 形象正在生成中…</p>
      </div>
      <p class="pet-sub">{{ pet.color }}{{ pet.species }} · Lv.{{ pet.level }}</p>
      <div class="chips">
        <span v-for="tag in pet.personality.tags" :key="tag" class="chip">{{ tag }}</span>
      </div>
      <p class="hint">
        天赋：{{ pet.talents.map((t) => t.name).join('、') }} ｜ 技能：{{ pet.skills.map((s) => s.name).join('、') }}
      </p>

      <!-- 改名 -->
      <div class="rename-row">
        <input v-model="nameDraft" class="name-input" maxlength="16" placeholder="给它起个名字" />
        <button class="wood-btn save-btn" :disabled="busy" @click="saveName">保存名字</button>
      </div>

      <button class="wood-btn regen-btn" :disabled="busy || pet.sprite_status === 'pending'" @click="regen">
        重新生成形象
      </button>
      <p class="hint">重新生成会换一套全新的动作图，原来的就退休啦</p>

      <p v-if="notice" class="notice">{{ notice }}</p>

      <button class="logout-btn" @click="logout">退出登录（{{ auth.username }}）</button>
    </template>
  </div>
</template>

<style scoped>
.pet-page {
  position: relative;
  flex: 1;
  padding: 20px 20px 40px;
  background: linear-gradient(180deg, #1a1038 0%, #150c2e 60%, #1e1242 100%);
  overflow: hidden;
}
.stars i {
  position: absolute;
  width: 3px; height: 3px; border-radius: 50%;
  background: #fff; opacity: 0.5;
  animation: twinkle 3.2s ease-in-out infinite;
}
.stars i:first-child { top: 18%; left: 20%; }
.stars i:last-child { top: 12%; right: 22%; animation-delay: 1.6s; }
@keyframes twinkle { 0%, 100% { opacity: 0.2; } 50% { opacity: 0.7; } }

.pet-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
}
.pet-head h2 {
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

.sprite-box {
  width: 60%;
  margin: 8px auto 0;
  aspect-ratio: 1;
}
.pet-sub {
  text-align: center;
  margin: 6px 0 0;
  font-size: var(--fs-lg);
  color: var(--color-text-dim);
}
.chips {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 10px;
}
.chip {
  padding: 3px 11px;
  border-radius: 999px;
  font-size: var(--fs-xs);
  letter-spacing: 1px;
  color: #f7c98a;
  background: rgba(247, 201, 138, 0.12);
  border: 1px solid rgba(247, 201, 138, 0.28);
}
.hint {
  text-align: center;
  font-size: var(--fs-sm);
  color: var(--color-text-faint);
  margin: 10px 0 0;
}

.rename-row {
  display: flex;
  gap: 8px;
  margin-top: 22px;
}
.name-input {
  flex: 1;
  padding: 11px 14px;
  border: 1px solid var(--color-glass-border);
  border-radius: 12px;
  outline: none;
  font-size: var(--fs-lg);
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-text);
  font-family: inherit;
}
.save-btn {
  padding: 8px 18px;
  font-size: var(--fs-md);
  letter-spacing: 2px;
}
.regen-btn {
  display: block;
  width: 100%;
  margin-top: 18px;
  padding: 12px 0;
  font-size: var(--fs-lg);
}
.notice {
  text-align: center;
  margin: 14px 0 0;
  font-size: var(--fs-md);
  color: var(--color-gold);
}
.logout-btn {
  display: block;
  margin: 34px auto 0;
  padding: 10px 22px;
  border: 1px solid rgba(255, 122, 122, 0.3);
  border-radius: 999px;
  background: none;
  color: rgba(255, 150, 150, 0.8);
  font-size: var(--fs-md);
  letter-spacing: 1px;
  cursor: pointer;
}
.state-text { text-align: center; color: var(--color-text-faint); font-size: var(--fs-md); margin-top: 40px; }
</style>
