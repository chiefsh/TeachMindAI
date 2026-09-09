<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4 sm:mb-6">
      <div>
        <h1 class="page-title">班级 / 学生</h1>
        <p class="page-subtitle">先建班级，再录入花名册。批改作业、试卷会按班级对应到每个学生</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <el-button v-if="auth.can('classroom.manage')" :icon="Plus" @click="openClass">新建班级</el-button>
        <el-button v-if="auth.can('classroom.manage')" type="primary" :icon="UserFilled" :disabled="!current" @click="openStudent">添加学生</el-button>
      </div>
    </div>

    <p v-if="!edu.selectedGradeId" class="card text-sm text-slate-500">
      请先在顶部选择年级，再管理该年级的班级。
    </p>

    <div v-else class="grid lg:grid-cols-5 gap-4 items-start">
      <div class="lg:col-span-2 card !p-0 overflow-hidden">
        <div class="px-4 py-3 border-b border-slate-100 text-sm font-medium text-slate-700">
          {{ edu.gradeName(edu.selectedGradeId) }} · 班级
        </div>
        <div v-if="!classes.length && !loadingClass" class="px-4 py-8 text-center text-sm text-slate-400">
          还没有班级，请先新建。
        </div>
        <button
          v-for="c in classes"
          :key="c.id"
          type="button"
          class="w-full text-left px-4 py-3 border-b border-slate-50 hover:bg-slate-50"
          :class="current?.id === c.id ? 'bg-primary-50' : ''"
          @click="selectClass(c)"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="text-sm font-medium text-slate-800">{{ c.name }}</span>
            <span class="text-xs text-slate-400">{{ c.student_count }} 人</span>
          </div>
        </button>
      </div>

      <div class="lg:col-span-3 card !p-0 overflow-hidden">
        <div class="px-4 py-3 border-b border-slate-100 flex items-center justify-between gap-2">
          <p class="text-sm font-medium text-slate-700">
            {{ current ? `${current.name} · 花名册` : '请选择班级' }}
          </p>
          <div v-if="current && auth.can('classroom.manage')" class="flex gap-1">
            <el-button size="small" link @click="openBatch">批量录入</el-button>
            <el-button size="small" link @click="renameClass">改名</el-button>
            <el-popconfirm title="确定删除该班级？" @confirm="removeClass">
              <template #reference>
                <el-button size="small" link type="danger">删除班级</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
        <div class="table-scroll">
          <el-table :data="students" v-loading="loadingStu" max-height="560">
            <el-table-column label="学号" width="120">
              <template #default="{ row }"><span class="text-sm">{{ row.student_no }}</span></template>
            </el-table-column>
            <el-table-column label="姓名" min-width="100">
              <template #default="{ row }"><span class="text-sm">{{ row.name }}</span></template>
            </el-table-column>
            <el-table-column v-if="auth.can('classroom.manage')" label="" width="120" align="center">
              <template #default="{ row }">
                <el-button size="small" link @click="editStudent(row)">编辑</el-button>
                <el-popconfirm title="删除该学生？" @confirm="removeStudent(row.id)">
                  <template #reference>
                    <el-button size="small" link type="danger">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <p v-if="current && !loadingStu && !students.length" class="text-center text-xs text-slate-400 py-6">
          该班还没有学生。可单个添加，或按「学号 姓名」批量粘贴。
        </p>
      </div>
    </div>

    <el-dialog v-model="showClass" title="新建班级" width="400px">
      <el-input v-model="className" placeholder="如：1班、实验班" maxlength="32" />
      <template #footer>
        <el-button @click="showClass = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveClass">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showStudent" :title="editingStudent ? '编辑学生' : '添加学生'" width="420px">
      <el-form label-width="70px">
        <el-form-item label="学号">
          <el-input v-model="stuForm.student_no" placeholder="学号" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="stuForm.name" placeholder="姓名" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showStudent = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveStudent">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showBatch" title="批量录入花名册" width="480px">
      <p class="text-xs text-slate-500 mb-2">每行一个学生，学号与姓名用空格、逗号或 Tab 分隔。例如：</p>
      <pre class="text-xs text-slate-400 mb-2">202401 张三
