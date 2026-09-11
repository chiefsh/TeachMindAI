<template>
  <el-config-provider :locale="zhCn">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { useAuthStore } from '@/stores/auth'
import { useEducationStore } from '@/stores/education'
import { useAppearanceStore } from '@/stores/appearance'

const auth = useAuthStore()
const edu = useEducationStore()
useAppearanceStore()

onMounted(async () => {
  if (auth.isLoggedIn()) {
    await auth.fetchMe()
    await edu.init()
  }
})
</script>
