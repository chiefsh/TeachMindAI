<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useEducationStore } from '@/stores/education'

const auth = useAuthStore()
const edu = useEducationStore()

onMounted(async () => {
  if (auth.isLoggedIn()) {
    await auth.fetchMe()
    await edu.init()
  }
})
</script>
