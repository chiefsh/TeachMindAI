<template>
  <el-button
    text
    class="!px-2 flex-shrink-0"
    :title="appearance.theme === 'paper' ? '切换到科技主题' : '切换到暖纸主题'"
    @click="appearance.toggle()"
  >
    <el-icon :size="18">
      <Cpu v-if="appearance.theme === 'paper'" />
      <Notebook v-else />
    </el-icon>
  </el-button>
</template>

<script setup lang="ts">
import { Cpu, Notebook } from '@element-plus/icons-vue'
import { useAppearanceStore } from '@/stores/appearance'

const appearance = useAppearanceStore()
</script>
