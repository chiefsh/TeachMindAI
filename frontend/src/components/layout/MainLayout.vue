<template>
  <div class="flex h-screen overflow-hidden bg-slate-50">
    <!-- 桌面端固定侧栏 -->
    <aside
      v-if="isDesktop"
      class="flex-shrink-0 w-60 bg-white border-r border-slate-100 flex flex-col"
    >
      <div class="h-[60px] flex items-center px-5 border-b border-slate-100">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center">
            <el-icon class="text-white text-base"><Reading /></el-icon>
          </div>
          <span class="font-bold text-slate-800 text-base">AI 教学平台</span>
        </div>
      </div>
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
      <div class="border-t border-slate-100 p-3">
        <div class="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-slate-50">
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

    <!-- 移动/平板：抽屉侧栏 -->
    <el-drawer
      v-else
      v-model="drawerOpen"
      direction="ltr"
      size="260px"
      :with-header="false"
      class="mobile-nav-drawer"
    >
      <div class="h-full bg-white flex flex-col">
        <div class="h-[56px] flex items-center px-5 border-b border-slate-100">
          <div class="flex items-center gap-2.5">
            <div class="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center">
              <el-icon class="text-white text-base"><Reading /></el-icon>
            </div>
            <span class="font-bold text-slate-800 text-base">AI 教学平台</span>
          </div>
        </div>
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
              @click="drawerOpen = false"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </router-link>
          </div>
        </nav>
        <div class="border-t border-slate-100 p-3">
          <div class="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-slate-50">
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
      </div>
    </el-drawer>

    <!-- 主区域 -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <header
        class="min-h-[56px] md:h-[60px] bg-white border-b border-slate-100 flex items-center
               px-3 sm:px-4 md:px-6 gap-2 sm:gap-3 flex-shrink-0 flex-wrap py-2 md:py-0"
      >
        <el-button
          v-if="!isDesktop"
          text
          class="!px-2 flex-shrink-0"
          @click="drawerOpen = true"
        >
          <el-icon :size="22"><Fold /></el-icon>
        </el-button>

        <div class="flex items-center gap-1.5 sm:gap-2 flex-1 min-w-0 overflow-x-auto no-scrollbar">
          <el-select
            v-model="edu.selectedSchoolLevelId"
            placeholder="学段"
            size="small"
            class="ctx-select"
            @change="edu.selectSchoolLevel"
            clearable
          >
            <el-option v-for="l in edu.schoolLevels" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>

          <el-select
            v-model="edu.selectedGradeId"
            placeholder="年级"
            size="small"
            class="ctx-select"
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
            class="ctx-select"
            @change="edu.selectSubject"
            :disabled="!edu.selectedSchoolLevelId"
            clearable
          >
            <el-option v-for="s in edu.filteredSubjects" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </div>

        <div v-if="edu.selectedSchoolLevel" class="hidden lg:flex items-center gap-1.5 flex-shrink-0">
          <el-tag size="small" type="info">{{ edu.selectedSchoolLevel?.name }}</el-tag>
          <el-tag v-if="edu.selectedGrade" size="small">{{ edu.selectedGrade?.name }}</el-tag>
          <el-tag v-if="edu.selectedSubject" size="small" type="success">{{ edu.selectedSubject?.name }}</el-tag>
        </div>
      </header>

      <main class="flex-1 overflow-y-auto overflow-x-hidden">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import { useAuthStore } from '@/stores/auth'
import { useEducationStore } from '@/stores/education'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Fold } from '@element-plus/icons-vue'

const auth = useAuthStore()
const edu = useEducationStore()
const router = useRouter()
const route = useRoute()

const isDesktop = useMediaQuery('(min-width: 1024px)')
const drawerOpen = ref(false)

watch(isDesktop, (v) => { if (v) drawerOpen.value = false })
watch(() => route.path, () => { drawerOpen.value = false })

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
      { path: '/question-analysis', label: '试题分析', icon: 'DataAnalysis' },
    ],
  },
  {
    title: '数据分析',
    items: [
      { path: '/grades', label: '学生成绩', icon: 'TrendCharts' },
      { path: '/knowledge', label: '知识图谱', icon: 'Connection' },
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
.ctx-select {
  width: 76px;
  flex-shrink: 0;
}
@media (min-width: 640px) {
  .ctx-select { width: 90px; }
}
.nav-item {
  @apply flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-slate-600
         hover:bg-slate-50 hover:text-slate-900 transition-colors duration-150 mb-0.5;
}
.nav-item.active {
  @apply bg-primary-50 text-primary-700 font-medium;
}
.nav-item .el-icon { @apply text-base; }

.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>

<style>
.mobile-nav-drawer .el-drawer__body {
  padding: 0 !important;
  overflow: hidden;
}
</style>
