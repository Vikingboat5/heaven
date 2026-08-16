import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import ChatView from './views/ChatView.vue'
import LoginView from './views/LoginView.vue'
import AdventureView from './views/AdventureView.vue'
import QuizView from './views/QuizView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/quiz', name: 'quiz', component: QuizView },
    { path: '/chat', name: 'chat', component: ChatView },
    { path: '/adventure', name: 'adventure', component: AdventureView },
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
