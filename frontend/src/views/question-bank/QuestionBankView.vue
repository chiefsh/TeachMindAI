<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4 sm:mb-6">
      <div>
        <h1 class="page-title">题库管理</h1>
        <p class="page-subtitle">管理题目，支持文件批量导入和图片 OCR 识别</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <el-button :icon="Tickets" @click="openImports">导入记录</el-button>
        <el-button :icon="Upload" @click="openImport">导入题库</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">手动录入</el-button>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="card mb-4 flex flex-wrap items-center gap-3 !py-3">
      <el-select v-model="filter.question_type" placeholder="题型" clearable size="small" style="width:100px">
        <el-option v-for="t in questionTypes" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>
      <el-select v-model="filter.difficulty" placeholder="难度" clearable size="small" style="width:90px">
        <el-option v-for="d in difficulties" :key="d.value" :label="d.label" :value="d.value" />
      </el-select>
      <el-input v-model="filter.keyword" placeholder="搜索题目" size="small" clearable style="width:160px" />
      <el-button size="small" type="primary" @click="load">查询</el-button>
      <el-button
        v-if="selected.length"
        size="small" type="danger"
        @click="batchDelete"
      >删除所选（{{ selected.length }}）</el-button>
      <span class="text-xs text-slate-400 ml-auto">共 {{ total }} 道</span>
    </div>

    <!-- 题目列表 -->
    <div class="card !p-0 overflow-hidden">
      <div class="table-scroll">
      <el-table
        :data="questions" v-loading="loading" row-key="id"
        row-class-name="hover:bg-slate-50"
        @selection-change="onSelect"
      >
        <el-table-column type="selection" width="42" align="center" />
        <el-table-column type="index" width="55" align="center" />
        <el-table-column label="题干" min-width="280">
          <template #default="{ row }">
            <p class="text-sm line-clamp-2 cursor-pointer hover:text-primary-600" @click="openDetail(row)">
              {{ row.content }}
            </p>
            <el-tag v-if="hasImages(row)" size="small" type="warning" class="mt-1">含图</el-tag>
            <el-tag v-if="row.has_diagram || row.analysis_content" size="small" class="mt-1 ml-1">
              {{ row.has_diagram ? '含图解' : '已解析' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="年级" width="90">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ edu.gradeName(row.grade_id) || '—' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="科目" width="90">
          <template #default="{ row }">
            <el-tag size="small" type="success">{{ edu.subjectName(row.subject_id) || '—' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="题型" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTag(row.question_type)">{{ typeLabel(row.question_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="难度" width="80">
          <template #default="{ row }">
            <span :class="`text-xs font-medium ${diffColor(row.difficulty)}`">{{ diffLabel(row.difficulty) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="使用次数" width="90" align="center">
          <template #default="{ row }">
            <span class="text-xs text-slate-600">{{ row.use_count ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="错次" width="80" align="center">
          <template #default="{ row }">
            <span class="text-xs" :class="(row.wrong_count ?? 0) ? 'text-red-500 font-medium' : 'text-slate-400'">
              {{ row.wrong_count ?? 0 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openDetail(row)">查看</el-button>
            <el-button size="small" link type="primary" @click="openDetail(row, true)">编辑</el-button>
            <el-popconfirm title="确定删除该题目？" @confirm="deleteQ(row.id)">
              <template #reference>
                <el-button size="small" link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      </div>
      <div class="p-3 sm:p-4 flex justify-end overflow-x-auto">
        <el-pagination
          v-model:current-page="filter.page"
          :page-size="filter.page_size"
          :total="total"
          layout="prev, pager, next"
          @current-change="load"
        />
      </div>
    </div>

    <!-- 手动录入弹窗 -->
    <el-dialog v-model="showCreate" title="手动录入题目" width="720px" :close-on-click-modal="false" top="6vh">
      <div class="flex flex-wrap items-center gap-3 mb-3">
        <el-select v-model="createForm.grade_id" placeholder="年级" size="small" style="width:110px" @change="createForm.subject_id = edu.defaultSubjectId(createForm.grade_id)">
          <el-option v-for="g in edu.filteredGrades" :key="g.id" :label="g.name" :value="g.id" />
        </el-select>
        <el-select v-model="createForm.subject_id" placeholder="科目" size="small" style="width:110px" :disabled="!createForm.grade_id">
          <el-option v-for="s in edu.subjectsOfGrade(createForm.grade_id)" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-switch v-model="createForm.use_ai" active-text="AI 智能识别" inactive-text="纯文本拆分" size="small" />
      </div>

      <RichEditor
        ref="editorRef"
        v-model="createForm.html"
        @update:text="(t: string) => createForm.text = t"
        placeholder="在此输入或粘贴题目，可一次录入一道或多道题。例如：&#10;1. 下列哪个是质数？ A.4 B.6 C.7 D.9  答案：C&#10;2. 计算 3+5= ____  答案：8"
      />
      <p class="text-xs text-slate-400 mt-2">
        开启「AI 智能识别」后，系统会自动拆分多道题，并识别题型、选项与答案；关闭则按题号拆分为简答题。
      </p>

      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :icon="MagicStick" :loading="creating" @click="handleCreate">
          {{ createForm.use_ai ? '智能识别并保存' : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 导入弹窗 -->
    <el-dialog v-model="showImport" title="导入题库" width="460px">
      <el-form :model="importForm" label-width="80px" class="mb-2">
        <el-form-item label="年级">
          <el-select v-model="importForm.grade_id" placeholder="选择年级" style="width:100%" @change="importForm.subject_id = edu.defaultSubjectId(importForm.grade_id)">
            <el-option v-for="g in edu.filteredGrades" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="科目">
          <el-select
            v-model="importForm.subject_id"
            :placeholder="importForm.grade_id ? '选择科目' : '请先选择年级'"
            :disabled="!importForm.grade_id"
            style="width:100%"
          >
            <el-option v-for="s in edu.subjectsOfGrade(importForm.grade_id)" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <el-upload :auto-upload="false" :limit="1" accept=".pdf,.doc,.docx,.txt,.epub,.mobi,.jpg,.jpeg,.png"
            :on-change="(f: any) => importForm.file = f.raw">
            <el-button>选择文件</el-button>
            <template #tip>
              <p class="text-xs text-slate-400 mt-1">支持 PDF/Word/TXT 及图片；题干或选项里的配图会一并导入</p>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showImport = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="handleImport">导入</el-button>
      </template>
    </el-dialog>

    <!-- 导入记录 -->
    <el-dialog v-model="showImports" title="导入记录" width="720px" @open="loadImports">
      <el-table :data="importRows" v-loading="importsLoading" empty-text="暂无导入记录">
        <el-table-column label="文件" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.file_name }}</template>
        </el-table-column>
        <el-table-column label="年级/科目" width="140">
          <template #default="{ row }">
            {{ edu.gradeName(row.grade_id) || '—' }} / {{ edu.subjectName(row.subject_id) || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="importStatusType(row.parse_status)" :title="row.parse_error || ''">
              {{ importStatusLabel(row.parse_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="题数" width="70" align="center">
          <template #default="{ row }">{{ row.parse_status === 'done' ? row.question_count : '—' }}</template>
        </el-table-column>
        <el-table-column label="导入时间" width="150">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <p v-if="importRows.some((r) => r.parse_status === 'failed' && r.parse_error)" class="text-xs text-slate-400 mt-2">
        失败记录把鼠标移到状态上可查看原因。
      </p>
      <div v-if="importTotal > 10" class="mt-3 flex justify-end">
        <el-pagination
          v-model:current-page="importPage"
          :page-size="10"
          :total="importTotal"
          layout="prev, pager, next"
          @current-change="loadImports"
        />
      </div>
    </el-dialog>

    <!-- 题目详情 / 编辑弹窗 -->
    <el-dialog
      v-model="showDetail"
      :title="editing ? '编辑题目' : '题目详情'"
      width="800px"
      :close-on-click-modal="!editing"
      @closed="onDetailClosed"
    >
      <div v-if="detail && editing" class="space-y-4">
        <div class="flex flex-wrap items-center gap-2">
          <el-select v-model="editForm.grade_id" placeholder="年级" size="small" style="width:110px" @change="editForm.subject_id = edu.defaultSubjectId(editForm.grade_id)">
            <el-option v-for="g in edu.filteredGrades" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
          <el-select v-model="editForm.subject_id" placeholder="科目" size="small" style="width:110px" :disabled="!editForm.grade_id">
            <el-option v-for="s in edu.subjectsOfGrade(editForm.grade_id)" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
          <el-select v-model="editForm.question_type" placeholder="题型" size="small" style="width:110px" @change="onEditTypeChange">
            <el-option v-for="t in questionTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
          <el-select v-model="editForm.difficulty" placeholder="难度" size="small" style="width:100px">
            <el-option v-for="d in difficulties" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
        </div>

        <div>
          <p class="text-xs font-semibold text-slate-500 mb-1">题干</p>
          <el-input v-model="editForm.content" type="textarea" :rows="4" placeholder="题目内容" />
          <div v-if="detail.images?.stem?.length" class="mt-2 flex flex-wrap gap-2">
            <img
              v-for="(src, i) in detail.images.stem" :key="i"
              :src="src" alt="题干配图"
              class="q-img"
            />
          </div>
        </div>

        <div v-if="isChoiceType(editForm.question_type)">
          <div class="flex items-center justify-between mb-1">
            <p class="text-xs font-semibold text-slate-500">选项</p>
            <el-button size="small" link type="primary" @click="addEditOption">添加选项</el-button>
          </div>
          <div v-for="(opt, i) in editForm.options" :key="i" class="flex items-start gap-2 mb-2">
            <el-input v-model="opt.key" size="small" style="width:56px" placeholder="A" />
            <el-input v-model="opt.text" type="textarea" :rows="1" placeholder="选项内容" />
            <el-button size="small" link type="danger" :disabled="editForm.options.length <= 2" @click="editForm.options.splice(i, 1)">删</el-button>
          </div>
          <div v-if="hasOptionImages(detail)" class="mt-1 text-xs text-slate-400">选项配图会保留，仅修改文字。</div>
        </div>

        <div>
          <p class="text-xs font-semibold text-slate-500 mb-1">答案</p>
          <el-input v-model="editForm.answer" type="textarea" :rows="2" placeholder="正确答案，可留空" />
        </div>

        <div>
          <p class="text-xs font-semibold text-slate-500 mb-1">解析</p>
          <el-input v-model="editForm.explanation" type="textarea" :rows="3" placeholder="解析说明，可留空" />
        </div>

        <div>
          <p class="text-xs font-semibold text-slate-500 mb-1">知识点标签</p>
          <el-input v-model="editForm.tagsText" size="small" placeholder="多个标签用逗号分隔" />
        </div>
      </div>

      <div v-else-if="detail" class="space-y-4">
        <div class="flex flex-wrap items-center gap-1.5">
          <el-tag size="small" type="info">{{ edu.gradeName(detail.grade_id) || '—' }}</el-tag>
          <el-tag size="small" type="success">{{ edu.subjectName(detail.subject_id) || '—' }}</el-tag>
          <el-tag size="small" :type="typeTag(detail.question_type)">{{ typeLabel(detail.question_type) }}</el-tag>
          <span :class="`text-xs font-medium ${diffColor(detail.difficulty)}`">{{ diffLabel(detail.difficulty) }}</span>
          <span class="text-xs text-slate-500">作业/试卷使用 {{ detail.use_count ?? 0 }} 次</span>
        </div>

        <div>
          <p class="text-xs font-semibold text-slate-500 mb-1">题干</p>
          <div class="text-sm text-slate-800 math-text" v-html="renderMathText(detail.content)" />
          <div v-if="detail.images?.stem?.length" class="mt-2 flex flex-wrap gap-2">
            <img
              v-for="(src, i) in detail.images.stem" :key="i"
              :src="src" alt="题干配图"
              class="q-img"
            />
          </div>
        </div>

        <div v-if="optionKeys(detail).length">
          <p class="text-xs font-semibold text-slate-500 mb-1">选项</p>
          <div :class="hasOptionImages(detail) ? 'grid grid-cols-1 sm:grid-cols-2 gap-2' : 'space-y-1'">
            <div
              v-for="k in optionKeys(detail)" :key="k"
              class="text-sm text-slate-700 min-w-0"
              :class="hasOptionImages(detail) ? 'rounded-lg border border-slate-100 p-2 overflow-visible' : ''"
            >
              <p class="math-text">
                <span class="font-medium">{{ k }}. </span>
                <span v-html="renderMathText(String(detail.options?.[k] || ''))" />
              </p>
              <div v-if="detail.images?.options?.[k]" class="q-opt-frame mt-1.5">
                <img
                  :src="detail.images.options[k]"
                  :alt="`选项${k}`"
                  class="q-opt-img"
                />
              </div>
            </div>
          </div>
        </div>

        <div v-if="detail.answer">
          <p class="text-xs font-semibold text-slate-500 mb-1">答案</p>
          <div class="text-sm text-green-600 math-text" v-html="renderMathText(detail.answer)" />
        </div>
        <div v-else>
          <p class="text-xs font-semibold text-slate-500 mb-1">答案</p>
          <p class="text-sm text-slate-400">暂无答案</p>
        </div>

        <div v-if="detail.analysis_content || detail.analysis_html">
          <p class="text-xs font-semibold text-slate-500 mb-1">解析</p>
          <iframe
            v-if="detail.analysis_html && diagramBlob"
            :src="diagramBlob"
            class="w-full rounded-lg border border-slate-200 bg-white mb-3"
            style="height:360px" frameborder="0"
          />
          <div v-if="detail.analysis_content?.思路" class="mb-2 text-sm math-text">
            <span class="font-semibold text-indigo-600">思路：</span>
            <span v-html="renderMathText(detail.analysis_content.思路)" />
          </div>
          <div v-for="(st, i) in detail.analysis_content?.steps || []" :key="i" class="mb-2 text-sm math-text">
            <p class="font-medium">步骤{{ i + 1 }}{{ st.title ? '：' + st.title : '' }}</p>
            <p v-if="st.detail" class="text-slate-600" v-html="renderMathText(st.detail)" />
          </div>
          <div v-if="detail.analysis_content?.易错点" class="mb-2 text-sm math-text">
            <span class="font-semibold text-amber-600">易错点：</span>
            <span v-html="renderMathText(detail.analysis_content.易错点)" />
          </div>
          <div v-if="detail.analysis_content?.答案" class="text-sm math-text">
            <span class="font-semibold text-green-600">答案：</span>
            <span v-html="renderMathText(detail.analysis_content.答案)" />
          </div>
        </div>
        <div v-else-if="detail.explanation">
          <p class="text-xs font-semibold text-slate-500 mb-1">解析</p>
          <div class="text-sm text-slate-700 math-text" v-html="renderMathText(detail.explanation)" />
        </div>

        <div v-if="detail.tags?.length" class="flex flex-wrap gap-1.5">
          <el-tag v-for="t in detail.tags" :key="t" size="small">{{ t }}</el-tag>
        </div>
      </div>
      <template #footer>
        <template v-if="editing">
          <el-button @click="cancelEdit">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
        </template>
        <template v-else>
          <el-button @click="showDetail = false">关闭</el-button>
          <el-button type="primary" @click="startEdit">编辑</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { questionApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Plus, MagicStick, Tickets } from '@element-plus/icons-vue'
import type { Question, QuestionImport } from '@/types'
import RichEditor from '@/components/RichEditor.vue'
import { renderMathText } from '@/utils/mathText'
import { createIframeBlob } from '@/utils/coursewareFrame'
import { isBusyStatus, useBusyPoll } from '@/utils/busyPoll'
import dayjs from 'dayjs'

const edu = useEducationStore()
const questions = ref<Question[]>([])
const total = ref(0)
const loading = ref(false)
const showImport = ref(false)
const showImports = ref(false)
const showCreate = ref(false)
const showDetail = ref(false)
const detail = ref<Question | null>(null)
const editing = ref(false)
const saving = ref(false)
const pendingEdit = ref(false)
const diagramBlob = ref('')
const editForm = reactive({
  grade_id: null as number | null,
  subject_id: null as number | null,
  question_type: 'short_answer',
  difficulty: 'medium',
  content: '',
  answer: '',
  explanation: '',
  tagsText: '',
  options: [] as { key: string; text: string }[],
})
const importing = ref(false)
const creating = ref(false)
const selected = ref<Question[]>([])
const importRows = ref<QuestionImport[]>([])
const importTotal = ref(0)
const importPage = ref(1)
const importsLoading = ref(false)
const editorRef = ref<any>(null)
const filter = reactive({ question_type: null as any, difficulty: null as any, keyword: '', page: 1, page_size: 20 })
const importForm = reactive({ grade_id: null as any, subject_id: null as any, file: null as File | null })
const createForm = reactive({ grade_id: null as any, subject_id: null as any, use_ai: true, html: '', text: '' })

const questionTypes = [
  { value: 'single_choice', label: '单选题' }, { value: 'multi_choice', label: '多选题' },
  { value: 'fill_blank', label: '填空题' }, { value: 'short_answer', label: '简答题' },
  { value: 'essay', label: '作文' }, { value: 'true_false', label: '判断题' },
  { value: 'calculation', label: '计算题' },
]
const difficulties = [
  { value: 'easy', label: '简单' }, { value: 'medium', label: '中等' },
  { value: 'hard', label: '较难' }, { value: 'very_hard', label: '特难' },
]

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const res: any = await questionApi.list({
      ...filter,
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
    })
    questions.value = res.items
    total.value = res.total
    selected.value = []
  } finally { loading.value = false }
}

// 顶部全局年级/科目变化时回到第一页并刷新
watchDebounced(() => [edu.selectedGradeId, edu.selectedSubjectId], () => { filter.page = 1; load() }, { debounce: 250 })

function onSelect(rows: Question[]) {
  selected.value = rows
}

async function loadImports(silent = false) {
  if (!silent) importsLoading.value = true
  const hadBusy = importRows.value.some(r => isBusyStatus(r.parse_status))
  try {
    const res = await questionApi.listImports({ page: importPage.value, page_size: 10 })
    importRows.value = res.items || []
    importTotal.value = res.total || 0
    if (hadBusy && !importRows.value.some(r => isBusyStatus(r.parse_status))) {
      await load(true)
    }
  } finally {
    importsLoading.value = false
    importPoll.sync()
  }
}

const importPoll = useBusyPoll(
  () => loadImports(true),
  () => showImports.value && importRows.value.some(r => isBusyStatus(r.parse_status)),
)

function openImports() {
  importPage.value = 1
  showImports.value = true
}

function importStatusLabel(s: string) {
  return { pending: '排队中', processing: '导入中', done: '成功', failed: '失败' }[s] || s
}
function importStatusType(s: string): 'info' | 'warning' | 'success' | 'danger' {
  const map = { pending: 'info', processing: 'warning', done: 'success', failed: 'danger' } as const
  return map[s as keyof typeof map] || 'info'
}

watch(showImports, (open) => {
  if (!open) importPoll.stop()
})

function formatDate(d: string) {
  return d ? dayjs(d).format('YYYY-MM-DD HH:mm') : '—'
}

function hasImages(q: Question) {
  return !!(q.images?.stem?.length || (q.images?.options && Object.keys(q.images.options).length))
}
function hasOptionImages(q: Question) {
  return !!(q.images?.options && Object.keys(q.images.options).length)
}
function optionKeys(q: Question) {
  const keys = new Set([
    ...Object.keys(q.options || {}),
    ...Object.keys(q.images?.options || {}),
  ])
  return [...keys].sort()
}

function revokeDiagram() {
  if (diagramBlob.value) {
    URL.revokeObjectURL(diagramBlob.value)
    diagramBlob.value = ''
  }
}

const CHOICE_TYPES = new Set(['single_choice', 'multi_choice', 'true_false'])
const OPTION_LETTERS = 'ABCDEFGHIJ'

function isChoiceType(t: string) {
  return CHOICE_TYPES.has(t)
}

function fillEditForm(q: Question) {
  editForm.grade_id = q.grade_id
  editForm.subject_id = q.subject_id
  editForm.question_type = q.question_type
  editForm.difficulty = q.difficulty
  editForm.content = q.content || ''
  editForm.answer = q.answer || ''
  editForm.explanation = q.explanation || ''
  editForm.tagsText = (q.tags || []).join('，')
  const keys = optionKeys(q)
  editForm.options = keys.length
    ? keys.map(k => ({ key: k, text: String(q.options?.[k] || '') }))
    : isChoiceType(q.question_type)
      ? defaultOptions(q.question_type)
      : []
}

function defaultOptions(t: string) {
  if (t === 'true_false') return [{ key: 'A', text: '正确' }, { key: 'B', text: '错误' }]
  return ['A', 'B', 'C', 'D'].map(k => ({ key: k, text: '' }))
}

function onEditTypeChange(t: string) {
  if (!isChoiceType(t)) {
    editForm.options = []
    return
  }
  if (!editForm.options.length) editForm.options = defaultOptions(t)
}

function addEditOption() {
  const used = new Set(editForm.options.map(o => o.key))
  const next = [...OPTION_LETTERS].find(k => !used.has(k)) || String(editForm.options.length + 1)
  editForm.options.push({ key: next, text: '' })
}

function startEdit() {
  if (!detail.value) return
  fillEditForm(detail.value)
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  if (detail.value) fillEditForm(detail.value)
}

function editOptionsPayload() {
  const out: Record<string, string> = {}
  for (const o of editForm.options) {
    const k = (o.key || '').trim()
    if (k) out[k] = o.text || ''
  }
  return Object.keys(out).length ? out : null
}

async function saveEdit() {
  if (!detail.value) return
  if (!editForm.grade_id || !editForm.subject_id) { ElMessage.warning('请选择年级和科目'); return }
  if (!(editForm.content || '').trim()) { ElMessage.warning('请输入题目内容'); return }
  saving.value = true
  try {
    const updated = await questionApi.update(detail.value.id, {
      grade_id: editForm.grade_id,
      subject_id: editForm.subject_id,
      question_type: editForm.question_type,
      difficulty: editForm.difficulty,
      content: editForm.content,
      options: isChoiceType(editForm.question_type) ? editOptionsPayload() : null,
      answer: editForm.answer,
      explanation: editForm.explanation,
      tags: editForm.tagsText
        ? editForm.tagsText.split(/[,，;；、]/).map(s => s.trim()).filter(Boolean)
        : [],
    })
    detail.value = updated
    const idx = questions.value.findIndex(q => q.id === updated.id)
    if (idx >= 0) questions.value[idx] = { ...questions.value[idx], ...updated }
    editing.value = false
    ElMessage.success('已保存')
  } finally {
    saving.value = false
  }
}

async function openDetail(row: Question, edit = false) {
  revokeDiagram()
  detail.value = row
  editing.value = false
  pendingEdit.value = edit
  if (edit) fillEditForm(row)
  showDetail.value = true
  try {
    const full = await questionApi.get(row.id)
    detail.value = full
    if (full.analysis_html) {
      diagramBlob.value = createIframeBlob(full.analysis_html)
    }
    if (pendingEdit.value) {
      fillEditForm(full)
      editing.value = true
    }
  } catch {
    if (pendingEdit.value) editing.value = true
  }
}

function onDetailClosed() {
  revokeDiagram()
  detail.value = null
  editing.value = false
  pendingEdit.value = false
}

function openCreate() {
  createForm.grade_id = edu.selectedGradeId || null
  createForm.subject_id = edu.selectedSubjectId || null
  showCreate.value = true
}

function openImport() {
  importForm.grade_id = edu.selectedGradeId || null
  importForm.subject_id = edu.selectedSubjectId || null
  showImport.value = true
}

async function handleImport() {
  if (!importForm.file) { ElMessage.warning('请选择文件'); return }
  const fd = new FormData()
  fd.append('file', importForm.file)
  fd.append('subject_id', String(importForm.subject_id))
  fd.append('grade_id', String(importForm.grade_id))
  importing.value = true
  try {
    await questionApi.importFile(fd)
    ElMessage.success('导入任务已提交，正在后台处理')
    showImport.value = false
    importPage.value = 1
    showImports.value = true
    await load()
  } finally { importing.value = false }
}

async function handleCreate() {
  const text = (createForm.text || editorRef.value?.getText() || '').trim()
  if (!createForm.grade_id || !createForm.subject_id) { ElMessage.warning('请选择年级和科目'); return }
  if (!text) { ElMessage.warning('请输入题目内容'); return }
  creating.value = true
  try {
    const res: any = await questionApi.manual({
      text,
      subject_id: createForm.subject_id,
      grade_id: createForm.grade_id,
      use_ai: createForm.use_ai,
    })
    const created = res.created ?? res.count ?? 0
    const skipped = res.skipped ?? 0
    ElMessage.success(
      skipped
        ? `已录入 ${created} 道，跳过 ${skipped} 道重复题`
        : `已录入 ${created} 道题目`,
    )
    showCreate.value = false
    createForm.html = ''
    createForm.text = ''
    editorRef.value?.clear()
    await load()
  } finally { creating.value = false }
}

async function deleteQ(id: number) {
  await questionApi.delete(id)
  ElMessage.success('已删除')
  await load()
}

async function batchDelete() {
  const ids = selected.value.map(q => q.id)
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${ids.length} 道题目？`, '批量删除', { type: 'warning' })
  } catch {
    return
  }
  const res = await questionApi.batchDelete(ids)
  ElMessage.success(`已删除 ${res.count} 道题目`)
  await load()
}

function typeLabel(t: string) {
  return { single_choice: '单选', multi_choice: '多选', fill_blank: '填空', short_answer: '简答', essay: '作文', true_false: '判断', calculation: '计算' }[t] || t
}
function typeTag(t: string): any {
  return { single_choice: '', multi_choice: 'warning', fill_blank: 'success', short_answer: 'info' }[t] || ''
}
function diffLabel(d: string) {
  return { easy: '简单', medium: '中等', hard: '较难', very_hard: '特难' }[d] || d
}
function diffColor(d: string) {
  return { easy: 'text-green-600', medium: 'text-blue-600', hard: 'text-orange-600', very_hard: 'text-red-600' }[d] || ''
}

onMounted(load)
onBeforeUnmount(revokeDiagram)
</script>

<style scoped>
.math-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
}
.math-text :deep(.katex) {
  font-size: 1.02em;
  white-space: normal;
}
.q-img {
  @apply max-h-40 max-w-full rounded-md border border-slate-100 object-contain bg-slate-50;
}
.q-opt-frame {
  width: 100%;
  max-width: 220px;
  min-width: 0;
  overflow: visible;
}
.q-opt-img {
  display: block;
  width: 100%;
  height: auto;
  max-height: 7.5rem;
  object-fit: contain;
  object-position: left center;
  border-radius: 0.375rem;
  border: 1px solid #f1f5f9;
  background: #f8fafc;
}
</style>
