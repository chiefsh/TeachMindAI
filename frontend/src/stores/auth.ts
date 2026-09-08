import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api/modules'
import type { Teacher } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const teacher = ref<Teacher | null>(null)
  const token = ref<string>(localStorage.getItem('token') || '')

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)
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
      teacher.value = res
    } catch {
      logout()
    }
  }

  async function updateProfile(data: { real_name?: string; email?: string }) {
    const res: any = await authApi.updateMe(data)
    teacher.value = res
    return res
  }

  async function logout() {
    try { await authApi.logout() } catch {}
    token.value = ''
    teacher.value = null
    localStorage.removeItem('token')
  }

  const isLoggedIn = () => !!token.value

  return { teacher, token, login, logout, fetchMe, updateProfile, isLoggedIn }
})
