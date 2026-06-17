<template>
  <div class="flex h-screen overflow-hidden bg-slate-50">
    <!-- 侧边栏 -->
    <aside
      class="flex-shrink-0 w-60 bg-white border-r border-slate-100 flex flex-col"
    >
      <!-- Logo -->
      <div class="h-[60px] flex items-center px-5 border-b border-slate-100">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center">
            <el-icon class="text-white text-base"><Reading /></el-icon>
          </div>
          <span class="font-bold text-slate-800 text-base">AI 教学平台</span>
        </div>
      </div>

      <!-- 导航菜单 -->
      <nav class="flex-1 overflow-y-auto py-4 px-3">
        <div v-for="group in navGroups" :key="group.title" class="mb-5">
          <p class="text-[10px] font-semibold text-slate-400 uppercase tracking-widest px-3 mb-1.5">
            {{ group.title }}
          </p>
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: $route.path.startsWith(item.path) }"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </router-link>
        </div>
      </nav>

      <!-- 底部用户信息 -->
      <div class="border-t border-slate-100 p-3">
        <div class="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-slate-50 cursor-pointer">
          <el-avatar :size="32" class="bg-primary-600 text-white flex-shrink-0">
            {{ auth.teacher?.real_name?.charAt(0) || '师' }}
          </el-avatar>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-slate-700 truncate">{{ auth.teacher?.real_name }}</p>
            <p class="text-xs text-slate-400 truncate">{{ auth.teacher?.username }}</p>
          </div>
          <el-button link @click="handleLogout" class="!text-slate-400 hover:!text-slate-600">
            <el-icon><SwitchButton /></el-icon>
          </el-button>
        </div>
      </div>
    </aside>

    <!-- 主区域 -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <!-- 顶栏 -->
      <header class="h-[60px] bg-white border-b border-slate-100 flex items-center px-6 gap-4 flex-shrink-0">
        <!-- 学段/年级/科目选择器 -->
        <div class="flex items-center gap-2">
          <el-select
            v-model="edu.selectedSchoolLevelId"
            placeholder="选择学段"
            size="small"
            style="width: 90px"
            @change="edu.selectSchoolLevel"
            clearable
          >
            <el-option v-for="l in edu.schoolLevels" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>

          <el-select
            v-model="edu.selectedGradeId"
            placeholder="年级"
            size="small"
            style="width: 90px"
            @change="edu.selectGrade"
            :disabled="!edu.selectedSchoolLevelId"
            clearable
          >
            <el-option v-for="g in edu.filteredGrades" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>

          <el-select
            v-model="edu.selectedSubjectId"
            placeholder="科目"
            size="small"
            style="width: 90px"
            @change="edu.selectSubject"
            :disabled="!edu.selectedSchoolLevelId"
            clearable
          >
            <el-option v-for="s in edu.filteredSubjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </div>

        <div class="flex-1" />

        <!-- 当前上下文标签 -->
        <div v-if="edu.selectedSchoolLevel" class="flex items-center gap-1.5">
          <el-tag size="small" type="info">{{ edu.selectedSchoolLevel?.name }}</el-tag>
          <el-tag v-if="edu.selectedGrade" size="small">{{ edu.selectedGrade?.name }}</el-tag>
          <el-tag v-if="edu.selectedSubject" size="small" type="success">{{ edu.selectedSubject?.name }}</el-tag>
        </div>
      </header>

      <!-- 页面内容 -->
      <main class="flex-1 overflow-y-auto">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useEducationStore } from '@/stores/education'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'

const auth = useAuthStore()
const edu = useEducationStore()
const router = useRouter()

const navGroups = [
  {
    title: '概览',
    items: [
      { path: '/dashboard', label: '工作台', icon: 'HomeFilled' },
    ],
  },
  {
    title: '教学资源',
    items: [
      { path: '/textbook',      label: '课本管理', icon: 'Collection' },
      { path: '/question-bank', label: '题库管理', icon: 'EditPen' },
    ],
  },
  {
    title: 'AI 生成',
    items: [
      { path: '/courseware', label: '课件生成', icon: 'VideoPlay' },
      { path: '/homework',   label: '作业/考试', icon: 'Tickets' },
    ],
  },
  {
    title: '数据分析',
    items: [
      { path: '/grades', label: '学生成绩', icon: 'TrendCharts' },
    ],
  },
  {
    title: '系统',
    items: [
      { path: '/settings', label: '系统设置', icon: 'Setting' },
    ],
  },
]

async function handleLogout() {
  await ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning' })
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.nav-item {
  @apply flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-600
         hover:bg-slate-50 hover:text-slate-900 transition-colors duration-150 mb-0.5;
}
.nav-item.active {
  @apply bg-primary-50 text-primary-700 font-medium;
}
.nav-item .el-icon { @apply text-base; }
</style>
