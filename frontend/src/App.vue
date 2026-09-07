<script setup lang="ts">
// 全局 header 已撤下 (规范 v1.2): 主页即场景; 各内容页自带返回; 退出在宠物详情页
</script>

<template>
  <div class="app-shell">
    <!-- 规范 v1.2: 全局 header 已撤下 (主页即场景; 各内容页自带返回; 退出在宠物详情页) -->
    <main>
      <!-- 规范 §4: 页面转场 fade + 上移 8px, 180ms -->
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
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

/* 页面转场 (规范 §4) */
.page-enter-active,
.page-leave-active {
  transition: opacity 180ms var(--ease-out), transform 180ms var(--ease-out);
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
main {
  flex: 1;
  display: flex;
  flex-direction: column;
}
</style>
