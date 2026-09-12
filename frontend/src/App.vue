<script setup lang="ts">
// 全局 header 已撤下 (规范 v1.2): 主页即场景; 底部 tab 导航 (规范 v1.3)
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import BottomTabBar from './components/BottomTabBar.vue'

const route = useRoute()
const auth = useAuthStore()
// 登录后除问答/登录页外都显示底部 tab
const showTabs = computed(() => !!auth.token && route.name !== 'login' && route.name !== 'quiz')
</script>

<template>
  <div class="app-shell">
    <main :class="{ 'with-tabs': showTabs }">
      <!-- 规范 §4: 页面转场 fade + 上移 8px -->
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <BottomTabBar v-if="showTabs" />
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

/* 页面转场 (规范 §4) */
.page-enter-active,
.page-leave-active {
  transition: opacity 220ms var(--ease-out), transform 220ms var(--ease-out);
}
.page-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
main {
  flex: 1;
  display: flex;
  flex-direction: column;
}
main.with-tabs {
  padding-bottom: 76px; /* 底部 tab bar 占位 */
}
</style>
