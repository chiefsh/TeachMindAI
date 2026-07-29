<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4">
      <div class="min-w-0">
        <el-button link :icon="ArrowLeft" @click="router.back()">返回</el-button>
        <h1 class="page-title truncate">{{ set?.name || '试题分析' }}</h1>
        <div class="flex items-center gap-2 mt-1">
          <el-tag v-if="set" size="small" type="info">{{ edu.gradeName(set.grade_id) }}</el-tag>
          <el-tag v-if="set" size="small" type="success">{{ edu.subjectName(set.subject_id) }}</el-tag>
          <span v-if="set" :class="`badge badge-${set.parse_status}`">{{ statusLabel(set.parse_status) }}</span>
          <span class="text-xs text-slate-400">{{ questions.length }} 题</span>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <el-button :icon="Download" @click="exportFile('docx')">导出 Word</el-button>
        <el-button :icon="Download" @click="exportFile('pdf')">导出 PDF</el-button>
      </div>
    </div>

    <!-- 解析中（文件解析阶段） -->
    <div v-if="set && (set.parse_status === 'pending' || set.parse_status === 'processing')" class="card !p-10 text-center">
      <el-icon class="text-3xl text-indigo-400 animate-spin"><Loading /></el-icon>
      <p class="text-slate-500 mt-3">{{ parseHint || '正在解析试题文件，请稍候...' }}</p>
    </div>
    <div v-else-if="set && set.parse_status === 'failed'" class="card !p-8 text-center">
      <el-icon class="text-3xl text-red-400"><CircleClose /></el-icon>
      <p class="text-slate-500 mt-3">解析失败：{{ set.parse_error || '未知错误' }}</p>
      <el-button
        v-if="set.source_type !== 'manual'"
        class="mt-4" type="primary" :icon="Refresh" :loading="reparsing" @click="reparse"
      >重新解析</el-button>
    </div>

    <template v-else>
      <!-- 操作栏 -->
      <div class="card !p-3 mb-4 flex items-center gap-3 flex-wrap sticky top-0 z-10">
        <el-checkbox v-model="allChecked" :indeterminate="indeterminate" @change="toggleAll">全选</el-checkbox>
        <span class="text-sm text-slate-500">已选 {{ checked.size }} 题</span>
        <div class="flex-1" />
        <el-button size="small" :icon="Collection" :disabled="!checked.size" @click="saveToBank">选中题目入库</el-button>
        <el-button size="small" type="primary" :icon="MagicStick" :loading="analyzing"
          :disabled="!checked.size" @click="startAnalyze">
          AI 解析选中题目
        </el-button>
      </div>

      <!-- 解析进度 -->
      <div v-if="analyzing" class="card !p-4 mb-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-slate-600">AI 正在图解解析（{{ progress.current }}/{{ progress.total }}）</span>
          <span class="text-xs text-slate-400">{{ progress.hint }}</span>
        </div>
        <el-progress :percentage="progressPct" :stroke-width="10" />
      </div>

      <!-- 题目列表 -->
      <div class="space-y-3">
        <div v-for="q in questions" :key="q.id" class="card !p-4">
          <div class="flex items-start gap-3">
            <el-checkbox :model-value="checked.has(q.id)" @change="(v: any) => toggleOne(q.id, v)" />
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-sm font-semibold text-slate-800">第 {{ q.seq }} 题</span>
                <el-tag size="small" type="info">{{ typeLabel(q.question_type) }}</el-tag>
                <el-tag v-if="q.analysis_status === 'processing'" size="small" type="warning">解析中</el-tag>
                <el-tag v-else-if="q.selected && q.analysis_status === 'done'" size="small" type="success">已解析</el-tag>
                <el-tag v-else-if="q.selected && q.analysis_status === 'failed'" size="small" type="danger">解析失败</el-tag>
              </div>
              <p class="text-sm text-slate-700 mt-2 math-text" v-html="renderMathText(q.content)" />
              <div v-if="q.options" class="mt-2 space-y-1">
                <p v-for="(v, k) in q.options" :key="k" class="text-sm text-slate-600 math-text">
                  <span>{{ k }}. </span><span v-html="renderMathText(String(v))" />
                </p>
              </div>

              <div class="mt-3">
                <el-button size="small" :type="revealed.has(q.id) ? 'primary' : 'default'"
                  :icon="Reading" @click="toggleReveal(q)">
                  答案解析
                </el-button>
              </div>

              <!-- 展开区 -->
              <div v-if="revealed.has(q.id)" class="mt-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
                <!-- 已 AI 解析：展示图解 + 分步解析 -->
                <template v-if="hasAnalysis(q)">
                  <iframe v-if="q.analysis_html && blobUrls[q.id]" :src="blobUrls[q.id]"
                    class="w-full rounded-lg border border-slate-200 bg-white mb-3"
                    style="height:360px" frameborder="0" />
                  <div v-if="q.analysis_content?.思路" class="mb-2 math-text">
                    <span class="font-semibold text-indigo-600">思路：</span>
                    <span class="text-sm text-slate-700" v-html="renderMathText(q.analysis_content.思路)" />
                  </div>
                  <div v-for="(st, i) in q.analysis_content?.steps || []" :key="i" class="mb-2 math-text">
                    <p class="text-sm font-medium text-slate-800">
                      <span>步骤{{ i + 1 }}{{ st.title ? '：' : '' }}</span>
                      <span v-if="st.title" v-html="renderMathText(st.title)" />
                    </p>
                    <p v-if="st.detail" class="text-sm text-slate-600" v-html="renderMathText(st.detail)" />
                    <p v-if="st.formula" class="text-sm text-slate-600" v-html="renderMathText(wrapFormula(st.formula))" />
                  </div>
                  <div v-if="q.analysis_content?.知识点?.length" class="mb-2">
                    <span class="font-semibold text-slate-700">知识点：</span>
                    <el-tag v-for="(kp, i) in q.analysis_content.知识点" :key="i" size="small" class="mr-1">{{ kp }}</el-tag>
                  </div>
                  <div v-if="q.analysis_content?.易错点" class="mb-2 math-text">
                    <span class="font-semibold text-amber-600">易错点：</span>
                    <span class="text-sm text-slate-700" v-html="renderMathText(q.analysis_content.易错点)" />
                  </div>
                  <div v-if="q.analysis_content?.答案" class="math-text">
                    <span class="font-semibold text-green-600">答案：</span>
                    <span class="text-sm text-slate-700" v-html="renderMathText(q.analysis_content.答案)" />
                  </div>
                </template>
                <!-- 未解析：直接显示答案 -->
                <template v-else>
                  <span class="font-semibold text-green-600">答案：</span>
                  <span v-if="q.answer" class="text-sm text-slate-700 math-text" v-html="renderMathText(q.answer)" />
                  <span v-else class="text-sm text-slate-700">（该题暂无答案，可勾选后用 AI 解析）</span>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { analysisApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, Download, Loading, CircleClose, Collection, MagicStick, Reading, Refresh,
} from '@element-plus/icons-vue'
import type { AnalysisSet, AnalysisQuestion } from '@/types'
import { createIframeBlob } from '@/utils/coursewareFrame'
import { renderMathText } from '@/utils/mathText'

