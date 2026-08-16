import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'

const TOKEN_KEY = 'pp_token'
const USERNAME_KEY = 'pp_username'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) ?? '')
  const username = ref<string>(localStorage.getItem(USERNAME_KEY) ?? '')

  function setAuth(t: string, u: string) {
    token.value = t
    username.value = u
    localStorage.setItem(TOKEN_KEY, t)
    localStorage.setItem(USERNAME_KEY, u)
  }

  function clearAuth() {
    token.value = ''
    username.value = ''
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USERNAME_KEY)
  }

  async function login(u: string, p: string) {
    const r = await api.login(u, p)
    setAuth(r.token, r.user.username)
  }

  async function register(u: string, p: string) {
    const r = await api.register(u, p)
    setAuth(r.token, r.user.username)
  }

  return { token, username, setAuth, clearAuth, login, register }
})
