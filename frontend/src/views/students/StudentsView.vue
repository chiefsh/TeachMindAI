<template>
  <div class="page">
    <div class="mb-4 sm:mb-6">
      <h1 class="page-title">班级 / 学生</h1>
      <p class="page-subtitle">
        先选年级、再建班级，把花名册录进对应班。批改作业和试卷会按班级对到每个学生。
      </p>
    </div>

    <div v-if="!edu.selectedGradeId" class="card">
      <p class="text-sm font-medium" style="color: var(--ink)">请先选择年级</p>
      <p class="text-sm mt-1" style="color: var(--ink-muted)">点下方年级即可，之后顶栏也会跟着切换。</p>
      <div v-if="gradeOptions.length" class="flex flex-wrap gap-2 mt-4">
        <button
          v-for="g in gradeOptions"
          :key="g.id"
          type="button"
          class="grade-chip"
          @click="edu.selectGrade(g.id)"
        >
          {{ g.name }}
        </button>
      </div>
      <p v-else class="empty-hint !py-6 !text-left">当前没有可选年级，请先在顶部选择学段。</p>
    </div>

    <div v-else class="grid lg:grid-cols-5 gap-4 items-start">
      <!-- 手机：班级横滑切换 -->
      <div class="lg:hidden space-y-2">
        <div class="flex items-center justify-between gap-2">
          <p class="text-sm font-medium" style="color: var(--ink)">
            {{ edu.gradeName(edu.selectedGradeId) }} · {{ classes.length }} 个班
          </p>
          <el-button
            v-if="canManage"
            size="small"
            type="primary"
            :icon="Plus"
            @click="openClass()"
          >新建班级</el-button>
        </div>
        <div v-if="classes.length" class="flex gap-2 overflow-x-auto no-scrollbar pb-1">
          <button
            v-for="c in classes"
            :key="c.id"
            type="button"
            class="class-chip"
            :class="{ 'is-active': current?.id === c.id }"
            @click="selectClass(c)"
          >
            <span>{{ c.name }}</span>
            <span class="class-chip-count">{{ c.student_count }}</span>
          </button>
        </div>
        <p v-else-if="!loadingClass" class="text-sm" style="color: var(--ink-muted)">还没有班级。</p>
      </div>

      <!-- 桌面：班级列表 -->
      <div class="hidden lg:block lg:col-span-2 card !p-0 overflow-hidden" v-loading="loadingClass">
        <div class="px-4 py-3 border-b flex items-center justify-between gap-2" style="border-color: var(--border-subtle)">
          <div class="min-w-0">
            <p class="text-sm font-medium truncate" style="color: var(--ink)">
              {{ edu.gradeName(edu.selectedGradeId) }} · 班级
            </p>
            <p class="text-xs mt-0.5" style="color: var(--ink-muted)">
              {{ classes.length }} 个班 · {{ studentTotal }} 人
            </p>
          </div>
          <el-button
            v-if="canManage"
            size="small"
            type="primary"
            :icon="Plus"
            @click="openClass()"
          >新建</el-button>
        </div>
        <div v-if="!classes.length && !loadingClass" class="px-4 py-10 text-center">
          <p class="text-sm" style="color: var(--ink-muted)">这个年级还没有班级</p>
          <el-button v-if="canManage" class="mt-3" size="small" :icon="Plus" @click="openClass()">
            新建班级
          </el-button>
        </div>
        <div v-else class="class-list">
          <div
            v-for="c in classes"
            :key="c.id"
            class="class-row"
            :class="{ 'is-active': current?.id === c.id }"
            @click="selectClass(c)"
          >
            <div class="min-w-0">
              <p class="text-sm font-medium truncate" style="color: var(--ink)">{{ c.name }}</p>
              <p class="text-xs mt-0.5 tabular-nums" style="color: var(--ink-muted)">{{ c.student_count }} 人</p>
            </div>
            <div v-if="canManage" @click.stop>
              <el-dropdown
                trigger="click"
                placement="bottom-end"
                @command="(cmd: string) => onClassCommand(c, cmd)"
              >
                <el-button size="small" link :icon="MoreFilled" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="rename" :icon="EditPen">改名</el-dropdown-item>
                    <el-dropdown-item command="delete" :icon="Delete" divided>删除班级</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </div>
      </div>

      <!-- 花名册 -->
      <div class="lg:col-span-3 card !p-0 overflow-hidden">
        <div class="px-4 py-3 border-b space-y-3" style="border-color: var(--border-subtle)">
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0 flex items-center gap-1">
              <p class="text-sm font-medium truncate" style="color: var(--ink)">
                {{ current ? `${current.name} · 花名册` : '请选择班级' }}
              </p>
              <el-dropdown
                v-if="canManage && current"
                class="lg:hidden"
                trigger="click"
                placement="bottom-end"
                @command="(cmd: string) => current && onClassCommand(current, cmd)"
              >
                <el-button size="small" link :icon="MoreFilled" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="rename" :icon="EditPen">改名</el-dropdown-item>
                    <el-dropdown-item command="delete" :icon="Delete" divided>删除班级</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
            <el-button
              v-if="canManage && current"
              type="primary"
              size="small"
              :icon="Upload"
              @click="openBatch"
            >批量录入</el-button>
          </div>
          <div v-if="current" class="flex flex-wrap items-center gap-2">
            <el-input
              v-model="keyword"
              size="small"
              clearable
              placeholder="搜索学号 / 姓名"
              class="!max-w-xs"
              :prefix-icon="Search"
            />
            <span class="text-xs tabular-nums" style="color: var(--ink-muted)">
              {{ keyword.trim() ? `${filteredStudents.length} / ${students.length} 人` : `${students.length} 人` }}
            </span>
          </div>
        </div>

        <div v-if="!current" class="empty-hint">请在左侧选择一个班级</div>

        <template v-else>
          <div v-if="canManage" class="quick-add">
            <el-input
              ref="addNoRef"
              v-model="stuForm.student_no"
              size="small"
              placeholder="学号"
              maxlength="32"
              @keydown.enter.prevent="focusAddName"
            />
            <el-input
              ref="addNameRef"
              v-model="stuForm.name"
              size="small"
              placeholder="姓名"
              maxlength="32"
              @keydown.enter.prevent="addStudentInline"
            />
            <el-button
              type="primary"
              size="small"
              :loading="saving === 'add'"
              @click="addStudentInline"
            >添加</el-button>
          </div>

          <div v-if="loadingStu || students.length" class="table-scroll">
            <el-table :data="filteredStudents" v-loading="loadingStu" max-height="520">
              <el-table-column type="index" label="#" width="52" align="center" />
              <el-table-column label="学号" min-width="120">
                <template #default="{ row }">
                  <el-input
                    v-if="editingId === row.id"
                    v-model="editForm.student_no"
                    size="small"
                    maxlength="32"
                    @keydown.enter.prevent="saveEdit"
                    @keydown.esc.prevent="cancelEdit"
                  />
                  <span v-else class="text-sm tabular-nums">{{ row.student_no }}</span>
                </template>
              </el-table-column>
              <el-table-column label="姓名" min-width="110">
                <template #default="{ row }">
                  <el-input
                    v-if="editingId === row.id"
                    v-model="editForm.name"
                    size="small"
                    maxlength="32"
                    @keydown.enter.prevent="saveEdit"
                    @keydown.esc.prevent="cancelEdit"
                  />
                  <span v-else class="text-sm">{{ row.name }}</span>
                </template>
              </el-table-column>
              <el-table-column v-if="canManage" label="" width="132" align="right">
                <template #default="{ row }">
                  <template v-if="editingId === row.id">
                    <el-button size="small" link type="primary" :loading="saving === 'edit'" @click="saveEdit">保存</el-button>
                    <el-button size="small" link @click="cancelEdit">取消</el-button>
                  </template>
                  <template v-else>
                    <el-button size="small" link @click="startEdit(row)">编辑</el-button>
                    <el-popconfirm title="删除该学生？" @confirm="removeStudent(row.id)">
                      <template #reference>
                        <el-button size="small" link type="danger">删除</el-button>
                      </template>
                    </el-popconfirm>
                  </template>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div v-if="!loadingStu && !students.length" class="px-4 py-8 text-center">
            <p class="text-sm" style="color: var(--ink-muted)">这个班还没有学生</p>
            <p v-if="canManage" class="text-xs mt-1" style="color: var(--ink-muted)">
              上面直接填学号姓名回车添加，或粘贴整份名单。
            </p>
            <el-button v-if="canManage" class="mt-3" size="small" :icon="Upload" @click="openBatch">
              粘贴名单
            </el-button>
          </div>
          <p
            v-else-if="!loadingStu && keyword.trim() && !filteredStudents.length"
            class="text-center text-xs py-6"
            style="color: var(--ink-muted)"
          >
            没有匹配「{{ keyword.trim() }}」的学生
          </p>
        </template>
      </div>
    </div>

    <el-dialog
      v-model="showClass"
      :title="editingClass ? '班级改名' : '新建班级'"
      width="400px"
      @opened="focusClassInput"
    >
      <el-input
        ref="classInputRef"
        v-model="className"
        placeholder="如：1班、实验班"
        maxlength="32"
        @keydown.enter.prevent="saveClass"
      />
      <template #footer>
        <el-button @click="showClass = false">取消</el-button>
        <el-button type="primary" :loading="saving === 'class'" @click="saveClass">
          {{ editingClass ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showBatch" title="批量录入花名册" width="520px">
      <p class="text-xs mb-2" style="color: var(--ink-muted)">
        每行一个学生，学号与姓名用空格、逗号或 Tab 分隔。粘贴后会显示可导入人数。
      </p>
      <pre class="batch-example">202401 张三
202402,李四
202403	王五</pre>
      <el-input v-model="batchText" type="textarea" :rows="10" placeholder="从 Excel 或文档粘贴名单" />
      <p v-if="batchRows.length" class="text-xs mt-2 tabular-nums" style="color: var(--ink-secondary)">
        识别到 {{ batchRows.length }} 人，已存在的学号会自动跳过。
      </p>
      <template #footer>
        <el-button @click="showBatch = false">取消</el-button>
        <el-button type="primary" :loading="saving === 'batch'" :disabled="!batchRows.length" @click="saveBatch">
          导入{{ batchRows.length ? ` ${batchRows.length} 人` : '' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { Plus, MoreFilled, EditPen, Delete, Upload, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { InputInstance } from 'element-plus'
import { classApi, studentApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { useAuthStore } from '@/stores/auth'
import type { SchoolClass, Student } from '@/types'

const edu = useEducationStore()
const auth = useAuthStore()
const canManage = computed(() => auth.can('classroom.manage'))
const gradeOptions = computed(() => edu.filteredGrades)
const classes = ref<SchoolClass[]>([])
const current = ref<SchoolClass | null>(null)
const students = ref<Student[]>([])
const loadingClass = ref(false)
const loadingStu = ref(false)
const saving = ref<'class' | 'add' | 'edit' | 'batch' | ''>('')
const showClass = ref(false)
const showBatch = ref(false)
const className = ref('')
const batchText = ref('')
const keyword = ref('')
const editingClass = ref<SchoolClass | null>(null)
const editingId = ref<number | null>(null)
const stuForm = reactive({ student_no: '', name: '' })
const editForm = reactive({ student_no: '', name: '' })
const addNoRef = ref<InputInstance>()
const addNameRef = ref<InputInstance>()
const classInputRef = ref<InputInstance>()

const studentTotal = computed(() => classes.value.reduce((n, c) => n + (c.student_count || 0), 0))
const filteredStudents = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return students.value
  return students.value.filter(
    s => s.name.toLowerCase().includes(q) || s.student_no.toLowerCase().includes(q),
  )
})
const batchRows = computed(() => parseBatch(batchText.value))

function bumpCount(classId: number, delta: number) {
  const hit = classes.value.find(c => c.id === classId)
  if (hit) hit.student_count = Math.max(0, (hit.student_count || 0) + delta)
  if (current.value?.id === classId) {
    current.value.student_count = Math.max(0, (current.value.student_count || 0) + delta)
  }
}

function sortStudents() {
  students.value.sort((a, b) => a.student_no.localeCompare(b.student_no, 'zh-CN', { numeric: true }))
}

async function loadClasses() {
  keyword.value = ''
  editingId.value = null
  if (current.value && current.value.grade_id !== edu.selectedGradeId) {
    current.value = null
    students.value = []
  }
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
  if (current.value?.id === c.id) return
  current.value = c
  keyword.value = ''
  editingId.value = null
  loadStudents()
}

function openClass(row?: SchoolClass) {
  if (!edu.selectedGradeId) {
    ElMessage.warning('请先选择年级')
    return
  }
  editingClass.value = row || null
  className.value = row?.name || ''
  showClass.value = true
}

function focusClassInput() {
  classInputRef.value?.focus()
}

async function saveClass() {
  const name = className.value.trim()
  if (!name || !edu.selectedGradeId) return
  saving.value = 'class'
  try {
    if (editingClass.value) {
      const row = await classApi.update(editingClass.value.id, { name })
      const hit = classes.value.find(c => c.id === row.id)
      if (hit) hit.name = row.name
      if (current.value?.id === row.id) current.value.name = row.name
      ElMessage.success('已改名')
    } else {
      const row = await classApi.create({ grade_id: edu.selectedGradeId, name })
      classes.value = [...classes.value, { ...row, student_count: row.student_count || 0 }]
      current.value = classes.value.find(c => c.id === row.id) || row
      students.value = []
      keyword.value = ''
      ElMessage.success('已创建班级，可以直接录学生')
      await nextTick()
      addNoRef.value?.focus()
    }
    showClass.value = false
  } finally {
    saving.value = ''
  }
}

async function onClassCommand(c: SchoolClass, cmd: string) {
  if (cmd === 'rename') {
    openClass(c)
    return
  }
  if (cmd !== 'delete') return
  try {
    await ElMessageBox.confirm(
      `删除「${c.name}」及该班花名册？此操作不可恢复。`,
      '删除班级',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  await classApi.delete(c.id)
  if (current.value?.id === c.id) current.value = null
  ElMessage.success('已删除')
  await loadClasses()
}

function focusAddName() {
  addNameRef.value?.focus()
}

async function addStudentInline() {
  if (!current.value || !canManage.value) return
  const student_no = stuForm.student_no.trim()
  const name = stuForm.name.trim()
  if (!student_no || !name) {
    ElMessage.warning('请填写学号和姓名')
    return
  }
  saving.value = 'add'
  try {
    const row = await classApi.addStudent(current.value.id, {
      student_no,
      name,
      grade_id: current.value.grade_id,
    })
    students.value = [...students.value, row]
    sortStudents()
    bumpCount(current.value.id, 1)
    stuForm.student_no = ''
    stuForm.name = ''
    await nextTick()
    addNoRef.value?.focus()
  } finally {
    saving.value = ''
  }
}

function startEdit(row: Student) {
  editingId.value = row.id
  editForm.student_no = row.student_no
  editForm.name = row.name
}

function cancelEdit() {
  editingId.value = null
}

async function saveEdit() {
  if (!editingId.value) return
  const student_no = editForm.student_no.trim()
  const name = editForm.name.trim()
  if (!student_no || !name) {
    ElMessage.warning('请填写学号和姓名')
    return
  }
  saving.value = 'edit'
  try {
    await studentApi.update(editingId.value, { student_no, name })
    const hit = students.value.find(s => s.id === editingId.value)
    if (hit) {
      hit.student_no = student_no
      hit.name = name
    }
    sortStudents()
    editingId.value = null
    ElMessage.success('已保存')
  } finally {
    saving.value = ''
  }
}

async function removeStudent(id: number) {
  await studentApi.delete(id)
  students.value = students.value.filter(s => s.id !== id)
  if (current.value) bumpCount(current.value.id, -1)
  if (editingId.value === id) editingId.value = null
  ElMessage.success('已删除')
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
  const rows = batchRows.value
  if (!rows.length) {
    ElMessage.warning('没有有效行')
    return
  }
  saving.value = 'batch'
  try {
    const r = await classApi.batchStudents(current.value.id, rows)
    showBatch.value = false
    await loadClasses()
    ElMessage.success(`新增 ${r.created} 人，跳过 ${r.skipped} 人`)
  } finally {
    saving.value = ''
  }
}

watchDebounced(() => edu.selectedGradeId, () => loadClasses(), { debounce: 200 })
onMounted(loadClasses)
</script>

<style scoped>
.grade-chip,
.class-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
  background: var(--surface);
  color: var(--ink);
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  transition: background 160ms ease, border-color 160ms ease;
}
.grade-chip:hover,
.class-chip:hover {
  background: var(--hover);
}
.class-chip.is-active,
.grade-chip:focus-visible {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary-dark-2);
}
.class-chip-count {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: var(--ink-muted);
}
.class-chip.is-active .class-chip-count {
  color: var(--el-color-primary);
}
.class-list {
  max-height: min(70vh, 640px);
  overflow-y: auto;
}
.class-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-subtle);
  transition: background 160ms ease;
}
.class-row:hover {
  background: var(--hover);
}
.class-row.is-active {
  background: var(--el-color-primary-light-9);
}
.quick-add {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--muted-fill);
}
.batch-example {
  font-size: 12px;
  line-height: 1.6;
  margin: 0 0 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--muted-fill);
  color: var(--ink-muted);
}
.table-scroll :deep(.el-table) {
  min-width: 0;
}
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
@media (max-width: 639px) {
  .quick-add {
    grid-template-columns: 1fr;
  }
}
</style>
