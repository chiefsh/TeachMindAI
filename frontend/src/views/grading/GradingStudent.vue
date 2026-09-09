<template>
  <div class="page">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between mb-4">
      <div class="flex items-center gap-2 flex-wrap">
        <el-button link type="primary" @click="$router.push(`/grading/${assignmentId}`)">← 学生列表</el-button>
        <h1 class="page-title !mb-0">{{ detail?.student_name }}　<span class="text-sm font-normal text-slate-500">{{ detail?.student_no }}</span></h1>
        <el-tag v-if="detail" size="small" :type="detail.paper_type === 'exam' ? 'danger' : 'primary'">
          {{ detail.assignment_title }}
        </el-tag>
      </div>
      <div class="flex items-center gap-2">
        <el-button size="small" :disabled="!prevId" @click="goPeer(prevId)">上一位</el-button>
        <el-button size="small" :disabled="!nextId" @click="goPeer(nextId)">下一位</el-button>
      </div>
    </div>

    <div v-if="detail?.paper_type === 'exam' && detail.full_score != null" class="card !py-3 mb-4">
      <span class="text-sm text-slate-600">
        得分
        <b class="text-primary-600 text-lg mx-1">{{ detail.total_score ?? '—' }}</b>
        / {{ detail.full_score }}
        · 已批 {{ gradedCount }}/{{ detail.questions.length }}
      </span>
    </div>

    <div class="grid lg:grid-cols-2 gap-4 items-start">
      <!-- 原卷 -->
      <div class="card">
        <div class="flex items-center justify-between mb-3">
          <p class="text-sm font-medium text-slate-700">纸质原卷</p>
          <span class="text-xs text-slate-400">{{ pageIndex + 1 }} / {{ pages.length || 0 }}</span>
        </div>
        <el-upload
          drag
          multiple
          accept="image/*,.pdf"
          :show-file-list="false"
          :http-request="uploadOne"
          :disabled="uploading || !detail"
        >
          <p class="text-sm text-slate-500 py-2">拍照或扫描上传（支持多图 / PDF）</p>
        </el-upload>
        <div v-if="currentPage" class="mt-3">
          <el-image
            :src="currentPage.url"
            :preview-src-list="pages.map(p => p.url)"
            :initial-index="pageIndex"
            fit="contain"
            class="w-full bg-slate-100 rounded-lg min-h-[280px] max-h-[70vh]"
          />
          <div class="flex items-center justify-between mt-2">
            <el-button size="small" :disabled="pageIndex <= 0" @click="pageIndex--">上一页</el-button>
            <el-button size="small" link type="danger" @click="removePage(currentPage.id)">删除本页</el-button>
            <el-button size="small" :disabled="pageIndex >= pages.length - 1" @click="pageIndex++">下一页</el-button>
          </div>
        </div>
        <p v-else class="text-center text-xs text-slate-400 mt-4">尚未上传原卷</p>
      </div>

      <!-- 题目 -->
      <div class="card max-h-[calc(100vh-8rem)] overflow-y-auto">
        <p class="text-sm font-medium text-slate-700 mb-3">逐题批改（对照左侧原卷）</p>
        <div v-for="(q, i) in detail?.questions || []" :key="q.id" class="border-b border-slate-100 py-3 last:border-0">
          <p class="text-sm text-slate-800 leading-relaxed">
            <span class="font-medium">{{ i + 1 }}.</span>
            <span class="math-text" v-html="renderMathText(q.content)" />
            <span v-if="isExam && q.score" class="text-xs text-slate-400">（{{ q.score }} 分）</span>
          </p>
          <div v-if="q.options" class="mt-1 ml-4 space-y-0.5">
            <p v-for="(val, key) in q.options" :key="key" class="text-xs text-slate-600">
              {{ key }}. <span v-html="renderMathText(String(val))" />
            </p>
          </div>
          <p class="text-xs text-green-700 mt-1 ml-4">
            参考答案：<span v-html="renderMathText(q.answer || '—')" />
          </p>
          <div class="flex flex-wrap items-center gap-1.5 mt-2 ml-4">
            <el-button
              v-for="v in verdicts"
              :key="v.value"
              size="small"
              :type="answerOf(q.id)?.verdict === v.value ? v.type : 'default'"
              @click="setVerdict(q.id, v.value)"
            >{{ v.label }}</el-button>
            <el-input-number
              v-if="isExam && answerOf(q.id)?.verdict === 'partial'"
              size="small"
              :min="0"
              :max="Number(q.score || 0)"
              :model-value="answerOf(q.id)?.score ?? 0"
              @change="(n: number) => setVerdict(q.id, 'partial', n)"
              style="width:110px"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { gradingApi } from '@/api/modules'
import { renderMathText } from '@/utils/mathText'
import type { GradeVerdict, GradingAnswer, GradingSubmission } from '@/types'

const route = useRoute()
const router = useRouter()
const detail = ref<GradingSubmission | null>(null)
const uploading = ref(false)
const pageIndex = ref(0)
const saving = ref(false)

const assignmentId = computed(() => Number(route.params.id))
const studentId = computed(() => Number(route.params.studentId))
const pages = computed(() => detail.value?.pages || [])
const currentPage = computed(() => pages.value[pageIndex.value] || null)
const isExam = computed(() => detail.value?.paper_type === 'exam')
const gradedCount = computed(() => (detail.value?.answers || []).filter(a => a.verdict).length)

const rosterIds = computed(() => (detail.value?.roster || []).map(s => s.student_id))
const prevId = computed(() => {
  const i = rosterIds.value.indexOf(studentId.value)
  return i > 0 ? rosterIds.value[i - 1] : 0
})
const nextId = computed(() => {
  const i = rosterIds.value.indexOf(studentId.value)
  return i >= 0 && i < rosterIds.value.length - 1 ? rosterIds.value[i + 1] : 0
})

const verdicts: { value: GradeVerdict; label: string; type: 'success' | 'warning' | 'danger' | 'info' }[] = [
  { value: 'correct', label: '对', type: 'success' },
  { value: 'partial', label: '半对', type: 'warning' },
  { value: 'wrong', label: '错', type: 'danger' },
  { value: 'blank', label: '未做', type: 'info' },
]

function answerOf(pqid: number): GradingAnswer | undefined {
  return detail.value?.answers.find(a => a.paper_question_id === pqid)
}

async function load() {
  detail.value = await gradingApi.getSubmission(assignmentId.value, studentId.value)
  pageIndex.value = 0
}

function goPeer(id: number) {
  if (!id) return
  router.push(`/grading/${assignmentId.value}/student/${id}`)
}

async function uploadOne(opt: { file: File }) {
  if (!detail.value) return
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('files', opt.file)
    detail.value = await gradingApi.uploadPages(detail.value.id, fd)
    pageIndex.value = Math.max(0, (detail.value.pages?.length || 1) - 1)
  } catch {
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
  }
}

async function removePage(pageId: number) {
  if (!detail.value) return
  detail.value = await gradingApi.deletePage(detail.value.id, pageId)
  pageIndex.value = Math.min(pageIndex.value, Math.max(0, pages.value.length - 1))
}

async function setVerdict(pqid: number, verdict: GradeVerdict, score?: number) {
  if (!detail.value || saving.value) return
  saving.value = true
  try {
    const payload: Record<string, unknown> = { paper_question_id: pqid, verdict, page_index: pageIndex.value }
    if (score != null) payload.score = score
    detail.value = await gradingApi.gradeAnswers(detail.value.id, [payload])
  } finally {
    saving.value = false
  }
}

watch(() => [route.params.id, route.params.studentId], load, { immediate: true })
</script>
