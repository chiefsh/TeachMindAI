<template>
  <div class="page">
    <div class="mb-7 flex flex-wrap items-end justify-between gap-3">
      <div>
        <p class="dash-date">{{ todayLabel }}</p>
        <h1 class="page-title">{{ greet }}，{{ auth.teacher?.real_name }} 老师</h1>
        <p class="page-subtitle">从这里开始今天的备课与批改</p>
      </div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4 mb-6">
      <template v-if="statsLoading">
        <div v-for="n in 5" :key="n" class="card !p-4 sm:!p-5">
          <div class="skeleton h-3 w-12 mb-3" />
          <div class="skeleton h-7 w-16" />
        </div>
      </template>
      <div
        v-else
        v-for="stat in stats"
        :key="stat.label"
        class="card !p-4 sm:!p-5 relative overflow-hidden dash-stat"
      >
        <div class="dash-stat-bar" />
        <div class="flex items-start justify-between pl-2">
          <div>
            <p class="text-xs" style="color: var(--ink-muted)">{{ stat.label }}</p>
            <p class="dash-stat-value">{{ stat.value }}</p>
          </div>
          <div class="dash-stat-icon">
            <el-icon class="text-lg"><component :is="stat.icon" /></el-icon>
          </div>
        </div>
      </div>
    </div>

    <div class="card mb-6">
      <h2 class="text-sm font-semibold mb-4" style="color: var(--ink)">快捷操作</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
        <router-link
          v-for="action in quickActions"
          :key="action.label"
          :to="action.path"
          class="quick-item"
        >
          <div class="quick-icon">
            <el-icon class="text-lg"><component :is="action.icon" /></el-icon>
          </div>
          <div class="min-w-0">
            <p class="text-sm font-medium" style="color: var(--ink)">{{ action.label }}</p>
            <p class="text-[11px] mt-0.5 truncate" style="color: var(--ink-muted)">{{ action.hint }}</p>
          </div>
        </router-link>
      </div>
    </div>

    <div class="card">
      <h2 class="text-sm font-semibold mb-4" style="color: var(--ink)">我的教学科目</h2>
      <div v-if="edu.mySubjects.length" class="flex flex-wrap gap-2">
        <div
          v-for="ts in edu.mySubjects"
          :key="ts.id"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg"
          style="background: var(--pill-bg); border: 1px solid var(--border-subtle)"
        >
          <span class="text-xs" style="color: var(--ink-muted)">{{ ts.grade.name }}</span>
          <span class="text-xs" style="color: var(--border)">/</span>
          <span class="text-sm font-medium" style="color: var(--ink)">{{ ts.subject.name }}</span>
        </div>
      </div>
      <div v-else class="empty-hint !py-6">
        暂未绑定教学范围，由管理员在「用户管理」中设置。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useEducationStore } from '@/stores/education'
import { dashboardApi } from '@/api/modules'

const auth = useAuthStore()
const edu = useEducationStore()

const greet = computed(() => {
  const h = new Date().getHours()
  if (h < 5) return '夜深了'
  if (h < 12) return '上午好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const todayLabel = computed(() => {
  const d = new Date()
  const wk = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日 星期${wk}`
})

const statsLoading = ref(true)
const stats = ref([
  { key: 'textbook_count',   label: '课本数量',  value: '—' as string | number, icon: 'Collection' },
  { key: 'question_count',   label: '题库题目',  value: '—' as string | number, icon: 'EditPen' },
  { key: 'courseware_count', label: '已生成课件', value: '—' as string | number, icon: 'VideoPlay' },
  { key: 'student_count',    label: '学生人数',  value: '—' as string | number, icon: 'User' },
  { key: 'analysis_count',   label: '试题分析',  value: '—' as string | number, icon: 'DataAnalysis' },
])

onMounted(async () => {
  try {
    const res: any = await dashboardApi.getStats()
    stats.value.forEach(s => { s.value = res[s.key] ?? 0 })
  } catch { /* 忽略统计加载失败 */ }
  statsLoading.value = false
})

const quickActions = [
  { label: '上传课本', path: '/textbook',      icon: 'Collection',    hint: '导入教材与章节' },
  { label: '导入题库', path: '/question-bank', icon: 'EditPen',       hint: '沉淀可复用题目' },
  { label: '生成课件', path: '/courseware',    icon: 'VideoPlay',     hint: '按课时生成演示文稿' },
  { label: '班级学生', path: '/students',      icon: 'User',          hint: '查看班级花名册' },
  { label: '布置作业', path: '/homework',      icon: 'Tickets',       hint: '组卷并布置到班级' },
  { label: '批改作业', path: '/grading',       icon: 'Finished',      hint: '原卷批改与回写' },
  { label: '试题分析', path: '/question-analysis', icon: 'DataAnalysis', hint: '拆解题面与考点' },
]
</script>

<style scoped>
.dash-date {
  font-size: 12px;
  letter-spacing: 0.04em;
  margin-bottom: 6px;
  color: var(--ink-muted);
}
.dash-stat {
  transition: transform 180ms cubic-bezier(0.16, 1, 0.3, 1), box-shadow 180ms ease;
}
.dash-stat:hover {
  transform: translateY(-2px);
}
.dash-stat-bar {
  position: absolute;
  left: 0;
  top: 16px;
  bottom: 16px;
  width: 2px;
  border-radius: 99px;
  background: var(--el-color-primary);
  opacity: 0.55;
}
.dash-stat-value {
  margin-top: 6px;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.04em;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  color: var(--ink);
}
.dash-stat-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.quick-item {
  @apply flex items-center gap-3 p-3 rounded-[10px];
  border: 1px solid var(--border-subtle);
  background: var(--muted-fill);
  transition: background 160ms ease, border-color 160ms ease, transform 160ms ease;
}
.quick-item:hover {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
  transform: translateY(-1px);
}
.quick-item:active {
  transform: scale(0.99);
}
.quick-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--surface);
  color: var(--el-color-primary);
  border: 1px solid var(--border-subtle);
}
</style>
