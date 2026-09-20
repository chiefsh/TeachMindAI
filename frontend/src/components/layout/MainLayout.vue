<template>
  <div class="flex h-screen overflow-hidden" style="background: var(--canvas)">
    <aside
      v-if="isDesktop"
      class="flex-shrink-0 w-60 flex flex-col overflow-hidden"
      style="border-right: 1px solid var(--border-subtle)"
    >
      <AppSidebar
        :nav-menu="navMenu"
        :expanded-key="expandedKey"
        :is-child-active="isChildActive"
        :is-group-active="isGroupActive"
        @toggle="toggle"
        @profile="profileOpen = true"
        @logout="handleLogout"
      />
    </aside>

    <el-drawer
      v-model="drawerOpen"
      direction="ltr"
      size="260px"
      :with-header="false"
      :modal="!isDesktop"
      append-to-body
      class="mobile-nav-drawer"
    >
      <AppSidebar
        v-if="!isDesktop"
        :nav-menu="navMenu"
        :expanded-key="expandedKey"
        :is-child-active="isChildActive"
        :is-group-active="isGroupActive"
        @toggle="toggle"
        @profile="profileOpen = true"
        @logout="handleLogout"
      />
    </el-drawer>

    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <header
        class="min-h-[56px] md:h-[60px] flex items-center
               px-3 sm:px-4 md:px-6 gap-2 sm:gap-3 flex-shrink-0 flex-wrap py-2 md:py-0"
        style="background: var(--surface); border-bottom: 1px solid var(--border-subtle)"
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
          <span class="ctx-pill">{{ edu.selectedSchoolLevel?.name }}</span>
          <span v-if="edu.selectedGrade" class="ctx-pill ctx-pill-ink">{{ edu.selectedGrade?.name }}</span>
          <span v-if="edu.selectedSubject" class="ctx-pill ctx-pill-accent">{{ edu.selectedSubject?.name }}</span>
        </div>
        <ThemeToggle />
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
import { Fold } from '@element-plus/icons-vue'
import ProfileDrawer from './ProfileDrawer.vue'
import ThemeToggle from './ThemeToggle.vue'
import AppSidebar, { type NavItem } from './AppSidebar.vue'

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
      { path: '/animations', label: '互动动画', icon: 'Monitor', perm: 'animation.view' },
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
.ctx-pill {
  @apply inline-flex items-center px-2.5 py-0.5 rounded-full text-xs;
  background: var(--pill-bg);
  color: var(--ink-secondary);
}
.ctx-pill-ink {
  background: var(--pill-bg-ink);
  color: var(--ink);
  font-weight: 600;
}
.ctx-pill-accent {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary-dark-2);
  font-weight: 600;
}
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>

<style>
.mobile-nav-drawer .el-drawer__body {
  padding: 0 !important;
  overflow: hidden;
  background: var(--sidebar-bg) !important;
}
.mobile-nav-drawer.el-drawer {
  background: var(--sidebar-bg);
}
</style>
