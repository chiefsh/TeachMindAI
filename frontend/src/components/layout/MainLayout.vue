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
          <span class="font-bold text-slate-800 text-base">智课星</span>
        </div>
      </div>
      <nav class="flex-1 overflow-y-auto py-3 px-3">
        <div v-for="item in navMenu" :key="item.key" class="mb-0.5">
          <router-link
            v-if="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: isChildActive(item.path) }"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </router-link>
          <template v-else>
            <button
              type="button"
              class="nav-item w-full"
              :class="{ 'nav-group-on': isGroupActive(item) }"
              :aria-expanded="expandedKey === item.key"
              @click="toggle(item)"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span class="flex-1 text-left">{{ item.label }}</span>
              <el-icon
                class="text-xs text-slate-400 transition-transform duration-150"
                :class="{ 'rotate-180': expandedKey === item.key }"
              >
                <ArrowDown />
              </el-icon>
            </button>
            <div
              v-show="expandedKey === item.key"
              class="ml-3 pl-2 border-l border-slate-100"
            >
              <router-link
                v-for="child in item.children"
                :key="child.path"
                :to="child.path"
                class="nav-item !py-2 !text-[13px]"
                :class="{ active: isChildActive(child.path) }"
              >
                <el-icon><component :is="child.icon" /></el-icon>
                <span>{{ child.label }}</span>
              </router-link>
            </div>
          </template>
        </div>
      </nav>
      <div class="border-t border-slate-100 p-3">
        <div class="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-slate-50">
          <button type="button" class="flex items-center gap-3 flex-1 min-w-0 text-left" @click="profileOpen = true">
            <el-avatar :size="32" class="bg-primary-600 text-white flex-shrink-0">
              {{ auth.teacher?.real_name?.charAt(0) || '师' }}
            </el-avatar>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-slate-700 truncate">{{ auth.teacher?.real_name }}</p>
              <p class="text-xs text-slate-400 truncate">{{ auth.teacher?.username }}</p>
            </div>
          </button>
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
            <span class="font-bold text-slate-800 text-base">智课星</span>
          </div>
        </div>
        <nav class="flex-1 overflow-y-auto py-3 px-3">
          <div v-for="item in navMenu" :key="item.key" class="mb-0.5">
            <router-link
              v-if="item.path"
              :to="item.path"
              class="nav-item"
              :class="{ active: isChildActive(item.path) }"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </router-link>
            <template v-else>
              <button
                type="button"
                class="nav-item w-full"
                :class="{ 'nav-group-on': isGroupActive(item) }"
                :aria-expanded="expandedKey === item.key"
                @click="toggle(item)"
              >
                <el-icon><component :is="item.icon" /></el-icon>
                <span class="flex-1 text-left">{{ item.label }}</span>
                <el-icon
                  class="text-xs text-slate-400 transition-transform duration-150"
                  :class="{ 'rotate-180': expandedKey === item.key }"
                >
                  <ArrowDown />
                </el-icon>
              </button>
              <div
                v-show="expandedKey === item.key"
                class="ml-3 pl-2 border-l border-slate-100"
              >
                <router-link
                  v-for="child in item.children"
                  :key="child.path"
                  :to="child.path"
                  class="nav-item !py-2 !text-[13px]"
                  :class="{ active: isChildActive(child.path) }"
                >
                  <el-icon><component :is="child.icon" /></el-icon>
                  <span>{{ child.label }}</span>
                </router-link>
              </div>
            </template>
          </div>
        </nav>
        <div class="border-t border-slate-100 p-3">
          <div class="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-slate-50">
            <button type="button" class="flex items-center gap-3 flex-1 min-w-0 text-left" @click="profileOpen = true">
              <el-avatar :size="32" class="bg-primary-600 text-white flex-shrink-0">
                {{ auth.teacher?.real_name?.charAt(0) || '师' }}
              </el-avatar>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-slate-700 truncate">{{ auth.teacher?.real_name }}</p>
                <p class="text-xs text-slate-400 truncate">{{ auth.teacher?.username }}</p>
              </div>
            </button>
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
            <el-option v-for="l in edu.visibleSchoolLevels" :key="l.id" :label="l.name" :value="l.id" />
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
    <ProfileDrawer v-model="profileOpen" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import { useAuthStore } from '@/stores/auth'
