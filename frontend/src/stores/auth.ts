import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api/modules'
import type { Teacher } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const teacher = ref<Teacher | null>(null)
  const token = ref<string>(localStorage.getItem('token') || '')
  const permissions = ref<string[]>([])
  const meLoaded = ref(false)
  let mePromise: Promise<void> | null = null

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)
  }

  function applyMe(res: Teacher) {
    teacher.value = res
    permissions.value = res.permissions || []
    meLoaded.value = true
  }

  function clearSession() {
    token.value = ''
    teacher.value = null
    permissions.value = []
    meLoaded.value = false
    mePromise = null
    localStorage.removeItem('token')
  }

  function can(code?: string) {
    if (!code) return true
    if (teacher.value?.is_super) return true
    const perms = permissions.value
    if (perms.includes(code)) return true
    if (code.endsWith('.view')) {
      const stem = code.slice(0, -5)
      return perms.includes(`${stem}.manage`) || perms.includes(`${stem}.edit`) || perms.includes(`${stem}.create`)
    }
    return false
  }

  async function login(username: string, password: string) {
    const res: any = await authApi.login({ username, password })
    setToken(res.access_token)
    teacher.value = {
      id: res.teacher_id,
      username: res.username,
      real_name: res.real_name,
      email: '',
      is_active: true,
    }
    meLoaded.value = false
    return res
  }

  async function fetchMe() {
    if (!token.value) return
    if (mePromise) return mePromise
    mePromise = (async () => {
      try {
        const res: any = await authApi.me()
        applyMe(res)
      } catch {
        // 只清本地会话，避免再打 /logout 触发 401 拦截器与路由守卫互锁
        clearSession()
      } finally {
        mePromise = null
      }
    })()
    return mePromise
  }

  async function updateProfile(data: { real_name?: string; email?: string }) {
    const res: any = await authApi.updateMe(data)
    applyMe(res)
    return res
  }

  async function logout() {
    try { await authApi.logout() } catch {}
    clearSession()
  }

  const isLoggedIn = () => !!token.value

  return {
    teacher, token, permissions, meLoaded,
    login, logout, fetchMe, updateProfile, isLoggedIn, can, clearSession,
  }
})