202402,李四</pre>
      <el-input v-model="batchText" type="textarea" :rows="10" placeholder="粘贴名单" />
      <template #footer>
        <el-button @click="showBatch = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveBatch">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { Plus, UserFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { classApi, studentApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { useAuthStore } from '@/stores/auth'
import type { SchoolClass, Student } from '@/types'

const edu = useEducationStore()
const auth = useAuthStore()
const classes = ref<SchoolClass[]>([])
const current = ref<SchoolClass | null>(null)
const students = ref<Student[]>([])
const loadingClass = ref(false)
const loadingStu = ref(false)
const saving = ref(false)
const showClass = ref(false)
const showStudent = ref(false)
const showBatch = ref(false)
const className = ref('')
const batchText = ref('')
const editingStudent = ref<Student | null>(null)
const stuForm = reactive({ student_no: '', name: '' })

async function loadClasses() {
  if (!edu.selectedGradeId) {
    classes.value = []
    current.value = null
    students.value = []
    return
  }
  loadingClass.value = true
  try {
    classes.value = await classApi.list({ grade_id: edu.selectedGradeId })
    if (current.value) {
      const hit = classes.value.find(c => c.id === current.value!.id)
      current.value = hit || classes.value[0] || null
    } else {
      current.value = classes.value[0] || null
    }
    await loadStudents()
  } finally {
    loadingClass.value = false
  }
}

async function loadStudents() {
  if (!current.value) {
    students.value = []
    return
  }
  loadingStu.value = true
  try {
    students.value = await classApi.students(current.value.id)
  } finally {
    loadingStu.value = false
  }
}

function selectClass(c: SchoolClass) {
  current.value = c
  loadStudents()
}

function openClass() {
  if (!edu.selectedGradeId) {
    ElMessage.warning('请先在顶部选择年级')
    return
  }
  className.value = ''
  showClass.value = true
}

async function saveClass() {
  if (!className.value.trim() || !edu.selectedGradeId) return
  saving.value = true
  try {
    const row = await classApi.create({ grade_id: edu.selectedGradeId, name: className.value.trim() })
    showClass.value = false
    await loadClasses()
    current.value = classes.value.find(c => c.id === row.id) || row
    await loadStudents()
    ElMessage.success('已创建班级')
  } finally {
    saving.value = false
  }
}

async function renameClass() {
  if (!current.value) return
  const { value } = await ElMessageBox.prompt('班级名称', '改名', {
    inputValue: current.value.name,
    inputPattern: /\S+/,
    inputErrorMessage: '请填写名称',
  })
  await classApi.update(current.value.id, { name: String(value).trim() })
  ElMessage.success('已改名')
  await loadClasses()
}

async function removeClass() {
  if (!current.value) return
  await classApi.delete(current.value.id)
  current.value = null
  ElMessage.success('已删除')
  await loadClasses()
}

function openStudent() {
  editingStudent.value = null
  stuForm.student_no = ''
  stuForm.name = ''
  showStudent.value = true
}

function editStudent(row: Student) {
  editingStudent.value = row
  stuForm.student_no = row.student_no
  stuForm.name = row.name
  showStudent.value = true
}

async function saveStudent() {
  if (!current.value) return
  if (!stuForm.student_no.trim() || !stuForm.name.trim()) {
    ElMessage.warning('请填写学号和姓名')
    return
  }
  saving.value = true
  try {
    if (editingStudent.value) {
      await studentApi.update(editingStudent.value.id, {
        student_no: stuForm.student_no.trim(),
        name: stuForm.name.trim(),
      })
    } else {
      await classApi.addStudent(current.value.id, {
        student_no: stuForm.student_no.trim(),
        name: stuForm.name.trim(),
        grade_id: current.value.grade_id,
      })
    }
    showStudent.value = false
    await loadClasses()
    ElMessage.success('已保存')
  } finally {
    saving.value = false
  }
}

async function removeStudent(id: number) {
  await studentApi.delete(id)
  ElMessage.success('已删除')
  await loadClasses()
}

function openBatch() {
  batchText.value = ''
  showBatch.value = true
}

function parseBatch(text: string) {
  const rows: { student_no: string; name: string }[] = []
  for (const line of text.split(/\r?\n/)) {
    const t = line.trim()
    if (!t) continue
    const parts = t.split(/[,，\t;；\s]+/).filter(Boolean)
    if (parts.length === 1) rows.push({ student_no: parts[0], name: parts[0] })
    else rows.push({ student_no: parts[0], name: parts.slice(1).join('') })
  }
  return rows
}

async function saveBatch() {
  if (!current.value) return
  const rows = parseBatch(batchText.value)
  if (!rows.length) {
    ElMessage.warning('没有有效行')
    return
  }
  saving.value = true
  try {
    const r = await classApi.batchStudents(current.value.id, rows)
    showBatch.value = false
    await loadClasses()
    ElMessage.success(`新增 ${r.created} 人，跳过 ${r.skipped} 人`)
  } finally {
    saving.value = false
  }
}

watchDebounced(() => edu.selectedGradeId, () => loadClasses(), { debounce: 200 })
onMounted(loadClasses)
</script>
