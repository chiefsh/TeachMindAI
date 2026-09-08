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
            <span :class="diffColor(row.difficulty)">{{ diffLabel(row.difficulty) }}</span>
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
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="viewDetail(row)">查看</el-button>
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

    <!-- 生成弹窗 -->
    <el-dialog v-model="showCreate" title="生成作业/试卷" width="640px" :close-on-click-modal="false">
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
          <el-radio-group v-model="form.difficulty">
            <el-radio-button v-for="d in difficulties" :key="d.value" :value="d.value">{{ d.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="题目配置">
          <div class="grid grid-cols-2 gap-3 w-full">
            <div v-for="t in questionTypes" :key="t.value" class="flex items-center gap-2">
              <span class="text-sm text-slate-600 w-16 flex-shrink-0">{{ t.label }}</span>
              <el-input-number v-model="form.question_config[t.value]" :min="0" :max="20" size="small" style="width:100px" />
              <span class="text-xs text-slate-400">道</span>
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
        <el-button type="primary" :icon="MagicStick" :loading="creating" @click="handleCreate">开始生成</el-button>
      </template>
    </el-dialog>

    <!-- 查看详情 -->
    <el-dialog v-model="showDetail" :title="detailPaper?.title" width="820px" top="5vh">
      <template #header>
        <div class="flex items-center justify-between pr-6">
          <span class="font-semibold text-slate-800">{{ detailPaper?.title }}</span>
          <el-button-group v-if="detailPaper?.gen_status === 'done' && questions.length">
            <el-button size="small" :loading="exporting === 'docx'" :icon="Document" @click="doExport('docx')">导出 Word</el-button>
            <el-button size="small" :loading="exporting === 'pdf'" :icon="Tickets" @click="doExport('pdf')">导出 PDF</el-button>
          </el-button-group>
        </div>
      </template>

      <!-- Word 文档样式 -->
      <div v-if="detailPaper?.gen_status === 'done' && questions.length"
           class="max-h-[72vh] overflow-y-auto bg-slate-100 p-6">
        <div class="paper-doc bg-white mx-auto px-12 py-10 shadow-sm" style="max-width:720px">
          <h2 class="text-center text-xl font-bold text-slate-900">{{ detailPaper?.title }}</h2>
          <p class="text-center text-sm text-slate-500 mt-2">
            {{ detailPaper?.paper_type === 'exam' ? '考试试卷' : '课后作业' }}
            　·　共 {{ questions.length }} 题
            <template v-if="isExam">　·　满分 {{ totalScore }} 分</template>
          </p>
          <p class="text-center text-sm text-slate-500 mt-1">
            姓名：____________　班级：____________　得分：____________
          </p>
          <div class="border-b border-slate-200 my-5"></div>

          <div class="space-y-5">
            <div v-for="(q, i) in questions" :key="q.id">
              <p class="text-slate-800 leading-relaxed">
                <span class="font-medium">{{ i + 1 }}.</span> {{ q.content }}
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
          </div>

          <!-- 参考答案 -->
          <div class="mt-8 pt-5 border-t border-dashed border-slate-300">
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
        生成失败，请重新生成
        <p v-if="detailPaper.content" class="text-xs text-slate-400 mt-2">{{ detailPaper.content }}</p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { homeworkApi, coursewareApi, textbookApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { ElMessage } from 'element-plus'
import { Plus, MagicStick, Loading, Document, Tickets } from '@element-plus/icons-vue'
import type { HomeworkPaper, HomeworkQuestion, Courseware, Textbook, Chapter, HomeworkSourceType, QuestionSourceMode } from '@/types'
import { isBusyStatus, useBusyPoll } from '@/utils/busyPoll'
import dayjs from 'dayjs'

const edu = useEducationStore()
const papers = ref<HomeworkPaper[]>([])
const coursewares = ref<Courseware[]>([])
const textbooks = ref<Textbook[]>([])
const chapters = ref<Chapter[]>([])
const doneCourseware = computed(() => coursewares.value.filter(c => c.gen_status === 'done'))
const doneTextbooks = computed(() => textbooks.value.filter(t => t.parse_status === 'done'))
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const showDetail = ref(false)
const detailPaper = ref<HomeworkPaper | null>(null)
const exporting = ref<string>('')
const formRef = ref()
const chapterTreeRef = ref()

const questions = computed<HomeworkQuestion[]>(() => detailPaper.value?.questions || [])
const isExam = computed(() => detailPaper.value?.paper_type === 'exam')
const totalScore = computed(() => questions.value.reduce((s, q) => s + (q.score || 0), 0))

const form = reactive({
  title: '',
  paper_type: 'homework',
  source_type: 'courseware' as HomeworkSourceType,
  question_source: 'ai' as QuestionSourceMode,
  courseware_ids: [] as number[],
  textbook_id: null as number | null,
  chapter_ids: [] as number[],
  difficulty: 'medium',
  question_config: { single_choice: 5, fill_blank: 3, short_answer: 2 } as Record<string, number>,
})
const rules = {
  title: [{ required: true, message: '请填写标题' }],
}

const difficulties = [
  { value: 'easy', label: '简单' }, { value: 'medium', label: '中等' },
  { value: 'hard', label: '较难' }, { value: 'very_hard', label: '特难' },
]
const questionTypes = [
  { value: 'single_choice', label: '单选题' }, { value: 'fill_blank', label: '填空题' },
  { value: 'short_answer', label: '简答题' }, { value: 'true_false', label: '判断题' },
]

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

function openCreate() {
  resetScopeFields()
  form.source_type = 'courseware'
  showCreate.value = true
}

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
  const totalQ = Object.values(form.question_config).reduce((s, n) => s + (n || 0), 0)
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
    await homeworkApi.create({
      title: form.title,
      paper_type: form.paper_type,
      difficulty: form.difficulty,
      question_config: form.question_config,
      source_type: form.source_type,
      question_source: form.question_source,
      courseware_ids: form.source_type === 'courseware' ? form.courseware_ids : [],
      textbook_id: form.source_type === 'courseware' ? undefined : form.textbook_id,
      chapter_ids: form.source_type === 'chapters' ? form.chapter_ids : [],
    })
    ElMessage.success('生成任务已提交')
    showCreate.value = false
    await load()
  } finally { creating.value = false }
}

async function viewDetail(paper: HomeworkPaper) {
  detailPaper.value = (await homeworkApi.get(paper.id)) as any
  showDetail.value = true
}

async function doExport(fmt: 'docx' | 'pdf') {
  if (!detailPaper.value) return
  exporting.value = fmt
  try {
    const blob = (await homeworkApi.exportFile(detailPaper.value.id, fmt)) as unknown as Blob
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
function diffColor(d: string) {
  return { easy: 'text-green-600', medium: 'text-blue-600', hard: 'text-orange-500', very_hard: 'text-red-500' }[d] || 'text-slate-600'
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
