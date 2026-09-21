<template>
  <button
    type="button"
    class="theme-chip"
    :title="appearance.theme === 'paper' ? '切换到科技主题' : '切换到暖纸主题'"
    :aria-label="appearance.theme === 'paper' ? '当前暖纸，点击切换到科技' : '当前科技，点击切换到暖纸'"
    @click="appearance.toggle()"
  >
    <el-icon :size="15">
      <Notebook v-if="appearance.theme === 'paper'" />
      <Cpu v-else />
    </el-icon>
    <span class="hidden sm:inline">{{ appearance.theme === 'paper' ? '暖纸' : '科技' }}</span>
  </button>
</template>

<script setup lang="ts">
import { Cpu, Notebook } from '@element-plus/icons-vue'
import { useAppearanceStore } from '@/stores/appearance'

const appearance = useAppearanceStore()
</script>

<style scoped>
.theme-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--muted-fill);
  color: var(--ink-secondary);
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  flex-shrink: 0;
  transition: background 160ms ease, border-color 160ms ease, color 160ms ease, transform 160ms ease;
}
.theme-chip:hover {
  background: var(--hover);
  color: var(--ink);
  border-color: var(--ink-muted);
}
.theme-chip:active {
  transform: scale(0.98);
}
.theme-chip:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}
</style>
