<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4 sm:mb-6">
      <div>
        <h1 class="page-title">试题分析</h1>
        <p class="page-subtitle">导入试题，AI 图解式解析，帮助学生更直观地掌握每道题</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openImport">导入试题</el-button>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      <div v-for="s in sets" :key="s.id"
        class="card !p-4 hover:shadow-md transition-shadow cursor-pointer"
        @click="router.push(`/question-analysis/${s.id}`)"
      >
        <div class="flex items-start gap-3">
          <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 bg-indigo-50">
            <el-icon class="text-xl text-indigo-500"><DataAnalysis /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold text-slate-800 truncate">{{ s.name }}</p>
            <div class="flex items-center flex-wrap gap-1.5 mt-1.5">
              <el-tag size="small" type="info">{{ edu.gradeName(s.grade_id) }}</el-tag>
              <el-tag size="small" type="success">{{ edu.subjectName(s.subject_id) }}</el-tag>
            </div>
            <div class="flex items-center flex-wrap gap-2 mt-1.5">
              <span :class="`badge badge-${s.parse_status}`">{{ statusLabel(s.parse_status) }}</span>
              <span class="text-xs text-slate-400">{{ s.question_count }} 题</span>
              <span class="text-xs text-slate-400">{{ formatDate(s.created_at) }}</span>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2 mt-3 pt-3 border-t border-slate-50" @click.stop>
          <el-button size="small" link :icon="View" @click="router.push(`/question-analysis/${s.id}`)">查看解析</el-button>
          <el-button
            v-if="s.parse_status === 'done' && s.question_count"
            size="small" link :icon="Share"
            @click="openShare(s)"
          >分享</el-button>
          <el-popconfirm
            v-if="s.source_type !== 'manual'"
            title="重新解析将清空已拆题目并重新拆题，确定继续吗？"
            width="240"
            @confirm="reparse(s)"
          >
            <template #reference>
              <el-button
                size="small" link :icon="Refresh"
                :loading="reparsingId === s.id"
                :disabled="s.parse_status === 'processing'"
              >重新解析</el-button>
            </template>
          </el-popconfirm>
          <div class="flex-1" />
          <el-popconfirm title="确定删除该试题批次？" @confirm="del(s.id)">
            <template #reference>
              <el-button size="small" link type="danger" :icon="Delete">删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
      <div v-if="!loading && !sets.length" class="col-span-full">
        <el-empty description="还没有试题，点击右上角导入" />
      </div>
    </div>

    <div v-if="total > pageSize" class="mt-4 flex justify-end">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="load"
      />
    </div>

    <!-- 导入弹窗 -->
    <el-dialog v-model="showImport" title="导入试题" width="620px" :close-on-click-modal="false">
      <el-form :model="form" label-width="90px">
        <el-form-item label="年级">
          <el-select v-model="form.grade_id" placeholder="选择年级" style="width:100%" @change="onGradeChange">
            <el-option v-for="g in edu.filteredGrades" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="学科">
          <el-select v-model="form.subject_id" placeholder="请先选择年级" style="width:100%"
            :disabled="!form.grade_id">
            <el-option v-for="s in edu.subjectsOfGrade(form.grade_id)" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="试题名称">
          <el-input v-model="form.name" placeholder="留空则默认：年级_学科_时间" />
        </el-form-item>
        <el-form-item label="导入方式">
          <el-radio-group v-model="form.mode">
            <el-radio value="manual">富文本录入</el-radio>
            <el-radio value="file">文件导入</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.mode === 'manual'" label="试题内容">
          <RichEditor ref="editorRef" v-model="form.html"
            @update:text="(t: string) => form.text = t"
            placeholder="在此输入或粘贴试题，可一道或多道..." />
        </el-form-item>
        <el-form-item v-else label="上传文件">
          <el-upload
            drag :auto-upload="false" :limit="1"
            :on-change="onFileChange" :on-remove="() => (file = null)"
            accept=".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png,.webp"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文件到此，或 <em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">支持 pdf / doc / docx / txt / 图片，导入后自动用 AI 拆题</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showImport = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">开始导入</el-button>
      </template>
    </el-dialog>

    <ShareDialog
      v-model="showShare"
      resource-type="question_analysis"
      :resource-id="shareTarget?.id || 0"
      :resource-title="shareTarget?.name"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { useRouter } from 'vue-router'
import { analysisApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { ElMessage } from 'element-plus'
import { Plus, View, Delete, DataAnalysis, UploadFilled, Refresh, Share } from '@element-plus/icons-vue'
import ShareDialog from '@/components/ShareDialog.vue'
import type { AnalysisSet } from '@/types'
import { isBusyStatus, useBusyPoll } from '@/utils/busyPoll'
import RichEditor from '@/components/RichEditor.vue'
import dayjs from 'dayjs'

const router = useRouter()
const edu = useEducationStore()
const sets = ref<AnalysisSet[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = 12
const showShare = ref(false)
const shareTarget = ref<AnalysisSet | null>(null)
const showImport = ref(false)
const submitting = ref(false)
const reparsingId = ref<number | null>(null)
const editorRef = ref()
const file = ref<File | null>(null)
const form = reactive({
  grade_id: null as number | null, subject_id: null as number | null,
  name: '', mode: 'manual' as 'manual' | 'file', html: '', text: '',
})

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const res = await analysisApi.list({
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
      page: page.value, page_size: pageSize,
    }) as any
    sets.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
    busyPoll.sync()
  }
}

const busyPoll = useBusyPoll(
  () => load(true),
  () => sets.value.some(s => isBusyStatus(s.parse_status)),
)

watchDebounced(() => [edu.selectedGradeId, edu.selectedSubjectId], () => { page.value = 1; load() }, { debounce: 250 })

function openShare(s: AnalysisSet) {
  shareTarget.value = s
  showShare.value = true
}

function openImport() {
  form.grade_id = edu.selectedGradeId || null
  // 仅当全局科目属于该年级学段时才预填，避免带入不匹配的学科
  const validSubjects = edu.subjectsOfGrade(form.grade_id).map(s => s.id)
  form.subject_id = validSubjects.includes(edu.selectedSubjectId as number)
    ? edu.selectedSubjectId
    : null
  form.name = ''
  form.mode = 'manual'
  form.html = ''
  form.text = ''
  file.value = null
  editorRef.value?.clear?.()
  showImport.value = true
}

// 年级变化时清空已选学科，保证学科与年级联动
function onGradeChange() {
  form.subject_id = null
}

function onFileChange(f: any) { file.value = f.raw }

async function submit() {
  if (!form.grade_id || !form.subject_id) {
    ElMessage.warning('请选择年级和学科')
    return
  }
  submitting.value = true
  try {
    if (form.mode === 'manual') {
      const text = (editorRef.value?.getText?.() || form.text || '').trim()
      if (!text) { ElMessage.warning('请输入试题内容'); return }
      const s = await analysisApi.importManual({
        text, grade_id: form.grade_id, subject_id: form.subject_id,
        name: form.name || undefined,
      }) as any
      ElMessage.success('导入成功')
      showImport.value = false
      router.push(`/question-analysis/${s.id}`)
    } else {
      if (!file.value) { ElMessage.warning('请上传文件'); return }
      const fd = new FormData()
      fd.append('file', file.value)
      fd.append('grade_id', String(form.grade_id))
      fd.append('subject_id', String(form.subject_id))
      if (form.name) fd.append('name', form.name)
      const s = await analysisApi.importFile(fd) as any
      ElMessage.success('文件已上传，正在后台解析')
      showImport.value = false
      router.push(`/question-analysis/${s.id}`)
    }
  } finally { submitting.value = false }
}

async function del(id: number) {
  await analysisApi.delete(id)
  ElMessage.success('已删除')
  await load()
}

async function reparse(s: AnalysisSet) {
  reparsingId.value = s.id
  try {
    await analysisApi.reparse(s.id)
    ElMessage.success('已重新提交解析')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '重新解析失败')
  } finally {
    reparsingId.value = null
  }
}

function statusLabel(s: string) {
  return { pending: '待解析', processing: '解析中', done: '已就绪', failed: '解析失败' }[s] || s
}
function formatDate(d: string) { return dayjs(d).format('MM-DD HH:mm') }

onMounted(load)
</script>
