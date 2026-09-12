import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import LoginView from './views/LoginView.vue'
import QuizView from './views/QuizView.vue'
import PackView from './views/PackView.vue'
import CollectionView from './views/CollectionView.vue'
import DiaryView from './views/DiaryView.vue'
import PetView from './views/PetView.vue'
import PostcardWallView from './views/PostcardWallView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/quiz', name: 'quiz', component: QuizView },
    // v1.3 (ADR-003): 对话移出 MVP, /chat 重定向回主页; ChatView 代码保留备拓展
    { path: '/chat', redirect: '/' },
    { path: '/pack', name: 'pack', component: PackView },
    { path: '/collection', name: 'collection', component: CollectionView },
    // 2026-09-06: 日记拆分为独立页 (原收藏页标签)
    { path: '/diary', name: 'diary', component: DiaryView },
    // H7: 宠物详情页 (改名/重新生成形象/退出)
    { path: '/pet', name: 'pet', component: PetView },
    // 规范 v1.3: 明信片墙 (软木钉墙)
    { path: '/postcards', name: 'postcards', component: PostcardWallView },
    // v1.2: 旅行日记并入收藏页, 旧链接重定向 → 2026-09 改指独立日记页
    { path: '/adventure', redirect: '/diary' },
    { path: '/login', name: 'login', component: LoginView },
  ],
})

// 简易路由守卫: 除登录页外都需要 token
router.beforeEach((to) => {
  const authed = !!localStorage.getItem('pp_token')
  if (to.name !== 'login' && !authed) {
    return { name: 'login' }
  }
  if (to.name === 'login' && authed) {
    return { name: 'home' }
  }
  return true
})
