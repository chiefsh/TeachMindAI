<template>
  <div class="p-6">
    <div class="mb-6">
      <h1 class="page-title">工作台</h1>
      <p class="page-subtitle">欢迎回来，{{ auth.teacher?.real_name }} 老师</p>
    </div>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
      <div v-for="stat in stats" :key="stat.label" class="card">
        <div class="flex items-start justify-between">
          <div>
            <p class="text-sm text-slate-500">{{ stat.label }}</p>
            <p class="text-2xl font-bold text-slate-800 mt-1">{{ stat.value }}</p>
          </div>
          <div :class="`w-10 h-10 rounded-lg ${stat.bgColor} flex items-center justify-center`">
            <el-icon :class="`text-xl ${stat.color}`"><component :is="stat.icon" /></el-icon>
          </div>
        </div>
      </div>
    </div>

    <!-- 快捷入口 -->
    <div class="card mb-6">
      <h3 class="text-sm font-semibold text-slate-600 mb-4">快捷操作</h3>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <router-link
          v-for="action in quickActions"
          :key="action.label"
          :to="action.path"
          class="flex flex-col items-center justify-center gap-2 p-4 rounded-xl border-2 border-dashed border-slate-200 hover:border-primary-400 hover:bg-primary-50 transition-all text-slate-500 hover:text-primary-600"
        >
          <el-icon class="text-2xl"><component :is="action.icon" /></el-icon>
          <span class="text-xs font-medium">{{ action.label }}</span>
        </router-link>
      </div>
    </div>

    <!-- 当前教学科目 -->
    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-semibold text-slate-600">我的教学科目</h3>
        <router-link to="/settings" class="text-xs text-primary-600 hover:underline">管理科目 →</router-link>
      </div>
      <div v-if="edu.mySubjects.length" class="flex flex-wrap gap-2">
        <div
          v-for="ts in edu.mySubjects"
          :key="ts.id"
          class="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 rounded-lg border border-slate-100"
        >
          <span class="text-xs text-slate-500">{{ ts.grade.name }}</span>
          <span class="text-xs text-slate-300">·</span>
          <span class="text-sm font-medium text-slate-700">{{ ts.subject.name }}</span>
        </div>
      </div>
      <div v-else class="text-sm text-slate-400 py-4 text-center">
        暂未配置教学科目，前往
        <router-link to="/settings" class="text-primary-600 hover:underline">系统设置</router-link>
        添加
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useEducationStore } from '@/stores/education'
import { dashboardApi } from '@/api/modules'

const auth = useAuthStore()
const edu = useEducationStore()

const stats = ref([
  { key: 'textbook_count',   label: '课本数量',  value: '—' as string | number, icon: 'Collection', bgColor: 'bg-blue-50',   color: 'text-blue-500' },
  { key: 'question_count',   label: '题库题目',  value: '—' as string | number, icon: 'EditPen',    bgColor: 'bg-purple-50', color: 'text-purple-500' },
  { key: 'courseware_count', label: '已生成课件', value: '—' as string | number, icon: 'VideoPlay',  bgColor: 'bg-green-50',  color: 'text-green-500' },
  { key: 'student_count',    label: '学生人数',  value: '—' as string | number, icon: 'User',       bgColor: 'bg-orange-50', color: 'text-orange-500' },
  { key: 'analysis_count',   label: '试题分析',  value: '—' as string | number, icon: 'DataAnalysis', bgColor: 'bg-indigo-50', color: 'text-indigo-500' },
])

onMounted(async () => {
  try {
    const res: any = await dashboardApi.getStats()
    stats.value.forEach(s => { s.value = res[s.key] ?? 0 })
  } catch { /* 忽略统计加载失败 */ }
})

const quickActions = [
  { label: '上传课本', path: '/textbook',      icon: 'Upload' },
  { label: '导入题库', path: '/question-bank', icon: 'EditPen' },
  { label: '生成课件', path: '/courseware',    icon: 'MagicStick' },
  { label: '布置作业', path: '/homework',      icon: 'Tickets' },
  { label: '试题分析', path: '/question-analysis', icon: 'DataAnalysis' },
]
</script>