// 公式字段可能是不带 $ 定界符的裸 LaTeX，补上 $...$ 以便渲染
function wrapFormula(f: string): string {
  const s = String(f || '').trim()
  if (!s) return ''
  return s.includes('$') ? s : `$${s}$`
}

const route = useRoute()
const router = useRouter()
const edu = useEducationStore()
const setId = Number(route.params.id)

const set = ref<AnalysisSet | null>(null)
const questions = ref<AnalysisQuestion[]>([])
const checked = reactive(new Set<number>())
const revealed = reactive(new Set<number>())
const blobUrls = reactive<Record<number, string>>({})
const analyzing = ref(false)
const reparsing = ref(false)
const parseHint = ref('')
const progress = reactive({ current: 0, total: 0, hint: '' })

let ws: WebSocket | null = null
let poll: number | null = null

const progressPct = computed(() =>
  progress.total ? Math.round((progress.current / progress.total) * 100) : 0)
const allChecked = computed({
  get: () => questions.value.length > 0 && checked.size === questions.value.length,
  set: () => {},
})
const indeterminate = computed(() => checked.size > 0 && checked.size < questions.value.length)

function hasAnalysis(q: AnalysisQuestion) {
  return !!q.analysis_content && q.analysis_status === 'done'
}

async function load() {
  const data = (await analysisApi.get(setId)) as any as AnalysisSet
  set.value = data
  questions.value = data.questions || []
  // 预填已勾选
  for (const q of questions.value) if (q.selected) checked.add(q.id)
  // 若仍在文件解析中：WebSocket 实时进度 + 轮询兜底
  if (data.parse_status === 'pending' || data.parse_status === 'processing') {
    if (data.task_id) connectParseWs(data.task_id)
    startParsePoll()
  }
}

async function reparse() {
  reparsing.value = true
  try {
    await analysisApi.reparse(setId)
    ElMessage.success('已重新提交解析')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '重新解析失败')
  } finally {
    reparsing.value = false
  }
}

function connectParseWs(taskId: string) {
  closeWs()
  try {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${proto}://${location.host}/api/v1/ws/task/${taskId}`)
    ws.onopen = () => stopPoll()  // WS 通了就停轮询，失败再开
    ws.onmessage = (e) => {
      let msg: any
      try { msg = JSON.parse(e.data) } catch { return }
      if (msg.message) parseHint.value = msg.message
      if (msg.stage === 'parse_completed' || msg.stage === 'parse_error') {
        closeWs()
        stopPoll()
        load()
      }
    }
    ws.onerror = () => { startParsePoll() }
    ws.onclose = () => {
      if (set.value && (set.value.parse_status === 'pending' || set.value.parse_status === 'processing')) {
        startParsePoll()
      }
    }
  } catch { startParsePoll() }
}