import { useEducationStore } from '@/stores/education'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Fold, ArrowDown } from '@element-plus/icons-vue'
import ProfileDrawer from './ProfileDrawer.vue'

type NavChild = { path: string; label: string; icon: string; perm?: string }
type NavItem = {
  key: string
  label: string
  icon: string
  path?: string
  perm?: string
  children?: NavChild[]
}

const auth = useAuthStore()
const edu = useEducationStore()
const router = useRouter()
const route = useRoute()

const isDesktop = useMediaQuery('(min-width: 1024px)')
const drawerOpen = ref(false)
const profileOpen = ref(false)

const allNav: NavItem[] = [
  { key: 'dashboard', label: '工作台', icon: 'HomeFilled', path: '/dashboard' },
  {
    key: 'resources',
    label: '教学资源',
    icon: 'Collection',
    children: [
      { path: '/textbook', label: '课本管理', icon: 'Collection', perm: 'textbook.view' },
      { path: '/question-bank', label: '题库管理', icon: 'EditPen', perm: 'question.view' },
      { path: '/students', label: '班级/学生', icon: 'User', perm: 'classroom.view' },
    ],
  },
  {
    key: 'ai',
    label: 'AI 生成',
    icon: 'VideoPlay',
    children: [
      { path: '/courseware', label: '课件生成', icon: 'VideoPlay', perm: 'courseware.view' },
      { path: '/homework', label: '作业/考试', icon: 'Tickets', perm: 'homework.view' },
      { path: '/question-analysis', label: '试题分析', icon: 'DataAnalysis', perm: 'analysis.view' },
    ],
  },
  {
    key: 'analytics',
    label: '学情分析',
    icon: 'TrendCharts',
    children: [
      { path: '/grading', label: '批改作业/试卷', icon: 'Finished', perm: 'grading.view' },
      { path: '/wrong-questions', label: '错题本', icon: 'Flag', perm: 'wrong_question.view' },
      { path: '/grades', label: '学生成绩', icon: 'TrendCharts', perm: 'grade.view' },
      { path: '/knowledge', label: '知识图谱', icon: 'Connection', perm: 'knowledge.view' },
    ],
  },
  {
    key: 'users',
    label: '用户管理',
    icon: 'Avatar',
    children: [
      { path: '/users', label: '用户', icon: 'Avatar', perm: 'user.view' },
      { path: '/roles', label: '角色', icon: 'Key', perm: 'role.view' },
    ],
  },
  {
    key: 'settings',
    label: '系统设置',
    icon: 'Setting',
    children: [
      { path: '/settings/models', label: '系统模型', icon: 'Cpu', perm: 'settings.llm' },
      { path: '/settings/prompts', label: '提示词设置', icon: 'ChatDotRound', perm: 'settings.prompt' },
    ],
  },
]

const navMenu = computed(() => {
  return allNav
    .map((item) => {
      if (item.path) return auth.can(item.perm) ? item : null
      const children = (item.children || []).filter(c => auth.can(c.perm))
      return children.length ? { ...item, children } : null
    })
    .filter((x): x is NavItem => !!x)
})

function isChildActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}

function isGroupActive(item: NavItem) {
  if (item.path) return isChildActive(item.path)
  return item.children?.some(c => isChildActive(c.path)) ?? false
}

function groupOf(path: string) {
  return navMenu.value.find(g =>
    (g.path && (path === g.path || path.startsWith(g.path + '/')))
    || g.children?.some(c => path === c.path || path.startsWith(c.path + '/')),
  )?.key ?? ''
}

const expandedKey = ref(groupOf(route.path))

function toggle(item: NavItem) {
  if (!item.children) return
  expandedKey.value = expandedKey.value === item.key ? '' : item.key
}

watch(isDesktop, (v) => { if (v) drawerOpen.value = false })
watch(() => route.path, (p) => {
  drawerOpen.value = false
  expandedKey.value = groupOf(p)
})

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
.nav-group-on {
  @apply text-primary-700 font-medium;
}

.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>

<style>
.mobile-nav-drawer .el-drawer__body {
  padding: 0 !important;
  overflow: hidden;
}
</style>
