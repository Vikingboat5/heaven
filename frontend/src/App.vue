<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.clearAuth()
  router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <router-link to="/" class="logo">宠物乐园</router-link>
      <nav>
        <template v-if="auth.token">
          <router-link to="/" class="nav-pill">家园</router-link>
          <router-link to="/chat" class="nav-pill">对话</router-link>
          <button class="nav-pill user-pill" title="退出登录" @click="logout">
            {{ auth.username }} · 退出
          </button>
        </template>
        <router-link v-else to="/login" class="nav-pill">登录</router-link>
      </nav>
    </header>
    <main>
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  max-width: 480px;
  margin: 0 auto;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 0 80px rgba(0, 0, 0, 0.5);
}
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 18px;
  background: rgba(21, 12, 46, 0.4);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  position: sticky;
  top: 0;
  z-index: 10;
}
.logo {
  font-weight: 700;
  font-size: 17px;
  letter-spacing: 3px;
  color: var(--color-gold);
  text-decoration: none;
  text-shadow: 0 1px 8px rgba(247, 201, 138, 0.3);
}
nav {
  display: flex;
  gap: 6px;
  align-items: center;
}
.nav-pill {
  padding: 6px 15px;
  border-radius: 999px;
  color: rgba(253, 240, 220, 0.7);
  text-decoration: none;
  font-size: 13px;
  letter-spacing: 1px;
  transition: all 0.25s;
  border: none;
  background: none;
  cursor: pointer;
  font-family: inherit;
}
.nav-pill.router-link-active {
  background: rgba(255, 255, 255, 0.13);
  color: #fff;
  font-weight: 600;
}
.user-pill {
  color: var(--color-gold);
  border: 1px solid rgba(247, 201, 138, 0.25);
}
.user-pill:hover {
  background: rgba(247, 201, 138, 0.12);
}
main {
  flex: 1;
  display: flex;
  flex-direction: column;
}
</style>
