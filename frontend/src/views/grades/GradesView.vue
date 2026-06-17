<template>
  <div class="p-6">
    <div class="flex items-start justify-between mb-6">
      <div>
        <h1 class="page-title">学生成绩管理</h1>
        <p class="page-subtitle">成绩录入、统计分析、AI 智能报告</p>
      </div>
      <div class="flex gap-2">
        <el-button :icon="Upload" @click="showImport = true">导入成绩</el-button>
        <el-button type="primary" :icon="Plus" @click="openManual">手动录入</el-button>
      </div>
    </div>

    <!-- Tab 导航 -->
    <el-tabs v-model="activeTab" class="card !pb-0">
      <el-tab-pane label="成绩列表" name="list" />
      <el-tab-pane label="统计分析" name="stats" />
      <el-tab-pane label="AI 分析报告" name="ai" />
    </el-tabs>

    <!-- 成绩列表 -->
    <div v-if="activeTab === 'list'" class="mt-4">
      <div class="card !p-0 overflow-hidden">
        <el-table :data="results" v-loading="loading" max-height="550">
          <el-table-column label="姓名" width="100">
            <template #default="{ row }">
              <span class="text-sm text-slate-700">{{ row.student_name || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="学号" width="100">
            <template #default="{ row }">
              <span class="text-xs text-slate-500">{{ row.student_no || row.student_id }}</span>
            </template>
          </el-table-column>
          <el-table-column label="年级" width="100">
            <template #default="{ row }">
              <span class="text-sm text-slate-600">{{ edu.gradeName(row.grade_id) || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="科目" width="90">
            <template #default="{ row }">
              <span class="text-sm text-slate-600">{{ edu.subjectName(row.subject_id) || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="考试名称" min-width="160">
            <template #default="{ row }"><span class="text-sm">{{ row.exam_name }}</span></template>
          </el-table-column>
          <el-table-column label="得分" width="90" align="center">
            <template #default="{ row }">
              <span :class="`font-bold ${scoreColor(row.score, row.full_score)}`">{{ row.score }}</span>
              <span class="text-xs text-slate-400">/{{ row.full_score }}</span>
            </template>
          </el-table-column>
          <el-table-column label="录入方式" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="entryTag(row.entry_method)">{{ entryLabel(row.entry_method) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" width="110">
            <template #default="{ row }">
              <span class="text-xs text-slate-400">{{ formatDate(row.created_at) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 统计分析 -->
    <div v-if="activeTab === 'stats'" class="mt-4 space-y-4">
      <div class="card flex flex-wrap items-center gap-3 !py-3">
        <span v-if="!edu.selectedSubjectId" class="text-sm text-amber-600">请先在顶部选择年级和科目</span>
        <el-select v-model="statsForm.exam_name" placeholder="选择考试" style="width:220px" filterable clearable :disabled="!edu.selectedSubjectId">
          <el-option v-for="name in examNames" :key="name" :label="name" :value="name" />
        </el-select>
        <el-button type="primary" :loading="statsLoading" :disabled="!edu.selectedSubjectId" @click="generateStats">生成统计</el-button>
      </div>

      <template v-if="stats">
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="card text-center">
            <p class="text-sm text-slate-500">平均分</p>
            <p class="text-2xl font-bold text-primary-600 mt-1">{{ stats.avg_score }}</p>
          </div>
          <div class="card text-center">
            <p class="text-sm text-slate-500">及格率</p>
            <p class="text-2xl font-bold text-green-600 mt-1">{{ ((stats.pass_rate || 0) * 100).toFixed(1) }}%</p>
          </div>
          <div class="card text-center">
            <p class="text-sm text-slate-500">优秀率</p>
            <p class="text-2xl font-bold text-blue-600 mt-1">{{ ((stats.excellent_rate || 0) * 100).toFixed(1) }}%</p>
          </div>
          <div class="card text-center">
            <p class="text-sm text-slate-500">最高/最低</p>
            <p class="text-lg font-bold text-slate-700 mt-1">{{ stats.max_score }} / {{ stats.min_score }}</p>
          </div>
        </div>
        <div class="card">
          <h3 class="text-sm font-semibold text-slate-600 mb-4">分数段分布</h3>
          <v-chart :option="chartOption" style="height:260px" autoresize />
        </div>
      </template>

      <!-- 历史统计 -->
      <div class="card !p-0 overflow-hidden">
        <div class="px-4 py-3 border-b border-slate-100 text-sm font-semibold text-slate-600">历史统计分析</div>
        <el-table :data="statsReports" v-loading="statsHistLoading">
          <el-table-column label="年级" width="100"><template #default="{ row }">{{ edu.gradeName(row.grade_id) || '—' }}</template></el-table-column>
          <el-table-column label="科目" width="90"><template #default="{ row }">{{ edu.subjectName(row.subject_id) || '—' }}</template></el-table-column>
          <el-table-column label="考试名称" min-width="160"><template #default="{ row }">{{ row.exam_name }}</template></el-table-column>
          <el-table-column label="平均分" width="90" align="center"><template #default="{ row }">{{ row.content?.avg_score ?? '—' }}</template></el-table-column>
          <el-table-column label="生成时间" width="130"><template #default="{ row }"><span class="text-xs text-slate-400">{{ formatDate(row.created_at) }}</span></template></el-table-column>
          <el-table-column label="操作" width="190" align="center">
            <template #default="{ row }">
              <el-button size="small" link type="primary" @click="viewStats(row)">查看</el-button>
              <el-button size="small" link type="warning" @click="regenStats(row)">重新生成</el-button>
              <el-popconfirm title="确定删除该记录？" @confirm="delReport(row, 'stats')">
                <template #reference><el-button size="small" link type="danger">删除</el-button></template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- AI 分析报告 -->
    <div v-if="activeTab === 'ai'" class="mt-4 space-y-4">
      <div class="card !py-3 space-y-3">
        <div class="flex flex-wrap items-center gap-3">
          <span v-if="!edu.selectedSubjectId" class="text-sm text-amber-600">请先在顶部选择年级和科目</span>
          <el-select v-model="aiForm.exam_name" placeholder="选择考试" style="width:220px" filterable clearable :disabled="!edu.selectedSubjectId">
            <el-option v-for="name in examNames" :key="name" :label="name" :value="name" />
          </el-select>
          <el-button type="primary" :icon="MagicStick" :loading="aiLoading" :disabled="!edu.selectedSubjectId" @click="genAiReport">生成 AI 分析</el-button>
        </div>
        <el-input
          v-model="aiForm.custom_prompt" type="textarea" :rows="2"
          placeholder="自定义提示词（可选）：例如「重点分析两极分化情况，并给出分层教学建议」"
        />
      </div>

      <!-- 当前报告 -->
      <div v-if="aiCurrent" class="card">
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm font-semibold text-slate-700">
            {{ aiCurrent.exam_name }}
            <span class="text-xs text-slate-400 ml-2">{{ formatDate(aiCurrent.created_at) }}</span>
          </span>
          <span :class="`badge badge-${aiCurrent.gen_status}`">{{ statusLabel(aiCurrent.gen_status) }}</span>
        </div>
        <div v-if="aiCurrent.gen_status === 'processing' || aiCurrent.gen_status === 'pending'" class="text-center py-10">
          <el-icon class="text-4xl text-primary-500 animate-spin"><Loading /></el-icon>
          <p class="mt-3 text-slate-500">AI 正在分析，请稍候...</p>
        </div>
        <div v-else-if="aiCurrent.gen_status === 'failed'" class="text-center py-8 text-red-500">
          生成失败：{{ aiCurrent.content?.error || '请重试' }}
        </div>
        <div v-else class="md-report" v-html="renderMarkdown(aiCurrent.content?.report || '')" />
      </div>

      <!-- 历史报告 -->
      <div class="card !p-0 overflow-hidden">
        <div class="px-4 py-3 border-b border-slate-100 text-sm font-semibold text-slate-600">历史 AI 分析报告</div>
        <el-table :data="aiReports" v-loading="aiHistLoading">
          <el-table-column label="年级" width="100"><template #default="{ row }">{{ edu.gradeName(row.grade_id) || '—' }}</template></el-table-column>
          <el-table-column label="科目" width="90"><template #default="{ row }">{{ edu.subjectName(row.subject_id) || '—' }}</template></el-table-column>
          <el-table-column label="考试名称" min-width="150"><template #default="{ row }">{{ row.exam_name }}</template></el-table-column>
          <el-table-column label="状态" width="90"><template #default="{ row }"><span :class="`badge badge-${row.gen_status}`">{{ statusLabel(row.gen_status) }}</span></template></el-table-column>
          <el-table-column label="生成时间" width="130"><template #default="{ row }"><span class="text-xs text-slate-400">{{ formatDate(row.created_at) }}</span></template></el-table-column>
          <el-table-column label="操作" width="190" align="center">
            <template #default="{ row }">
              <el-button size="small" link type="primary" @click="viewAi(row)">查看</el-button>
              <el-button size="small" link type="warning" @click="regenAi(row)">重新生成</el-button>
              <el-popconfirm title="确定删除该报告？" @confirm="delReport(row, 'ai')">
                <template #reference><el-button size="small" link type="danger">删除</el-button></template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 手动录入弹窗 -->
    <el-dialog v-model="showManual" title="手动录入成绩" width="720px" :close-on-click-modal="false" top="5vh">
      <!-- 步骤一：基本信息 -->
      <div class="flex flex-wrap items-center gap-3 mb-4">
        <el-select v-model="manualForm.grade_id" placeholder="年级" style="width:120px" @change="manualForm.subject_id = null">
          <el-option v-for="g in edu.sortedGrades" :key="g.id" :label="g.name" :value="g.id" />
        </el-select>
        <el-select v-model="manualForm.subject_id" placeholder="科目" style="width:130px" :disabled="!manualForm.grade_id">
          <el-option v-for="s in edu.subjectsOfGrade(manualForm.grade_id)" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-input v-model="manualForm.exam_name" placeholder="考试名称，如：期中考试" style="width:200px" />
        <div class="flex items-center gap-1">
          <span class="text-sm text-slate-500">满分</span>
          <el-input-number v-model="manualForm.full_score" :min="1" :max="1000" size="small" style="width:110px" />
        </div>
      </div>

      <!-- 步骤二：Excel 样式表格 -->
      <div class="border border-slate-200 rounded-lg overflow-hidden" @paste="onPasteRows">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-slate-50 text-slate-600">
              <th class="w-10 py-2 font-medium border-b border-slate-200">#</th>
              <th class="py-2 font-medium border-b border-slate-200 text-left px-2">姓名</th>
              <th class="py-2 font-medium border-b border-slate-200 text-left px-2">学号</th>
              <th class="py-2 font-medium border-b border-slate-200 text-left px-2 w-32">成绩</th>
              <th class="w-12 py-2 font-medium border-b border-slate-200"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in manualRows" :key="i" class="hover:bg-slate-50">
              <td class="text-center text-slate-400 border-b border-slate-100">{{ i + 1 }}</td>
              <td class="border-b border-slate-100 px-1">
                <input v-model="row.name" class="cell-input" placeholder="姓名" />
              </td>
              <td class="border-b border-slate-100 px-1">
                <input v-model="row.student_no" class="cell-input" placeholder="学号" />
              </td>
              <td class="border-b border-slate-100 px-1">
                <input v-model="row.score" type="number" class="cell-input" placeholder="分数" />
              </td>
              <td class="text-center border-b border-slate-100">
                <el-button link type="danger" size="small" @click="removeRow(i)">删除</el-button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex items-center justify-between mt-2">
        <el-button size="small" :icon="Plus" @click="addRow">添加一行</el-button>
        <span class="text-xs text-slate-400">提示：可直接从 Excel 复制「姓名 学号 成绩」整片单元格，粘贴到表格区域</span>
      </div>

      <template #footer>
        <el-button @click="showManual = false">取消</el-button>
        <el-button type="primary" :loading="manualSaving" @click="submitManual">保存成绩</el-button>
      </template>
    </el-dialog>

    <!-- 导入弹窗 -->
    <el-dialog v-model="showImport" title="导入成绩" width="460px">
      <el-tabs v-model="importTab">
        <el-tab-pane label="文档导入" name="doc">
          <div class="pt-3">
            <el-upload :auto-upload="false" accept=".xlsx,.xls,.csv" :on-change="(f: any) => importFile = f.raw">
              <el-button :icon="Upload">选择 Excel 文件</el-button>
            </el-upload>
            <p class="text-xs text-slate-400 mt-2">列格式：student_no, name, exam_name, subject_id, score, full_score</p>
          </div>
        </el-tab-pane>
        <el-tab-pane label="图片识别" name="img">
          <div class="pt-3">
            <el-upload :auto-upload="false" accept=".jpg,.jpeg,.png" :on-change="(f: any) => importImg = f.raw">
              <el-button :icon="PictureFilled">选择成绩图片</el-button>
            </el-upload>
            <p class="text-xs text-slate-400 mt-2">支持手写/印刷成绩单，AI 自动识别</p>
          </div>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="showImport = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="handleImport">确定导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { studentApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { renderMarkdown } from '@/utils/markdown'
import { ElMessage } from 'element-plus'
import { Upload, Plus, MagicStick, PictureFilled, Loading } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { ExamResult, GradeReport } from '@/types'
import dayjs from 'dayjs'

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const edu = useEducationStore()
const results = ref<ExamResult[]>([])
const loading = ref(false)
const activeTab = ref('list')
const showImport = ref(false)
const showManual = ref(false)
const importing = ref(false)
const importTab = ref('doc')
const importFile = ref<File | null>(null)
const importImg = ref<File | null>(null)
const stats = ref<any>(null)
const statsForm = reactive({ exam_name: '' })
const aiForm = reactive({ exam_name: '', custom_prompt: '' })
const examNames = ref<string[]>([])
const statsLoading = ref(false)
const statsHistLoading = ref(false)
const statsReports = ref<GradeReport[]>([])
const aiLoading = ref(false)
const aiHistLoading = ref(false)
const aiReports = ref<GradeReport[]>([])
const aiCurrent = ref<GradeReport | null>(null)
let aiPollTimer: ReturnType<typeof setInterval> | null = null

// 根据顶部全局年级/科目加载可选的考试名称
async function loadExamNames() {
  if (!edu.selectedSubjectId) { examNames.value = []; return }
  examNames.value = (await studentApi.getExamNames({
    grade_id: edu.selectedGradeId || undefined,
    subject_id: edu.selectedSubjectId,
  })) as any
}

type ManualRow = { name: string; student_no: string; score: string | number | null }
const manualForm = reactive({ grade_id: null as any, subject_id: null as any, exam_name: '', full_score: 100 })
const manualRows = ref<ManualRow[]>([])
const manualSaving = ref(false)

function blankRows(n: number): ManualRow[] {
  return Array.from({ length: n }, () => ({ name: '', student_no: '', score: '' }))
}
function addRow() { manualRows.value.push({ name: '', student_no: '', score: '' }) }
function removeRow(i: number) {
  manualRows.value.splice(i, 1)
  if (manualRows.value.length === 0) manualRows.value = blankRows(1)
}

// 支持从 Excel 复制整片单元格粘贴
function onPasteRows(e: ClipboardEvent) {
  const text = e.clipboardData?.getData('text/plain') || ''
  if (!text.includes('\t') && !text.includes('\n')) return  // 单格粘贴交给输入框
  e.preventDefault()
  const lines = text.split(/\r?\n/).filter(l => l.trim())
  const parsed: ManualRow[] = []
  for (const line of lines) {
    const cols = line.split('\t')
    const name = (cols[0] || '').trim()
    const student_no = (cols[1] || '').trim()
    const score = (cols[2] || '').trim()
    // 跳过表头行
    if (name === '姓名' || student_no === '学号') continue
    if (!name && !student_no && !score) continue
    parsed.push({ name, student_no, score: score === '' ? '' : Number(score) })
  }
  if (parsed.length) {
    // 用现有空行填充，否则追加
    const existing = manualRows.value.filter(r => r.name || r.student_no || (r.score !== '' && r.score !== null))
    manualRows.value = [...existing, ...parsed]
  }
}

async function submitManual() {
  if (!manualForm.grade_id || !manualForm.subject_id) { ElMessage.warning('请选择年级和科目'); return }
  if (!manualForm.exam_name.trim()) { ElMessage.warning('请填写考试名称'); return }
  const rows = manualRows.value
    .filter(r => (r.name || r.student_no) && r.score !== '' && r.score !== null)
    .map(r => ({ name: r.name.trim(), student_no: String(r.student_no).trim(), score: Number(r.score) }))
  if (!rows.length) { ElMessage.warning('请至少填写一行有效成绩'); return }
  manualSaving.value = true
  try {
    const res: any = await studentApi.manualGrades({
      grade_id: manualForm.grade_id,
      subject_id: manualForm.subject_id,
      exam_name: manualForm.exam_name.trim(),
      full_score: manualForm.full_score,
      rows,
    })
    ElMessage.success(`已录入 ${res.count} 条成绩`)
    showManual.value = false
    manualRows.value = blankRows(8)
    manualForm.exam_name = ''
    await loadResults()
  } finally { manualSaving.value = false }
}

function openManual() {
  manualRows.value = blankRows(8)
  manualForm.grade_id = edu.selectedGradeId || null
  manualForm.subject_id = edu.selectedSubjectId || null
  showManual.value = true
}

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: Object.keys(stats.value?.score_distribution || {}) },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: Object.values(stats.value?.score_distribution || {}), itemStyle: { color: '#4f46e5', borderRadius: [4, 4, 0, 0] } }],
}))

async function loadResults() {
  loading.value = true
  try {
    results.value = (await studentApi.getResults({
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
    })) as any
  }
  finally { loading.value = false }
}

// ─── 统计分析 ───────────────────────────────
async function loadStatsHistory() {
  statsHistLoading.value = true
  try {
    statsReports.value = (await studentApi.listAnalysis({
      report_type: 'stats',
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
    })) as any
  }
  finally { statsHistLoading.value = false }
}
async function generateStats() {
  if (!edu.selectedSubjectId) { ElMessage.warning('请先在顶部选择年级和科目'); return }
  if (!statsForm.exam_name) { ElMessage.warning('请选择考试'); return }
  statsLoading.value = true
  try {
    const rec: any = await studentApi.createAnalysis({
      grade_id: edu.selectedGradeId, subject_id: edu.selectedSubjectId,
      exam_name: statsForm.exam_name, report_type: 'stats',
    })
    stats.value = rec.content
    await loadStatsHistory()
  } finally { statsLoading.value = false }
}
function viewStats(row: GradeReport) { stats.value = row.content }
async function regenStats(row: GradeReport) {
  const rec: any = await studentApi.regenerateAnalysis(row.id)
  stats.value = rec.content
  ElMessage.success('已重新生成')
  await loadStatsHistory()
}

// ─── AI 分析报告 ────────────────────────────
async function loadAiHistory() {
  aiHistLoading.value = true
  try {
    aiReports.value = (await studentApi.listAnalysis({
      report_type: 'ai',
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
    })) as any
  }
  finally { aiHistLoading.value = false }
}
function startAiPoll(id: number) {
  if (aiPollTimer) clearInterval(aiPollTimer)
  aiPollTimer = setInterval(async () => {
    const rec: any = await studentApi.getAnalysis(id)
    aiCurrent.value = rec
    const idx = aiReports.value.findIndex(r => r.id === id)
    if (idx >= 0) aiReports.value[idx] = rec
    if (rec.gen_status === 'done' || rec.gen_status === 'failed') {
      if (aiPollTimer) { clearInterval(aiPollTimer); aiPollTimer = null }
    }
  }, 4000)
}
async function genAiReport() {
  if (!edu.selectedSubjectId) { ElMessage.warning('请先在顶部选择年级和科目'); return }
  if (!aiForm.exam_name) { ElMessage.warning('请选择考试'); return }
  aiLoading.value = true
  try {
    const rec: any = await studentApi.createAnalysis({
      grade_id: edu.selectedGradeId, subject_id: edu.selectedSubjectId, exam_name: aiForm.exam_name,
      report_type: 'ai', custom_prompt: aiForm.custom_prompt || null,
    })
    aiCurrent.value = rec
    await loadAiHistory()
    startAiPoll(rec.id)
  } finally { aiLoading.value = false }
}
async function viewAi(row: GradeReport) {
  aiCurrent.value = row
  if (row.gen_status === 'processing' || row.gen_status === 'pending') startAiPoll(row.id)
}
async function regenAi(row: GradeReport) {
  const rec: any = await studentApi.regenerateAnalysis(row.id, aiForm.custom_prompt || row.custom_prompt || null)
  aiCurrent.value = rec
  await loadAiHistory()
  startAiPoll(rec.id)
  ElMessage.success('已重新生成')
}

async function delReport(row: GradeReport, type: 'stats' | 'ai') {
  await studentApi.deleteAnalysis(row.id)
  ElMessage.success('已删除')
  if (type === 'stats') {
    await loadStatsHistory()
  } else {
    if (aiCurrent.value?.id === row.id) aiCurrent.value = null
    await loadAiHistory()
  }
}

async function handleImport() {
  importing.value = true
  try {
    if (importTab.value === 'doc' && importFile.value) {
      const fd = new FormData(); fd.append('file', importFile.value)
      await studentApi.batchImport(fd)
      ElMessage.success('导入任务已提交')
    } else if (importTab.value === 'img' && importImg.value) {
      const fd = new FormData(); fd.append('file', importImg.value)
      await studentApi.imageImport(fd)
      ElMessage.success('图片识别任务已提交')
    }
    showImport.value = false
  } finally { importing.value = false }
}

function scoreColor(score: number, full: number) {
  const pct = score / full
  if (pct >= 0.9) return 'text-green-600'
  if (pct >= 0.6) return 'text-blue-600'
  return 'text-red-500'
}
function entryLabel(m: string) { return { manual: '手动', document: '文档', image: '图片' }[m] || m }
function entryTag(m: string): any { return { manual: '', document: 'info', image: 'warning' }[m] || '' }
function statusLabel(s: string) { return { pending: '待生成', processing: '生成中', done: '已完成', failed: '失败' }[s] || s }
function formatDate(d: string) { return dayjs(d).format('MM-DD HH:mm') }

watch(activeTab, (tab) => {
  if (tab === 'stats') { loadStatsHistory(); loadExamNames() }
  if (tab === 'ai') { loadAiHistory(); loadExamNames() }
})

// 顶部全局年级/科目变化时，所有数据（成绩列表/统计/AI报告/考试名称）都同步刷新
watch(() => [edu.selectedGradeId, edu.selectedSubjectId], () => {
  statsForm.exam_name = ''
  aiForm.exam_name = ''
  stats.value = null
  aiCurrent.value = null
  loadResults()
  loadExamNames()
  if (activeTab.value === 'stats') loadStatsHistory()
  if (activeTab.value === 'ai') loadAiHistory()
})

onMounted(() => {
  loadResults()
  loadExamNames()
})
onUnmounted(() => { if (aiPollTimer) clearInterval(aiPollTimer) })
</script>

<style scoped>
.cell-input {
  width: 100%;
  padding: 6px 6px;
  font-size: 13px;
  color: #334155;
  background: transparent;
  border: none;
  outline: none;
}
.cell-input:focus {
  background: #eef2ff;
  border-radius: 4px;
}

.md-report {
  color: #334155;
  font-size: 14px;
  line-height: 1.75;
}
.md-report :deep(h3) { font-size: 17px; font-weight: 700; color: #1e293b; margin: 16px 0 8px; }
.md-report :deep(h4) { font-size: 15px; font-weight: 600; color: #334155; margin: 14px 0 6px; }
.md-report :deep(h5) { font-size: 14px; font-weight: 600; color: #334155; margin: 12px 0 6px; }
.md-report :deep(p) { margin: 8px 0; }
.md-report :deep(ul) { list-style: disc; padding-left: 1.5em; margin: 8px 0; }
.md-report :deep(ol) { list-style: decimal; padding-left: 1.5em; margin: 8px 0; }
.md-report :deep(li) { margin: 4px 0; }
.md-report :deep(strong) { color: #1e293b; font-weight: 600; }
.md-report :deep(code) { background: #f1f5f9; color: #be123c; padding: 1px 5px; border-radius: 4px; font-size: 12px; }
.md-report :deep(hr) { border: none; border-top: 1px solid #e2e8f0; margin: 14px 0; }
.md-report :deep(.md-table) { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 13px; }
.md-report :deep(.md-table th),
.md-report :deep(.md-table td) { border: 1px solid #e2e8f0; padding: 6px 10px; text-align: left; }
.md-report :deep(.md-table th) { background: #f8fafc; font-weight: 600; }
</style>
