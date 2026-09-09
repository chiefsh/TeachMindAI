<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4 sm:mb-6">
      <div>
        <h1 class="page-title">作业 / 考试生成</h1>
        <p class="page-subtitle">按课件、课本或章节组卷；可从题库筛选或 AI 出题，知识点不超出所选范围</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">生成作业/试卷</el-button>
    </div>

    <!-- 列表 -->
    <div class="card !p-0 overflow-hidden">
      <div class="table-scroll">
      <el-table :data="papers" v-loading="loading">
        <el-table-column label="标题" min-width="200">
          <template #default="{ row }">
            <p class="text-sm font-medium text-slate-800">{{ row.title }}</p>
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
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.paper_type === 'exam' ? 'danger' : 'primary'">
              {{ row.paper_type === 'exam' ? '考试' : '作业' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="范围" width="100">
          <template #default="{ row }">
            <span class="text-xs text-slate-500">{{ sourceLabel(row.source_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="难度" width="90">
          <template #default="{ row }">
            <span :class="diffColor(paperDiffKey(row))">{{ paperDiffLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span :class="`badge badge-${row.gen_status}`">{{ statusLabel(row.gen_status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="120">
          <template #default="{ row }">
            <span class="text-xs text-slate-400">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" align="center">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="viewDetail(row)">查看</el-button>
            <el-button
              v-if="canRegenerate(row)"
              size="small" link type="primary"
              @click="openRegenerate(row)"
            >重新生成</el-button>
            <el-button
              v-if="row.gen_status === 'done'"
              size="small" link type="success"
              @click="$router.push({ path: '/grading', query: { paper_id: row.id } })"
            >批改</el-button>
            <el-popconfirm title="确定删除？" @confirm="deletePaper(row.id)">
              <template #reference>
                <el-button size="small" link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      </div>
    </div>

    <!-- 生成 / 重新生成弹窗 -->
    <el-dialog v-model="showCreate" :title="regenId ? '重新生成作业/试卷' : '生成作业/试卷'" width="720px" :close-on-click-modal="false">
      <p v-if="regenId" class="text-xs text-amber-600 mb-3 -mt-1">
        将按下方配置重新组卷，替换当前题目；若已布置批改，对应作答记录会清空。
      </p>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="如：第一单元课后作业" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.paper_type">
            <el-radio value="homework">课后作业</el-radio>
            <el-radio value="exam">考试试卷</el-radio>
          </el-radio-group>
          <p v-if="form.paper_type === 'homework'" class="text-xs text-slate-400 mt-1">作业不设分值；考试由系统按题型赋分</p>
        </el-form-item>
        <el-form-item label="出题范围">
          <el-radio-group v-model="form.source_type" @change="onSourceTypeChange">
            <el-radio-button value="courseware">关联课件</el-radio-button>
            <el-radio-button value="textbook">整本课本</el-radio-button>
            <el-radio-button value="chapters">指定章节</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.source_type === 'courseware'" label="课件" prop="courseware_ids">
          <el-select v-model="form.courseware_ids" multiple placeholder="选择课件（可多选）" style="width:100%">
            <el-option v-for="cw in doneCourseware" :key="cw.id" :label="cw.title" :value="cw.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.source_type !== 'courseware'" label="课本" prop="textbook_id">
          <el-select
            v-model="form.textbook_id"
            placeholder="选择已解析的课本"
            style="width:100%"
            @change="onTextbookChange"
          >
            <el-option v-for="tb in doneTextbooks" :key="tb.id" :label="tb.title" :value="tb.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.source_type === 'chapters'" label="章节">
          <div class="w-full max-h-52 overflow-y-auto rounded-lg border border-slate-100 p-2">
            <el-tree
              v-if="chapters.length"
              ref="chapterTreeRef"
              :data="chapters"
              show-checkbox
              node-key="id"
              :props="{ label: 'title', children: 'children' }"
              :expand-on-click-node="false"
              @check="onChapterCheck"
            />
            <p v-else class="text-xs text-slate-400 py-4 text-center">请先选择课本</p>
          </div>
        </el-form-item>
        <el-form-item label="难度">
          <el-radio-group v-model="form.difficulty_mode" class="mb-2">
            <el-radio-button value="overall">总体等级</el-radio-button>
            <el-radio-button value="per_type">分题型占比</el-radio-button>
          </el-radio-group>
          <div v-if="form.difficulty_mode === 'overall'" class="w-full">
            <el-radio-group v-model="form.difficulty">
              <el-radio-button v-for="d in difficulties" :key="d.value" :value="d.value">{{ d.label }}</el-radio-button>
            </el-radio-group>
          </div>
          <p v-else class="text-xs text-slate-400">每种题型单独设置简单/中等/较难/特难的比例，按比例分配到该题型题量</p>
        </el-form-item>
        <el-form-item label="题目配置">
          <div class="w-full space-y-2">
            <p class="text-xs text-slate-400">拖动手柄调整题型顺序，即卷面大题顺序</p>
            <div
              v-for="(row, i) in form.type_rows"
              :key="row.type"
              class="rounded-lg border px-2 py-2 transition-colors"
              :class="dragOverIndex === i ? 'border-primary-400 bg-primary-50' : 'border-slate-100'"
              @dragover.prevent="onTypeDragOver(i)"
              @drop.prevent="onTypeDrop(i)"
              @dragleave="onTypeDragLeave(i)"
            >
              <div class="flex items-center gap-2">
                <span
                  class="cursor-grab text-slate-400 hover:text-slate-600 px-0.5"
                  draggable="true"
                  title="拖动排序"
                  @dragstart="onTypeDragStart(i, $event)"
                  @dragend="onTypeDragEnd"
                >
                  <el-icon><Rank /></el-icon>
                </span>
                <span class="text-sm text-slate-700 w-16 flex-shrink-0">{{ typeLabel(row.type) }}</span>
                <el-input-number v-model="row.count" :min="0" :max="20" size="small" style="width:110px" />
                <span class="text-xs text-slate-400">道</span>
              </div>
              <div v-if="form.difficulty_mode === 'per_type' && row.count > 0" class="mt-2 ml-7 flex flex-wrap items-center gap-x-3 gap-y-1">
                <label v-for="d in difficulties" :key="d.value" class="flex items-center gap-1 text-xs text-slate-500">
                  {{ d.label }}
                  <el-input-number v-model="row.ratios[d.value]" :min="0" :max="100" size="small" style="width:88px" />
                  <span>%</span>
                </label>
                <span class="text-xs" :class="ratioSum(row) ? 'text-slate-400' : 'text-amber-500'">
                  {{ ratioSum(row) ? `按 ${ratioSum(row)}% 比例分配` : '未填则按总体中等' }}
                </span>
              </div>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="题目来源">
          <el-radio-group v-model="form.question_source">
            <el-radio value="ai">AI 生成</el-radio>
            <el-radio value="bank">题库筛选</el-radio>
            <el-radio value="mixed">题库优先，不足补 AI</el-radio>
          </el-radio-group>
          <p class="text-xs text-slate-400 mt-1">题库按范围内知识点匹配；不够的题型会用 AI 补齐，仍不超出所选范围</p>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :icon="MagicStick" :loading="creating" @click="handleCreate">
          {{ regenId ? '重新生成' : '开始生成' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 查看详情 -->
    <el-dialog v-model="showDetail" :title="detailPaper?.title" width="820px" top="5vh">
      <template #header>
        <div class="flex items-center justify-between pr-6">
          <span class="font-semibold text-slate-800">{{ detailPaper?.title }}</span>
          <div class="flex items-center gap-3">
            <el-checkbox
              v-if="detailPaper?.gen_status === 'done' && questions.length"
              v-model="includeAnswers"
              size="small"
            >包括参考答案</el-checkbox>
            <el-button-group>
              <el-button
                v-if="detailPaper && canRegenerate(detailPaper)"
                size="small"
                @click="openRegenerate(detailPaper)"
              >重新生成</el-button>
              <template v-if="detailPaper?.gen_status === 'done' && questions.length">
                <el-button size="small" :icon="Printer" @click="openPrint">打印</el-button>
                <el-button size="small" :loading="exporting === 'docx'" :icon="Document" @click="doExport('docx')">导出 Word</el-button>
                <el-button size="small" :loading="exporting === 'pdf'" :icon="Tickets" @click="doExport('pdf')">导出 PDF</el-button>
                <el-button size="small" type="success" @click="goGrade">去批改</el-button>
              </template>
            </el-button-group>
          </div>
        </div>
      </template>

      <!-- Word 文档样式 -->
      <div v-if="detailPaper?.gen_status === 'done' && questions.length"
           class="max-h-[72vh] overflow-y-auto bg-slate-100 p-6">
        <div class="paper-doc bg-white mx-auto px-12 py-10 shadow-sm" style="max-width:720px">
          <h2 class="text-center text-xl font-bold text-slate-900">{{ detailPaper?.title }}</h2>
          <p class="text-center text-sm text-slate-500 mt-2">
            <template v-if="detailPaper?.grade_id || detailPaper?.subject_id">
              {{ [edu.gradeName(detailPaper?.grade_id), edu.subjectName(detailPaper?.subject_id)].filter(Boolean).join(' · ') }}
              　·　
            </template>
            {{ detailPaper?.paper_type === 'exam' ? '考试试卷' : '课后作业' }}
            　·　共 {{ questions.length }} 题
            <template v-if="isExam">　·　满分 {{ totalScore }} 分</template>
          </p>
          <p class="text-center text-sm text-slate-500 mt-1">
            姓名：____________　班级：____________　得分：____________
          </p>
          <div class="border-b border-slate-200 my-5"></div>

          <div class="space-y-5">
            <template v-for="(group, gi) in questionGroups" :key="gi">
              <p v-if="group.title" class="font-bold text-slate-800 pt-1">{{ group.title }}</p>
              <div v-for="q in group.questions" :key="q.id">
              <p class="text-slate-800 leading-relaxed">
                <span class="font-medium">{{ q._no }}.</span> {{ q.content }}
                <span v-if="isExam && q.score" class="text-xs text-slate-400">（{{ q.score }} 分）</span>
                <el-tag v-if="q.source" size="small" class="ml-2" :type="q.source === 'bank' ? 'success' : 'info'">
                  {{ q.source === 'bank' ? '题库' : 'AI' }}
                </el-tag>
              </p>
              <div v-if="q.options" class="mt-2 ml-5 space-y-1">
                <p v-for="(val, key) in q.options" :key="key" class="text-slate-700 text-sm">
                  {{ key }}. {{ val }}
                </p>
              </div>
              <p v-else class="mt-2 ml-5 text-slate-400 text-sm">答：</p>
            </div>
            </template>
          </div>

          <!-- 参考答案：默认不展示，勾选后才出现（与导出/打印一致） -->
          <div v-if="includeAnswers" class="mt-8 pt-5 border-t border-dashed border-slate-300">
            <p class="font-bold text-slate-800 mb-3">参考答案</p>
            <div class="space-y-1.5">
              <p v-for="(q, i) in questions" :key="q.id" class="text-sm text-slate-700">
                <span class="font-medium">{{ i + 1 }}.</span> {{ q.answer || '—' }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- 兼容旧数据：无结构化题目时展示原始内容 -->
      <div v-else-if="detailPaper?.gen_status === 'done'" class="max-h-[60vh] overflow-y-auto">
        <pre class="text-sm text-slate-700 whitespace-pre-wrap">{{ detailPaper.content }}</pre>
      </div>

      <div v-else-if="detailPaper?.gen_status === 'processing' || detailPaper?.gen_status === 'pending'" class="text-center py-10">
        <el-icon class="text-4xl text-primary-500 animate-spin"><Loading /></el-icon>
        <p class="mt-3 text-slate-500">正在组卷，请稍候...</p>
      </div>
      <div v-else-if="detailPaper?.gen_status === 'failed'" class="text-center py-10 text-slate-500">
        生成失败，请调整配置后重新生成
        <p v-if="detailPaper.content" class="text-xs text-slate-400 mt-2">{{ detailPaper.content }}</p>
        <el-button class="mt-4" type="primary" @click="openRegenerate(detailPaper)">重新生成</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, nextTick, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { homeworkApi, coursewareApi, textbookApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, MagicStick, Loading, Document, Tickets, Rank, Printer } from '@element-plus/icons-vue'
import type { HomeworkPaper, HomeworkQuestion, Courseware, Textbook, Chapter, HomeworkSourceType, QuestionSourceMode } from '@/types'
import { isBusyStatus, useBusyPoll } from '@/utils/busyPoll'
import dayjs from 'dayjs'

const edu = useEducationStore()
const router = useRouter()
const papers = ref<HomeworkPaper[]>([])
const coursewares = ref<Courseware[]>([])
const textbooks = ref<Textbook[]>([])
const chapters = ref<Chapter[]>([])
const doneCourseware = computed(() => coursewares.value.filter(c => c.gen_status === 'done'))
const doneTextbooks = computed(() => textbooks.value.filter(t => t.parse_status === 'done'))
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const regenId = ref<number | null>(null)
const showDetail = ref(false)
const detailPaper = ref<HomeworkPaper | null>(null)
const exporting = ref<string>('')
const includeAnswers = ref(false)
const formRef = ref()
const chapterTreeRef = ref()

type DiffKey = 'easy' | 'medium' | 'hard' | 'very_hard'
type TypeRow = { type: string; count: number; ratios: Record<DiffKey, number> }

const TYPE_ORDER = ['single_choice', 'fill_blank', 'short_answer', 'true_false']
const TYPE_LABELS: Record<string, string> = {
  single_choice: '单选题', multi_choice: '多选题', fill_blank: '填空题',
  true_false: '判断题', short_answer: '简答题', essay: '作文', calculation: '计算题',
}
const CN_SEC = '一二三四五六七八九十'

function defaultRatios(d: string): Record<DiffKey, number> {
  return { easy: 0, medium: 0, hard: 0, very_hard: 0, [d as DiffKey]: 100 } as Record<DiffKey, number>
}

function defaultTypeRows(): TypeRow[] {
  return [
    { type: 'single_choice', count: 5, ratios: defaultRatios('medium') },
    { type: 'fill_blank', count: 3, ratios: defaultRatios('medium') },
    { type: 'short_answer', count: 2, ratios: defaultRatios('medium') },
    { type: 'true_false', count: 0, ratios: defaultRatios('medium') },
  ]
}

const questions = computed<HomeworkQuestion[]>(() => detailPaper.value?.questions || [])
const isExam = computed(() => detailPaper.value?.paper_type === 'exam')
const totalScore = computed(() => questions.value.reduce((s, q) => s + (q.score || 0), 0))
const questionGroups = computed(() => {
  const groups: { type: string; title: string; questions: (HomeworkQuestion & { _no: number })[] }[] = []
  let no = 0
  for (const q of questions.value) {
    const t = q.question_type || ''
    no += 1
    const last = groups[groups.length - 1]
    if (!last || last.type !== t) {
      const gi = groups.length
      const label = TYPE_LABELS[t]
      const title = label ? `${CN_SEC[gi] || gi + 1}、${label}` : ''
      groups.push({ type: t, title, questions: [{ ...q, _no: no }] })
    } else {
      last.questions.push({ ...q, _no: no })
    }
  }
  return groups
})

const form = reactive({
  title: '',
  paper_type: 'homework',
  source_type: 'courseware' as HomeworkSourceType,
  question_source: 'ai' as QuestionSourceMode,
  courseware_ids: [] as number[],
  textbook_id: null as number | null,
  chapter_ids: [] as number[],
  difficulty: 'medium',
  difficulty_mode: 'overall' as 'overall' | 'per_type',
  type_rows: defaultTypeRows(),
})
const dragFromIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)
const rules = {
  title: [{ required: true, message: '请填写标题' }],
}

const difficulties: { value: DiffKey; label: string }[] = [
  { value: 'easy', label: '简单' }, { value: 'medium', label: '中等' },
  { value: 'hard', label: '较难' }, { value: 'very_hard', label: '特难' },
]
function typeLabel(t: string) {
  return TYPE_LABELS[t] || t
}

function ratioSum(row: TypeRow) {
  return difficulties.reduce((s, d) => s + (Number(row.ratios[d.value as DiffKey]) || 0), 0)
}

function onTypeDragStart(i: number, e: DragEvent) {
  dragFromIndex.value = i
  e.dataTransfer?.setData('text/plain', String(i))
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}

function onTypeDragOver(i: number) {
  dragOverIndex.value = i
}

function onTypeDragLeave(i: number) {
  if (dragOverIndex.value === i) dragOverIndex.value = null
}

function onTypeDrop(i: number) {
  const from = dragFromIndex.value
  dragOverIndex.value = null
  dragFromIndex.value = null
  if (from == null || from === i) return
  const rows = form.type_rows
  const [moved] = rows.splice(from, 1)
  rows.splice(i, 0, moved)
}

function onTypeDragEnd() {
  dragFromIndex.value = null
  dragOverIndex.value = null
}

function buildQuestionConfig() {
  return {
    difficulty_mode: form.difficulty_mode,
    items: form.type_rows.map(r => ({
      type: r.type,
      count: r.count || 0,
      ratios: form.difficulty_mode === 'per_type' ? { ...r.ratios } : undefined,
    })),
  }
}

function applyQuestionConfig(cfg: any, difficulty: string) {
  form.difficulty_mode = cfg?.difficulty_mode === 'per_type' ? 'per_type' : 'overall'
  const fallback = defaultRatios(difficulty)
  const makeRow = (type: string, count: number, ratios?: Record<string, number>): TypeRow => ({
    type,
    count,
    ratios: {
      easy: Number(ratios?.easy) || 0,
      medium: Number(ratios?.medium) || 0,
      hard: Number(ratios?.hard) || 0,
      very_hard: Number(ratios?.very_hard) || 0,
    },
  })
  const rows: TypeRow[] = []
  const seen = new Set<string>()
  if (Array.isArray(cfg?.items)) {
    for (const it of cfg.items) {
      const t = String(it?.type || '')
      if (!t || seen.has(t)) continue
      seen.add(t)
      const row = makeRow(t, Number(it.count) || 0, it.ratios)
      if (!ratioSum(row)) row.ratios = { ...fallback }
      rows.push(row)
    }
  } else if (cfg && typeof cfg === 'object') {
    for (const [k, v] of Object.entries(cfg)) {
      if (k === 'difficulty_mode' || k === 'items' || seen.has(k)) continue
      seen.add(k)
      if (v && typeof v === 'object' && !Array.isArray(v)) {
        const obj = v as { count?: number; ratios?: Record<string, number> }
        const row = makeRow(k, Number(obj.count) || 0, obj.ratios)
        if (!ratioSum(row)) row.ratios = { ...fallback }
        rows.push(row)
      } else {
        rows.push(makeRow(k, Number(v) || 0, fallback))
      }
    }
  }
  for (const t of TYPE_ORDER) {
    if (!seen.has(t)) rows.push({ type: t, count: 0, ratios: { ...fallback } })
  }
  form.type_rows = rows.length ? rows : defaultTypeRows()
}

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    papers.value = (await homeworkApi.list({
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
    })) as any
  } finally {
    loading.value = false
    busyPoll.sync()
  }
}

const busyPoll = useBusyPoll(
  () => load(true),
  () => papers.value.some(p => isBusyStatus(p.gen_status)),
)

async function loadCoursewares() {
  const res = await coursewareApi.list({
    grade_id: edu.selectedGradeId || undefined,
    subject_id: edu.selectedSubjectId || undefined,
    page: 1, page_size: 500,
  }) as any
  coursewares.value = res.items || []
}

async function loadTextbooks() {
  const res = await textbookApi.list({
    grade_id: edu.selectedGradeId || undefined,
    subject_id: edu.selectedSubjectId || undefined,
    page: 1, page_size: 200,
  }) as any
  textbooks.value = res.items || []
}

async function loadChapters(textbookId: number) {
  chapters.value = (await textbookApi.getChapters(textbookId)) as any || []
}

function resetScopeFields() {
  form.courseware_ids = []
  form.textbook_id = null
  form.chapter_ids = []
  chapters.value = []
}

function resetForm() {
  regenId.value = null
  form.title = ''
  form.paper_type = 'homework'
  form.source_type = 'courseware'
  form.question_source = 'ai'
  form.difficulty = 'medium'
  form.difficulty_mode = 'overall'
  form.type_rows = defaultTypeRows()
  resetScopeFields()
}

function canRegenerate(row: HomeworkPaper) {
  return row.gen_status === 'done' || row.gen_status === 'failed'
}

function openCreate() {
  resetForm()
  showCreate.value = true
}

async function fillFormFromPaper(p: HomeworkPaper) {
  form.title = p.title
  form.paper_type = p.paper_type
  form.source_type = (p.source_type || 'courseware') as HomeworkSourceType
  form.question_source = (p.question_source || 'ai') as QuestionSourceMode
  form.difficulty = p.difficulty || 'medium'
  applyQuestionConfig(p.question_config, form.difficulty)
  form.courseware_ids = p.courseware_ids?.length
    ? [...p.courseware_ids]
    : (p.courseware_id ? [p.courseware_id] : [])
  form.textbook_id = p.textbook_id || null
  form.chapter_ids = [...(p.chapter_ids || [])]
  chapters.value = []
  if (form.source_type === 'chapters' && form.textbook_id) {
    await loadChapters(form.textbook_id)
  }
}

async function openRegenerate(paper: HomeworkPaper) {
  const full = (await homeworkApi.get(paper.id)) as HomeworkPaper
  regenId.value = full.id
  await fillFormFromPaper(full)
  showDetail.value = false
  showCreate.value = true
  await nextTick()
  if (form.source_type === 'chapters') {
    chapterTreeRef.value?.setCheckedKeys(form.chapter_ids)
  }
}

watch(showCreate, (open) => {
  if (!open) regenId.value = null
})

watch(() => form.difficulty, (d) => {
  if (form.difficulty_mode !== 'overall') return
  const ratios = defaultRatios(d)
  form.type_rows.forEach((r) => { r.ratios = { ...ratios } })
})

watch(() => form.difficulty_mode, (mode) => {
  if (mode !== 'per_type') return
  form.type_rows.forEach((r) => {
    if (!ratioSum(r)) r.ratios = defaultRatios(form.difficulty)
  })
})

function onSourceTypeChange() {
  form.courseware_ids = []
  form.textbook_id = null
  form.chapter_ids = []
  chapters.value = []
}

async function onTextbookChange(id: number | null) {
  form.chapter_ids = []
  chapters.value = []
  if (id && form.source_type === 'chapters') {
    await loadChapters(id)
    await nextTick()
    chapterTreeRef.value?.setCheckedKeys([])
  }
}

function onChapterCheck() {
  form.chapter_ids = chapterTreeRef.value?.getCheckedKeys(false) || []
}

watchDebounced(
  () => [edu.selectedGradeId, edu.selectedSubjectId],
  () => { load(); loadCoursewares(); loadTextbooks() },
  { debounce: 250 },
)

async function handleCreate() {
  await formRef.value?.validate()
  const totalQ = form.type_rows.reduce((s, r) => s + (r.count || 0), 0)
  if (!totalQ) {
    ElMessage.warning('请至少配置一道题')
    return
  }
  if (form.source_type === 'courseware' && !form.courseware_ids.length) {
    ElMessage.warning('请选择关联课件')
    return
  }
  if (form.source_type !== 'courseware' && !form.textbook_id) {
    ElMessage.warning('请选择课本')
    return
  }
  if (form.source_type === 'chapters') {
    form.chapter_ids = chapterTreeRef.value?.getCheckedKeys(false) || form.chapter_ids
    if (!form.chapter_ids.length) {
      ElMessage.warning('请选择章节')
      return
    }
  }
  creating.value = true
  try {
    const payload = {
      title: form.title,
      paper_type: form.paper_type,
      difficulty: form.difficulty,
      question_config: buildQuestionConfig(),
      source_type: form.source_type,
      question_source: form.question_source,
      courseware_ids: form.source_type === 'courseware' ? form.courseware_ids : [],
      textbook_id: form.source_type === 'courseware' ? undefined : form.textbook_id,
      chapter_ids: form.source_type === 'chapters' ? form.chapter_ids : [],
    }
    if (regenId.value) {
      await homeworkApi.regenerate(regenId.value, payload)
      ElMessage.success('已提交重新生成')
    } else {
      await homeworkApi.create(payload)
      ElMessage.success('生成任务已提交')
    }
    showCreate.value = false
    await load()
  } finally { creating.value = false }
}

async function viewDetail(paper: HomeworkPaper) {
  includeAnswers.value = false
  detailPaper.value = (await homeworkApi.get(paper.id)) as any
  showDetail.value = true
}

function goGrade() {
  if (!detailPaper.value) return
  showDetail.value = false
  router.push({ path: '/grading', query: { paper_id: detailPaper.value.id } })
}

function escHtml(s: string) {
  return (s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function buildPrintHtml() {
  const p = detailPaper.value
  if (!p) return ''
  const ctx = [edu.gradeName(p.grade_id), edu.subjectName(p.subject_id)].filter(Boolean).join(' · ')
  const kind = p.paper_type === 'exam' ? '考试试卷' : '课后作业'
  const scoreBit = isExam.value ? `　·　满分 ${totalScore.value} 分` : ''
  const meta = `${ctx ? `${escHtml(ctx)}　·　` : ''}${kind}　·　共 ${questions.value.length} 题${scoreBit}`
  const body = questionGroups.value.map((group) => {
    const head = group.title ? `<p class="sec">${escHtml(group.title)}</p>` : ''
    const qs = group.questions.map((q) => {
      const score = isExam.value && q.score ? `<span class="muted">（${q.score} 分）</span>` : ''
      let opts = ''
      if (q.options) {
        opts = Object.entries(q.options)
          .map(([k, v]) => `<p class="opt">${escHtml(k)}. ${escHtml(String(v))}</p>`)
          .join('')
      } else {
        opts = '<p class="opt muted">答：</p>'
      }
      return `<div class="q"><p><b>${q._no}.</b> ${escHtml(q.content || '')} ${score}</p>${opts}</div>`
    }).join('')
    return head + qs
  }).join('')
  const answers = includeAnswers.value
    ? `<div class="ans"><p class="sec">参考答案</p>${
        questions.value.map((q, i) => `<p>${i + 1}. ${escHtml(q.answer || '—')}</p>`).join('')
      }</div>`
    : ''
  return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>${escHtml(p.title)}</title>
<style>
  @page { size: A4; margin: 16mm; }
  body { font-family: "PingFang SC","Microsoft YaHei",sans-serif; color:#111; font-size:14px; line-height:1.7; margin:24px; }
  h1 { text-align:center; font-size:20px; margin:0 0 8px; }
  .meta { text-align:center; color:#555; font-size:13px; margin:0 0 4px; }
  .line { border-bottom:1px solid #ddd; margin:16px 0; }
  .sec { font-weight:700; margin:16px 0 8px; }
  .q { margin:0 0 14px; }
  .opt { margin:2px 0 0 22px; }
  .muted { color:#888; font-size:12px; }
  .ans { margin-top:28px; padding-top:16px; border-top:1px dashed #bbb; }
</style></head><body>
<h1>${escHtml(p.title)}</h1>
<p class="meta">${meta}</p>
<p class="meta">姓名：____________　班级：____________　得分：____________</p>
<div class="line"></div>
${body}
${answers}
</body></html>`
}

function openPrint() {
  if (!detailPaper.value || !questions.value.length) return
  const w = window.open('', '_blank')
  if (!w) {
    ElMessage.warning('浏览器拦截了弹窗，请允许后重试')
    return
  }
  w.document.open()
  w.document.write(buildPrintHtml())
  w.document.close()
  w.focus()
  const go = () => {
    w.print()
  }
  if (w.document.readyState === 'complete') {
    setTimeout(go, 50)
  } else {
    w.onload = go
    setTimeout(go, 300)
  }
}

async function doExport(fmt: 'docx' | 'pdf') {
  if (!detailPaper.value) return
  exporting.value = fmt
  try {
    const blob = (await homeworkApi.exportFile(
      detailPaper.value.id, fmt, includeAnswers.value,
    )) as unknown as Blob
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${detailPaper.value.title}.${fmt}`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('导出失败，请稍后重试')
  } finally {
    exporting.value = ''
  }
}

async function deletePaper(id: number) {
  await homeworkApi.delete(id)
  ElMessage.success('已删除')
  await load()
}

function statusLabel(s: string) {
  return { pending: '待生成', processing: '生成中', done: '已完成', failed: '失败' }[s] || s
}
function sourceLabel(s?: string) {
  return { courseware: '课件', textbook: '整本课本', chapters: '指定章节' }[s || ''] || '课件'
}
function diffLabel(d: string) {
  return { easy: '简单', medium: '中等', hard: '较难', very_hard: '特难' }[d] || d
}
function paperDiffKey(row: HomeworkPaper) {
  return row.question_config?.difficulty_mode === 'per_type' ? 'mixed' : row.difficulty
}
function paperDiffLabel(row: HomeworkPaper) {
  return row.question_config?.difficulty_mode === 'per_type' ? '分题型' : diffLabel(row.difficulty)
}
function diffColor(d: string) {
  return { easy: 'text-green-600', medium: 'text-blue-600', hard: 'text-orange-500', very_hard: 'text-red-500', mixed: 'text-violet-600' }[d] || 'text-slate-600'
}
function formatDate(d: string) { return dayjs(d).format('MM-DD HH:mm') }

onMounted(async () => {
  await load()
  await loadCoursewares()
  await loadTextbooks()
})
</script>

<style scoped>
.paper-doc {
  font-family: "Songti SC", "SimSun", "Noto Serif CJK SC", serif;
}
</style>
