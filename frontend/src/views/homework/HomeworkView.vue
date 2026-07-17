<template>
  <div class="p-6">
    <div class="flex items-start justify-between mb-6">
      <div>
        <h1 class="page-title">作业 / 考试生成</h1>
        <p class="page-subtitle">基于课件内容，AI 自动生成课后作业或考试试卷</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="showCreate = true">生成作业/试卷</el-button>
    </div>

    <!-- 列表 -->
    <div class="card !p-0 overflow-hidden">
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

    <!-- 生成弹窗 -->
    <el-dialog v-model="showCreate" title="生成作业/试卷" width="580px" :close-on-click-modal="false">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="如：第一单元课后作业" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.paper_type">
            <el-radio value="homework">课后作业</el-radio>
            <el-radio value="exam">考试试卷</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="关联课件" prop="courseware_ids">
          <el-select v-model="form.courseware_ids" multiple placeholder="选择课件（可多选）" style="width:100%">
            <el-option v-for="cw in doneCourseware" :key="cw.id" :label="cw.title" :value="cw.id" />
          </el-select>
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
          <el-switch v-model="form.use_question_bank" active-text="从题库筛选" inactive-text="AI 直接生成" />
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
            {{ detailPaper?.paper_type === 'exam' ? '考试试卷' : '课后作业' }}　·　共 {{ questions.length }} 题　·　满分 {{ totalScore }} 分
          </p>
          <p class="text-center text-sm text-slate-500 mt-1">
            姓名：____________　班级：____________　得分：____________
          </p>
          <div class="border-b border-slate-200 my-5"></div>

          <div class="space-y-5">
            <div v-for="(q, i) in questions" :key="q.id">
              <p class="text-slate-800 leading-relaxed">
                <span class="font-medium">{{ i + 1 }}.</span> {{ q.content }}
                <span v-if="q.score" class="text-xs text-slate-400">（{{ q.score }} 分）</span>
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
        <p class="mt-3 text-slate-500">AI 正在生成，请稍候...</p>
      </div>
      <div v-else-if="detailPaper?.gen_status === 'failed'" class="text-center py-10 text-slate-500">
        生成失败，请重新生成
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { homeworkApi, coursewareApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { ElMessage } from 'element-plus'
import { Plus, MagicStick, Loading, Document, Tickets } from '@element-plus/icons-vue'
import type { HomeworkPaper, HomeworkQuestion, Courseware } from '@/types'
import dayjs from 'dayjs'

const edu = useEducationStore()
const papers = ref<HomeworkPaper[]>([])
const coursewares = ref<Courseware[]>([])
const doneCourseware = computed(() => coursewares.value.filter(c => c.gen_status === 'done'))
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const showDetail = ref(false)
const detailPaper = ref<HomeworkPaper | null>(null)
const exporting = ref<string>('')
const formRef = ref()

const questions = computed<HomeworkQuestion[]>(() => detailPaper.value?.questions || [])
const totalScore = computed(() => questions.value.reduce((s, q) => s + (q.score || 0), 0))

const form = reactive({
  title: '', paper_type: 'homework', courseware_ids: [] as number[],
  difficulty: 'medium', use_question_bank: false,
  question_config: { single_choice: 5, fill_blank: 3, short_answer: 2 } as Record<string, number>,
})
const rules = {
  title: [{ required: true, message: '请填写标题' }],
  courseware_ids: [{ required: true, message: '请选择关联课件', type: 'array', min: 1 }],
}

const difficulties = [
  { value: 'easy', label: '简单' }, { value: 'medium', label: '中等' },
  { value: 'hard', label: '较难' }, { value: 'very_hard', label: '特难' },
]
const questionTypes = [
  { value: 'single_choice', label: '单选题' }, { value: 'fill_blank', label: '填空题' },
  { value: 'short_answer', label: '简答题' }, { value: 'true_false', label: '判断题' },
]

async function load() {
  loading.value = true
  try {
    papers.value = (await homeworkApi.list({
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
    })) as any
  }
  finally { loading.value = false }
}

async function loadCoursewares() {
  coursewares.value = (await coursewareApi.list({
    grade_id: edu.selectedGradeId || undefined,
    subject_id: edu.selectedSubjectId || undefined,
  })) as any
}

// 顶部全局年级/科目变化时同步刷新试卷与可选课件
watchDebounced(() => [edu.selectedGradeId, edu.selectedSubjectId], () => { load(); loadCoursewares() }, { debounce: 250 })

async function handleCreate() {
  await formRef.value?.validate()
  creating.value = true
  try {
    await homeworkApi.create(form)
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
})
</script>

<style scoped>
.paper-doc {
  font-family: "Songti SC", "SimSun", "Noto Serif CJK SC", serif;
}
</style>
