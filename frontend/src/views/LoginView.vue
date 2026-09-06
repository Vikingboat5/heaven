<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ApiError } from '../api/client'

const router = useRouter()
const auth = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  if (busy.value) return
  error.value = ''
  busy.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(username.value.trim(), password.value)
    } else {
      await auth.register(username.value.trim(), password.value)
    }
    router.push('/')
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '网络异常, 请稍后再试'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login-scene">
    <div class="card">
      <p class="eyebrow">PET PARADISE</p>
      <h1 class="title">{{ mode === 'login' ? '欢迎回来' : '加入宠物乐园' }}</h1>
      <p class="subtitle">
        {{ mode === 'login' ? '你的小家伙一直在等你' : '注册即可获得第一枚宠物蛋' }}
      </p>

      <form class="form" @submit.prevent="submit">
        <input
          v-model="username"
          placeholder="用户名 (2-16 位)"
          minlength="2"
          maxlength="16"
          required
          autocomplete="username"
        />
        <input
          v-model="password"
          type="password"
          placeholder="密码 (至少 6 位)"
          minlength="6"
          maxlength="64"
          required
          autocomplete="current-password"
        />
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" :disabled="busy">
          {{ busy ? '请稍候…' : mode === 'login' ? '登录' : '注册并领取宠物蛋' }}
        </button>
      </form>

      <p class="switch">
        {{ mode === 'login' ? '还没有账号？' : '已经有账号了？' }}
        <a href="javascript:void 0" @click="mode = mode === 'login' ? 'register' : 'login'; error = ''">
          {{ mode === 'login' ? '去注册' : '去登录' }}
        </a>
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-scene {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 22px;
  background: linear-gradient(180deg, #1b1040 0%, #2c1a4e 55%, #3d2358 100%);
}
.card {
  width: 100%;
  max-width: 360px;
  padding: 34px 28px 26px;
  border-radius: 22px;
  background: rgba(22, 12, 44, 0.55);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid rgba(255, 255, 255, 0.09);
  box-shadow: 0 12px 40px rgba(10, 4, 26, 0.45);
  text-align: center;
}
.eyebrow {
  margin: 0 0 10px;
  font-size: var(--fs-xs);
  letter-spacing: 5px;
  color: rgba(255, 233, 200, 0.55);
}
.title {
  margin: 0;
  font-size: var(--fs-display);
  font-weight: 600;
  letter-spacing: 4px;
  color: #fdf6ec;
}
.subtitle {
  margin: 10px 0 24px;
  font-size: var(--fs-md);
  color: rgba(253, 240, 220, 0.55);
}
.form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.form input {
  padding: 12px 16px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 14px;
  outline: none;
  font-size: var(--fs-lg);
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-text);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.form input:focus {
  border-color: rgba(242, 165, 110, 0.55);
  box-shadow: 0 0 0 4px rgba(242, 165, 110, 0.12);
}
.form input::placeholder {
  color: rgba(253, 240, 220, 0.35);
}
.form button {
  margin-top: 4px;
  padding: 13px 0;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, #f2a56e, #e77fa2);
  color: #fff;
  font-size: var(--fs-lg);
  font-weight: 600;
  letter-spacing: 2px;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(231, 127, 162, 0.35);
  transition: transform 0.15s;
}
.form button:disabled {
  opacity: 0.5;
}
.error {
  margin: 0;
  font-size: var(--fs-md);
  color: #ff9d9d;
}
.switch {
  margin: 20px 0 0;
  font-size: var(--fs-md);
  color: rgba(253, 240, 220, 0.5);
}
.switch a {
  color: var(--color-gold);
  text-decoration: none;
}
</style>
