import { defineStore } from 'pinia'
import { ref } from 'vue'

export type AppTheme = 'paper' | 'tech'

export const THEME_KEY = 'app_theme'
export const THEMES: { key: AppTheme; label: string; hint: string }[] = [
  { key: 'paper', label: '暖纸', hint: '浅色，适合日常备课' },
  { key: 'tech', label: '科技', hint: '冷色浅底，干净利落' },
]

export function readStoredTheme(): AppTheme {
  const raw = localStorage.getItem(THEME_KEY)
  return raw === 'tech' ? 'tech' : 'paper'
}

export function applyTheme(theme: AppTheme) {
  const root = document.documentElement
  root.dataset.theme = theme
  root.classList.remove('dark')
}

export const useAppearanceStore = defineStore('appearance', () => {
  const theme = ref<AppTheme>(readStoredTheme())
  applyTheme(theme.value)

  function setTheme(next: AppTheme | string) {
    const t: AppTheme = next === 'tech' ? 'tech' : 'paper'
    theme.value = t
    localStorage.setItem(THEME_KEY, t)
    applyTheme(t)
  }

  function toggle() {
    setTheme(theme.value === 'paper' ? 'tech' : 'paper')
  }

  return { theme, setTheme, toggle }
})
