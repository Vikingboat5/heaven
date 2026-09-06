<script setup lang="ts">
/** 诞生问答 (S3.2): 注册送蛋后回答几个问题, 影响宠物的性格/物种/画风/配色 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, ApiError, type QuizQuestion } from '../api/client'

const router = useRouter()
const questions = ref<QuizQuestion[]>([])
const idx = ref(0)
const answers = ref<Record<string, string>>({})
const picked = ref('')        // 当前题选中的选项(用于高亮与延时跳转)
const customText = ref('')    // choice_or_text / text 的输入
const error = ref('')
const submitting = ref(false)
const loading = ref(true)

const current = computed<QuizQuestion | null>(() => questions.value[idx.value] ?? null)
const total = computed(() => questions.value.length)

onMounted(async () => {
  try {
    questions.value = await api.getQuiz()
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '加载失败, 请刷新重试'
  } finally {
    loading.value = false
  }
})

function next() {
  picked.value = ''
  customText.value = ''
  if (idx.value < total.value - 1) {
    idx.value++
  } else {
    void submit()
  }
}

/** 选择题: 选中高亮后短暂停顿自动进入下一题, 给用户确认感 */
function choose(key: string) {
  if (!current.value || picked.value) return
  picked.value = key
  answers.value[current.value.key] = key
  setTimeout(next, 300)
}

/** 手动输入(色系自定义 / IP 角色) */
function confirmText() {
  if (!current.value) return
  const text = customText.value.trim()
  if (!text) return
  answers.value[current.value.key] = text
  next()
}

function skip() {
  next()  // 可选题跳过: 不记录答案
}

async function submit() {
  submitting.value = true
  error.value = ''
  try {
    await api.submitQuiz(answers.value)
    router.push('/')
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '提交失败, 请重试'
    submitting.value = false
  }
}
</script>

<template>
  <div class="quiz-page">
    <div class="fireflies">
      <span v-for="i in 12" :key="i" class="firefly" :style="{ '--i': i }"></span>
    </div>

    <div v-if="loading" class="card">
      <p class="loading-text">蛋正在苏醒…</p>
    </div>

    <div v-else-if="current" class="card" :key="current.key">
      <p class="progress">第 {{ idx + 1 }} / {{ total }} 题</p>
      <div class="dots">
        <span v-for="i in total" :key="i" class="dot" :class="{ on: i - 1 <= idx }"></span>
      </div>

      <h1 class="title">{{ idx === 0 ? '蛋想更了解你…' : '' }}{{ current.text }}</h1>

      <!-- 选择题 -->
      <div v-if="current.type === 'choice'" class="options">
        <button
          v-for="opt in current.options" :key="opt.key"
          class="option" :class="{ picked: picked === opt.key }"
          @click="choose(opt.key)"
        >{{ opt.text }}</button>
      </div>

      <!-- 选择 + 手动输入 (色系) -->
      <div v-else-if="current.type === 'choice_or_text'" class="options">
        <button
          v-for="opt in current.options" :key="opt.key"
          class="option" :class="{ picked: picked === opt.key }"
          @click="choose(opt.key)"
        >{{ opt.text }}</button>
        <div class="text-row">
          <input
            v-model="customText" :maxlength="current.max_len ?? 10"
            class="text-input" placeholder="或者自己写一个, 比如: 薄荷绿"
            @keyup.enter="confirmText"
          >
          <button class="mini-btn" :disabled="!customText.trim()" @click="confirmText">确定</button>
        </div>
      </div>

      <!-- 纯文本 (IP 角色, 可跳过) -->
      <div v-else class="options">
        <div class="text-row">
          <input
            v-model="customText" :maxlength="current.max_len ?? 30"
            class="text-input" placeholder="写下它的名字…"
            @keyup.enter="confirmText"
          >
          <button class="mini-btn" :disabled="!customText.trim()" @click="confirmText">确定</button>
        </div>
        <button v-if="current.optional" class="skip" @click="skip">暂时没有, 跳过 →</button>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="submitting" class="loading-text">蛋把你的答案收好了…</p>
    </div>
  </div>
</template>

<style scoped>
.quiz-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #150c2e 0%, #2a1845 60%, #3d1d4e 100%);
  display: flex; align-items: center; justify-content: center;
  position: relative; overflow: hidden;
  font-family: system-ui, sans-serif;
}
.fireflies { position: absolute; inset: 0; pointer-events: none; }
.firefly {
  position: absolute; width: 4px; height: 4px; border-radius: 50%;
  background: #ffd9a0; opacity: .5;
  left: calc(var(--i) * 8%); top: calc((var(--i) * 37) % 90 * 1%);
  animation: float 6s ease-in-out infinite;
  animation-delay: calc(var(--i) * -0.7s);
  box-shadow: 0 0 8px #ffd9a0;
}
@keyframes float {
  0%, 100% { transform: translateY(0); opacity: .25; }
  50% { transform: translateY(-18px); opacity: .7; }
}
.card {
  position: relative; z-index: 1;
  width: min(420px, 88vw);
  background: rgba(30, 18, 54, .82);
  border: 1px solid rgba(255, 217, 160, .18);
  border-radius: 20px; padding: 32px 28px;
  backdrop-filter: blur(6px);
}
.progress { color: #b79fd8; font-size: var(--fs-sm); margin: 0 0 6px; letter-spacing: 2px; }
.dots { display: flex; gap: 6px; margin-bottom: 18px; }
.dot { width: 18px; height: 4px; border-radius: 2px; background: rgba(255,255,255,.12); }
.dot.on { background: linear-gradient(90deg, #f2b06e, #e87a9a); }
.title { color: #ffe9d0; font-size: var(--fs-xxl); font-weight: 600; margin: 0 0 22px; line-height: 1.5; }
.options { display: flex; flex-direction: column; gap: 10px; }
.option {
  padding: 13px 16px; border-radius: 12px; text-align: left;
  background: rgba(255, 255, 255, .06); color: #f0e6ff; font-size: var(--fs-lg);
  border: 1px solid rgba(255, 255, 255, .1); cursor: pointer;
  transition: all .18s;
}
.option:hover { background: rgba(242, 176, 110, .15); border-color: rgba(242, 176, 110, .4); }
.option.picked {
  background: linear-gradient(90deg, rgba(242,176,110,.35), rgba(232,122,154,.35));
  border-color: #f2b06e; transform: scale(1.02);
}
.text-row { display: flex; gap: 8px; margin-top: 4px; }
.text-input {
  flex: 1; padding: 12px 14px; border-radius: 12px;
  background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.15);
  color: #ffe9d0; font-size: var(--fs-lg); outline: none;
}
.text-input:focus { border-color: #f2b06e; }
.text-input::placeholder { color: rgba(255,233,208,.35); }
.mini-btn {
  padding: 0 18px; border: none; border-radius: 12px; cursor: pointer;
  background: linear-gradient(90deg, #f2b06e, #e87a9a); color: #2a1040;
  font-size: var(--fs-lg); font-weight: 600;
}
.mini-btn:disabled { opacity: .35; cursor: default; }
.skip {
  margin-top: 10px; background: none; border: none; cursor: pointer;
  color: #b79fd8; font-size: var(--fs-md); align-self: center;
}
.skip:hover { color: #ffe9d0; }
.error { color: #ff9a9a; font-size: var(--fs-md); margin: 14px 0 0; }
.loading-text { color: #b79fd8; text-align: center; margin: 14px 0 0; font-size: var(--fs-lg); }
</style>