function startParsePoll() {
  stopPoll()
  poll = window.setInterval(async () => {
    const st = await analysisApi.getStatus(setId)
    if (st.parse_status === 'done' || st.parse_status === 'failed') {
      stopPoll()
      await load()
    }
  }, 3000)
}

function stopPoll() {
  if (poll) { clearInterval(poll); poll = null }
}

function toggleAll(v: any) {
  checked.clear()
  if (v) for (const q of questions.value) checked.add(q.id)
}
function toggleOne(id: number, v: any) {
  if (v) checked.add(id); else checked.delete(id)
}

function toggleReveal(q: AnalysisQuestion) {
  if (revealed.has(q.id)) { revealed.delete(q.id); return }
  revealed.add(q.id)
  if (q.analysis_html && !blobUrls[q.id]) {
    blobUrls[q.id] = createIframeBlob(q.analysis_html)
  }
}

async function startAnalyze() {
  const ids = [...checked]
  if (!ids.length) return
  analyzing.value = true
  progress.current = 0
  progress.total = ids.length
  progress.hint = '任务已提交...'
  try {
    const { task_id } = await analysisApi.analyze(setId, ids)
    connectWs(task_id)
    startAnalyzePoll()
  } catch {
    analyzing.value = false
  }
}

function connectWs(taskId: string) {
  closeWs()
  try {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${proto}://${location.host}/api/v1/ws/task/${taskId}`)
    ws.onopen = () => stopPoll()
    ws.onmessage = (e) => {
      let msg: any
      try { msg = JSON.parse(e.data) } catch { return }
      if (msg.total) progress.total = msg.total
      if (typeof msg.current === 'number') progress.current = msg.current
      if (msg.stage === 'processing') progress.hint = `正在解析第 ${msg.seq} 题...`
      if (msg.stage === 'completed') { onAnalyzeDone() }
      if (msg.stage === 'error') { ElMessage.error(msg.message || '解析失败'); onAnalyzeDone() }
    }
    ws.onerror = () => { if (analyzing.value) startAnalyzePoll() }
    ws.onclose = () => { if (analyzing.value) startAnalyzePoll() }
  } catch { startAnalyzePoll() }
}

function closeWs() {
  if (ws) { try { ws.close() } catch { /* noop */ } ws = null }
}

// 轮询兜底：WebSocket 不可用时也能感知完成
function startAnalyzePoll() {
  stopPoll()
  poll = window.setInterval(async () => {
    const st = await analysisApi.getStatus(setId)
    const a = st.analysis
    progress.total = a.pending + a.processing + a.done + a.failed || progress.total
    progress.current = a.done + a.failed
    if (a.pending === 0 && a.processing === 0 && progress.total > 0) {
      onAnalyzeDone()
    }
  }, 4000)
}

async function onAnalyzeDone() {
  if (!analyzing.value) return
  analyzing.value = false
  stopPoll()
  closeWs()
  // 重新加载并刷新已展开的图解
  for (const k of Object.keys(blobUrls)) { URL.revokeObjectURL(blobUrls[Number(k)]); delete blobUrls[Number(k)] }
  const prevRevealed = new Set(revealed)
  await load()
  // 保持展开态，并为新生成的 html 重建 blob
  for (const q of questions.value) {
    if (prevRevealed.has(q.id)) {
      revealed.add(q.id)
      if (q.analysis_html) blobUrls[q.id] = createIframeBlob(q.analysis_html)
    }
  }
  ElMessage.success('AI 解析完成')
}

async function saveToBank() {
  const ids = [...checked]
  if (!ids.length) return
  const res = await analysisApi.saveToBank(setId, ids)
  ElMessage.success(`已入库 ${res.count} 道题`)
}

async function exportFile(format: 'docx' | 'pdf') {
  const blob = (await analysisApi.exportFile(setId, format)) as any as Blob
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${set.value?.name || '试题分析'}.${format}`
  a.click()
  URL.revokeObjectURL(url)
}

function statusLabel(s: string) {
  return { pending: '待解析', processing: '解析中', done: '已就绪', failed: '解析失败' }[s] || s
}
function typeLabel(t: string) {
  return {
    single_choice: '单选', multi_choice: '多选', fill_blank: '填空',
    short_answer: '简答', essay: '论述', true_false: '判断', calculation: '计算',
  }[t] || t
}

onMounted(load)
onBeforeUnmount(() => {
  stopPoll()
  closeWs()
  for (const k of Object.keys(blobUrls)) URL.revokeObjectURL(blobUrls[Number(k)])
})
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
</style>
