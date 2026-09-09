import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api/modules'
import type { Teacher } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const teacher = ref<Teacher | null>(null)
  const token = ref<string>(localStorage.getItem('token') || '')
  const permissions = ref<string[]>([])

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)
  }

  function applyMe(res: Teacher) {
    teacher.value = res
    permissions.value = res.permissions || []
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
    return res
  }

  async function fetchMe() {
    if (!token.value) return
    try {
      const res: any = await authApi.me()
      applyMe(res)
    } catch {
      logout()
    }
  }

  async function updateProfile(data: { real_name?: string; email?: string }) {
    const res: any = await authApi.updateMe(data)
    applyMe(res)
    return res
  }

  async function logout() {
    try { await authApi.logout() } catch {}
    token.value = ''
    teacher.value = null
    permissions.value = []
    localStorage.removeItem('token')
  }

  const isLoggedIn = () => !!token.value

  return { teacher, token, permissions, login, logout, fetchMe, updateProfile, isLoggedIn, can }
})
