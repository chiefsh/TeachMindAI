<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4 sm:mb-6">
      <div>
        <h1 class="page-title">批改作业 / 试卷</h1>
        <p class="page-subtitle">纸质原卷拍照上传，按学生看图手批，并统计错题</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <el-button @click="$router.push('/wrong-questions')">错题本</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建布置</el-button>
      </div>
    </div>

    <div class="card !p-0 overflow-hidden">
      <div class="table-scroll">
        <el-table :data="rows" v-loading="loading">
          <el-table-column label="标题" min-width="180">
            <template #default="{ row }">
              <p class="text-sm font-medium text-slate-800">{{ row.title }}</p>
              <p class="text-xs text-slate-400 mt-0.5">卷面：{{ row.paper_title }}</p>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="row.paper_type === 'exam' ? 'danger' : 'primary'">
                {{ row.paper_type === 'exam' ? '考试' : '作业' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="班级" width="110">
            <template #default="{ row }">
              <span class="text-xs text-slate-600">{{ row.class_name || '全年级' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="日期" width="110">
            <template #default="{ row }">
              <span class="text-xs text-slate-500">{{ row.assigned_at }}</span>
            </template>
          </el-table-column>
          <el-table-column label="进度" min-width="140">
            <template #default="{ row }">
              <p class="text-xs text-slate-600">
                已交 {{ row.submitted_count }} / {{ row.student_count }}
                · 已批 {{ row.graded_count }}
              </p>
              <span :class="`badge badge-${row.status === 'done' ? 'done' : row.status === 'grading' ? 'processing' : 'pending'}`">
                {{ statusLabel(row.status) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <el-button size="small" link type="primary" @click="$router.push(`/grading/${row.id}`)">批改</el-button>
              <el-popconfirm title="删除本次布置及全部原卷图？" @confirm="remove(row.id)">
                <template #reference>
                  <el-button size="small" link type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <p v-if="!loading && !rows.length" class="text-center text-sm text-slate-400 py-10">
        还没有布置。请先在「作业/考试」组卷并打印，再在这里按班级收卷批改。
      </p>
    </div>

    <el-dialog v-model="showCreate" title="布置一次作业/考试" width="560px" :close-on-click-modal="false">
      <el-form :model="form" label-width="90px">
        <el-form-item label="卷面" required>
          <el-select v-model="form.paper_id" filterable placeholder="选择已生成的作业/试卷" style="width:100%" @change="onPaper">
            <el-option
              v-for="p in papers"
              :key="p.id"
              :label="`${p.title}（${p.paper_type === 'exam' ? '考试' : '作业'}）`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" placeholder="默认同卷面标题" />
        </el-form-item>
        <el-form-item label="年级" required>
          <el-select v-model="form.grade_id" placeholder="年级" style="width:100%" @change="onGradeChange">
            <el-option v-for="g in edu.filteredGrades" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="科目" required>
          <el-select v-model="form.subject_id" placeholder="科目" style="width:100%">
            <el-option v-for="s in edu.subjectsOfGrade(form.grade_id)" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="班级" required>
          <el-select v-model="form.class_id" placeholder="选择班级" style="width:100%">
            <el-option v-for="c in classes" :key="c.id" :label="`${c.name}（${c.student_count} 人）`" :value="c.id" />
          </el-select>
          <p class="text-xs text-slate-400 mt-1">
            没有班级？
            <router-link to="/students" class="text-primary-600">先去录入班级和学生</router-link>
          </p>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="form.assigned_at" value-format="YYYY-MM-DD" type="date" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="create">布置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { gradingApi, homeworkApi, classApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import type { GradingAssignment, HomeworkPaper, SchoolClass } from '@/types'

const edu = useEducationStore()
const route = useRoute()
const router = useRouter()
const rows = ref<GradingAssignment[]>([])
const papers = ref<HomeworkPaper[]>([])
const classes = ref<SchoolClass[]>([])
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)

const form = reactive({
  paper_id: null as number | null,
  title: '',
  grade_id: 0,
  subject_id: 0,
  class_id: null as number | null,
  assigned_at: dayjs().format('YYYY-MM-DD'),
})

function statusLabel(s: string) {
  return { collecting: '待收卷', grading: '批改中', done: '已完成' }[s] || s
}

async function load() {
  loading.value = true
  try {
    rows.value = await gradingApi.listAssignments({
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
    })
  } finally {
    loading.value = false
  }
}

async function loadPapers() {
  const list = await homeworkApi.list({
    grade_id: edu.selectedGradeId || undefined,
    subject_id: edu.selectedSubjectId || undefined,
  })
  papers.value = (list || []).filter(p => p.gen_status === 'done')
}

async function loadClasses() {
  if (!form.grade_id) {
    classes.value = []
    return
  }
  classes.value = await classApi.list({ grade_id: form.grade_id })
}

function onPaper(id: number) {
  const p = papers.value.find(x => x.id === id)
  if (!p) return
  form.title = p.title
  if (p.grade_id) form.grade_id = p.grade_id
  if (p.subject_id) form.subject_id = p.subject_id
  form.class_id = null
  loadClasses()
}

function onGradeChange() {
  form.class_id = null
  loadClasses()
}

function openCreate() {
  form.paper_id = null
  form.title = ''
  form.grade_id = edu.selectedGradeId || 0
  form.subject_id = edu.selectedSubjectId || 0
  form.class_id = null
  form.assigned_at = dayjs().format('YYYY-MM-DD')
  showCreate.value = true
  loadPapers()
  loadClasses()
}

async function create() {
  if (!form.paper_id) {
    ElMessage.warning('请选择卷面')
    return
  }
  if (!form.grade_id || !form.subject_id) {
    ElMessage.warning('请选择年级和科目')
    return
  }
  if (!form.class_id) {
    ElMessage.warning('请选择班级（请先在「班级/学生」中建班并录入花名册）')
    return
  }
  creating.value = true
  try {
    const row = await gradingApi.createAssignment({
      paper_id: form.paper_id,
      grade_id: form.grade_id,
      subject_id: form.subject_id,
      class_id: form.class_id,
      title: form.title || null,
      assigned_at: form.assigned_at,
    })
    ElMessage.success('已布置')
    showCreate.value = false
    await load()
    router.push(`/grading/${row.id}`)
  } finally {
    creating.value = false
  }
}

async function remove(id: number) {
  await gradingApi.deleteAssignment(id)
  ElMessage.success('已删除')
  await load()
}

watchDebounced(
  () => [edu.selectedGradeId, edu.selectedSubjectId],
  () => load(),
  { debounce: 250 },
)

onMounted(async () => {
  await load()
  const pid = Number(route.query.paper_id)
  if (pid) {
    await loadPapers()
    openCreate()
    form.paper_id = pid
    onPaper(pid)
  }
})
</script>
