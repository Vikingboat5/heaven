<script setup lang="ts">
/**
 * 底部 tab 导航 (规范 v1.3): 小窝/日记/背包 三个同级 tab
 * AI 图标 + 激活弹跳; 出现在登录后的主页面 (登录/问答页不显示)
 */
import { useRoute } from 'vue-router'

const route = useRoute()

const TABS = [
  { name: 'home', label: '小窝', icon: '/static/ui/icon_home.png', to: '/' },
  { name: 'diary', label: '日记', icon: '/static/ui/icon_book.png', to: '/diary' },
  { name: 'collection', label: '背包', icon: '/static/ui/icon_basket.png', to: '/collection' },
]
</script>

<template>
  <nav class="tab-bar" aria-label="主导航">
    <router-link
      v-for="t in TABS"
      :key="t.name"
      :to="t.to"
      class="tab-item"
      :class="{ active: route.name === t.name }"
    >
      <img class="tab-icon" :src="t.icon" alt="" />
      <span class="tab-label">{{ t.label }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.tab-bar {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 480px;
  z-index: 30;
  display: flex;
  justify-content: space-around;
  padding: 8px 12px 10px;
  background: linear-gradient(180deg, rgba(30, 18, 58, 0.72), rgba(21, 12, 46, 0.92));
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-top: 1px solid rgba(255, 255, 255, 0.09);
}
.tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 4px 18px;
  text-decoration: none;
  border-radius: 14px;
  opacity: 0.65;
  transition: opacity var(--motion-fast) var(--ease-out),
    background var(--motion-fast) var(--ease-out);
}
.tab-item.active {
  opacity: 1;
  background: rgba(247, 201, 138, 0.12);
}
.tab-icon {
  width: 34px;
  height: 34px;
  object-fit: contain;
  filter: drop-shadow(0 2px 3px rgba(10, 6, 20, 0.5));
}
.tab-label {
  font-family: var(--font-display);
  font-size: var(--fs-xs);
  letter-spacing: 2px;
  color: var(--color-text-dim);
}
.tab-item.active .tab-label {
  color: var(--color-gold);
}
/* 激活弹跳 (规范 v1.3 动效) */
.tab-item.active .tab-icon {
  animation: tab-pop 0.4s var(--ease-spring);
}
@keyframes tab-pop {
  0% { transform: scale(0.7); }
  60% { transform: scale(1.18); }
  100% { transform: scale(1); }
}
</style>
