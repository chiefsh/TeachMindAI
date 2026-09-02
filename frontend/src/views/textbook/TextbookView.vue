<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4 sm:mb-6">
      <div>
        <h1 class="page-title">课本管理</h1>
        <p class="page-subtitle">管理上传的课本文档，支持 PDF、Word、TXT、EPUB、MOBI 格式</p>
      </div>
      <el-button type="primary" :icon="Upload" @click="openUpload">上传课本</el-button>
    </div>

    <!-- 课本列表 -->
    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      <div v-for="tb in textbooks" :key="tb.id" class="card !p-4 group hover:shadow-md transition-shadow">
        <div class="flex items-start gap-3">
          <!-- 文件类型图标 -->
          <div class="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
            <span class="text-xs font-bold text-slate-500 uppercase">{{ tb.file_type }}</span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold text-slate-800 truncate">{{ tb.title }}</p>
            <p class="text-xs text-slate-400 mt-0.5 truncate">{{ tb.file_name }}</p>
            <div class="flex items-center flex-wrap gap-1.5 mt-2">
              <el-tag size="small" type="info">{{ edu.gradeName(tb.grade_id) || '未设置年级' }}</el-tag>
              <el-tag size="small" type="success">{{ edu.subjectName(tb.subject_id) || '未设置科目' }}</el-tag>
            </div>
            <div class="flex items-center gap-2 mt-2">
              <span :class="`badge badge-${tb.parse_status}`">
                {{ statusLabel(tb.parse_status) }}
              </span>
              <span class="text-xs text-slate-400">{{ formatSize(tb.file_size) }}</span>
              <span v-if="tb.total_pages" class="text-xs text-slate-400">{{ tb.total_pages }}页</span>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2 mt-3 pt-3 border-t border-slate-50">
          <el-button size="small" link :icon="View" @click="previewBook(tb)">预览</el-button>
          <el-button size="small" link :icon="List" @click="viewChapters(tb)">章节</el-button>
          <el-popconfirm
            title="重新解析将清空已有章节并重新提取内容，确定继续吗？"
            width="240"
            @confirm="reparseBook(tb)"
          >
            <template #reference>
              <el-button
                size="small"
                link
                :icon="Refresh"
                :loading="reparsingId === tb.id"
                :disabled="tb.parse_status === 'processing'"
              >重新解析</el-button>
            </template>
          </el-popconfirm>
          <div class="flex-1" />
          <el-button size="small" link type="danger" :icon="Delete" @click="confirmDeleteBook(tb)">删除</el-button>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="!loading && !textbooks.length" class="col-span-full">
        <el-empty description="暂无课本，点击右上角上传" />
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

    <!-- 上传弹窗 -->
    <el-dialog v-model="showUpload" title="上传课本" width="480px" :close-on-click-modal="false">
      <el-form :model="uploadForm" :rules="uploadRules" ref="uploadFormRef" label-width="80px">
        <el-form-item label="课本标题" prop="title">
          <el-input v-model="uploadForm.title" placeholder="如：人教版数学七年级上册" />
        </el-form-item>
        <el-form-item label="年级" prop="grade_id">
          <el-select v-model="uploadForm.grade_id" placeholder="选择年级" style="width:100%" @change="onUploadGradeChange">
            <el-option v-for="g in edu.sortedGrades" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="科目" prop="subject_id">
          <el-select
            v-model="uploadForm.subject_id"
            :placeholder="uploadForm.grade_id ? '选择科目' : '请先选择年级'"
            :disabled="!uploadForm.grade_id"
            style="width:100%"
          >
            <el-option v-for="s in edu.subjectsOfGrade(uploadForm.grade_id)" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件" prop="file">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".pdf,.doc,.docx,.txt,.epub,.mobi"
            :on-change="onUploadFileChange"
          >
            <el-button :icon="Upload">选择文件</el-button>
            <template #tip>
              <p class="text-xs text-slate-400 mt-1">支持 PDF / Word / TXT / EPUB / MOBI，大小不超过 500MB</p>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUpload = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">上传</el-button>
      </template>
    </el-dialog>

    <!-- 章节弹窗：左目录，右 PDF 预览 -->
    <el-dialog
      v-model="showChapters"
      :title="`章节目录 - ${currentBook?.title}`"
      width="92vw"
      top="4vh"
      class="chapter-preview-dialog"
      destroy-on-close
      @closed="resetChapterPreview"
    >
      <div class="flex flex-col lg:flex-row gap-3 min-h-[68vh]">
        <div class="lg:w-[320px] lg:flex-shrink-0 lg:max-h-[68vh] overflow-y-auto rounded-xl border border-slate-100 bg-slate-50/70 p-2">
          <el-tree
            :data="chapters"
            node-key="id"
            :props="{ label: 'title', children: 'children' }"
            :expand-on-click-node="false"
            highlight-current
            :current-node-key="activeChapterId || undefined"
            @node-click="onChapterClick"
          >
            <template #default="{ data }">
              <span
                class="text-sm flex items-center gap-2 flex-1 min-w-0 pr-1 cursor-pointer"
                :class="data.id === activeChapterId ? 'text-primary-600 font-medium' : 'text-slate-700'"
              >
                <span class="truncate">{{ data.title }}</span>
                <span v-if="data.page_start" class="text-xs text-slate-400 flex-shrink-0">
                  p{{ data.page_start }}{{ data.page_end !== data.page_start ? `-${data.page_end}` : '' }}
                </span>
              </span>
            </template>
          </el-tree>
        </div>

        <div class="flex-1 min-w-0 flex flex-col rounded-xl border border-slate-100 bg-white overflow-hidden">
          <div class="flex items-center gap-2 px-3 py-2 border-b border-slate-100">
            <span class="text-sm text-slate-600 truncate flex-1">
              {{ activeChapterTitle || '点击左侧章节预览对应页' }}
            </span>
            <el-button
              v-if="previewUrl && viewerPage"
              size="small"
              link
              :icon="View"
              @click="openPreviewPage"
            >新窗口打开</el-button>
          </div>
          <div class="flex-1 min-h-[56vh] bg-slate-50 relative">
            <div v-if="previewLoading" class="absolute inset-0 flex items-center justify-center">
              <el-icon class="is-loading text-slate-400" :size="28"><Loading /></el-icon>
            </div>
            <iframe
              v-else-if="currentBook?.file_type === 'pdf' && viewerSrc"
              :key="viewerKey"
              :src="viewerSrc"
              class="w-full h-full min-h-[56vh] border-0"
              title="课本预览"
            />
            <div v-else class="absolute inset-0 flex items-center justify-center px-6">
              <p class="text-sm text-slate-400 text-center">
                {{ previewHint }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { textbookApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, View, List, Delete, Refresh, Loading } from '@element-plus/icons-vue'
import type { Textbook, Chapter } from '@/types'
import { isBusyStatus, useBusyPoll } from '@/utils/busyPoll'

const edu = useEducationStore()
const textbooks = ref<Textbook[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = 12
const showUpload = ref(false)
const showChapters = ref(false)
const chapters = ref<Chapter[]>([])
const currentBook = ref<Textbook | null>(null)
const previewUrl = ref('')
const previewLoading = ref(false)
const activeChapterId = ref<number | null>(null)
const activeChapterTitle = ref('')
const viewerPage = ref<number | null>(null)
const viewerKey = ref(0)
const uploading = ref(false)
const reparsingId = ref<number | null>(null)
const uploadFormRef = ref()
const uploadForm = reactive({ title: '', grade_id: null as number | null, subject_id: null as number | null, file: null as File | null })
const uploadRules = {
  title: [{ required: true, message: '请填写课本标题' }],
  grade_id: [{ required: true, message: '请选择年级' }],
  subject_id: [{ required: true, message: '请选择科目' }],
}

function onUploadGradeChange() {
  // 切换年级后，已选科目可能不属于新年级所在学段，清空重选
  uploadForm.subject_id = null
}

function onUploadFileChange(f: { name?: string; raw?: File }) {
  uploadForm.file = f.raw ?? null
  const name = (f.raw?.name || f.name || "").trim()
  if (!name) return
  const stem = name.replace(/\.[^.]+$/, "").trim()
  if (!stem) return
  uploadForm.title = stem
  uploadFormRef.value?.clearValidate?.('title')
}

function openUpload() {
  // 默认带入顶部全局选择的年级/科目
  uploadForm.title = ''
  uploadForm.file = null
  uploadForm.grade_id = edu.selectedGradeId || null
  uploadForm.subject_id = edu.selectedSubjectId || null
  uploadRef.value?.clearFiles?.()
  showUpload.value = true
}

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const res = await textbookApi.list({
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
      page: page.value, page_size: pageSize,
    }) as any
    textbooks.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
    busyPoll.sync()
  }
}

const busyPoll = useBusyPoll(
  () => load(true),
  () => textbooks.value.some(t => isBusyStatus(t.parse_status)),
)

// 顶部全局年级/科目变化时自动刷新
watchDebounced(() => [edu.selectedGradeId, edu.selectedSubjectId], () => { page.value = 1; load() }, { debounce: 250 })

async function handleUpload() {
  await uploadFormRef.value?.validate()
  if (!uploadForm.file) { ElMessage.warning('请选择文件'); return }
  if (uploadForm.file.size > 500 * 1024 * 1024) {
    ElMessage.warning('文件过大，最大支持 500MB')
    return
  }
  const fd = new FormData()
  fd.append('file', uploadForm.file)
  fd.append('title', uploadForm.title)
  fd.append('grade_id', String(uploadForm.grade_id))
  fd.append('subject_id', String(uploadForm.subject_id))
  uploading.value = true
  try {
    await textbookApi.upload(fd)
    ElMessage.success('上传成功，正在后台解析')
    showUpload.value = false
    uploadForm.title = ''
    uploadForm.file = null
    uploadRef.value?.clearFiles?.()
    await load()
  } finally {
    uploading.value = false
  }
}

function chapterStartPage(ch: Chapter): number | null {
  if (ch.page_start) return ch.page_start
  for (const child of ch.children || []) {
    const p = chapterStartPage(child)
    if (p) return p
  }
  return null
}

const viewerSrc = computed(() => {
  if (!previewUrl.value || !viewerPage.value) return ''
  const base = previewUrl.value.split('#')[0]
  return `${base}#page=${viewerPage.value}`
})

const previewHint = computed(() => {
  if (currentBook.value && currentBook.value.file_type !== 'pdf') {
    return '当前文件不是 PDF，无法按页预览。请使用「预览」在新窗口打开原文。'
  }
  if (!previewUrl.value) return '未能获取预览地址，请稍后重试或使用「预览」打开。'
  return '点击左侧章节，右侧将跳转到对应页。'
})

function jumpToPage(page: number) {
  viewerPage.value = page
  viewerKey.value += 1
}

function onChapterClick(data: Chapter) {
  activeChapterId.value = data.id
  activeChapterTitle.value = data.title
  const page = chapterStartPage(data)
  if (!page) {
    ElMessage.info('该章节没有页码，无法定位')
    return
  }
  if (currentBook.value?.file_type !== 'pdf' || !previewUrl.value) return
  jumpToPage(page)
}

function openPreviewPage() {
  if (viewerSrc.value) window.open(viewerSrc.value, '_blank')
}

function resetChapterPreview() {
  chapters.value = []
  currentBook.value = null
  previewUrl.value = ''
  previewLoading.value = false
  activeChapterId.value = null
  activeChapterTitle.value = ''
  viewerPage.value = null
}

async function previewBook(tb: Textbook) {
  const res = await textbookApi.getPreviewUrl(tb.id)
  window.open(res.url, '_blank')
}

async function viewChapters(tb: Textbook) {
  currentBook.value = tb
  chapters.value = []
  previewUrl.value = ''
  viewerPage.value = null
  activeChapterId.value = null
  activeChapterTitle.value = ''
  showChapters.value = true
  previewLoading.value = true
  try {
    const [chs, preview] = await Promise.all([
      textbookApi.getChapters(tb.id),
      tb.file_type === 'pdf' ? textbookApi.getPreviewUrl(tb.id) : Promise.resolve(null),
    ])
    chapters.value = chs
    if (preview) previewUrl.value = preview.url
    const first = chs[0]
    if (first && preview) onChapterClick(first)
  } catch {
    ElMessage.error('加载章节或预览地址失败')
  } finally {
    previewLoading.value = false
  }
}

async function confirmDeleteBook(tb: Textbook) {
  let related = { courseware: 0, homework: 0, questions: 0 }
  try {
    related = await textbookApi.relatedCounts(tb.id)
  } catch {
    // 数量查询失败仍继续二次确认，避免挡删除
  }
  const summary = [
    `课件 ${related.courseware} 个`,
    `作业/试卷 ${related.homework} 份`,
    `试题 ${related.questions} 道`,
  ].join('、')
  try {
    await ElMessageBox.confirm(
      `即将删除课本「${tb.title}」。\n关联的 ${summary} 都会被一并删除，且无法恢复。`,
      '删除课本',
      {
        type: 'warning',
        confirmButtonText: '继续删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      },
    )
    await ElMessageBox.confirm(
      '请再次确认：此操作不可撤销。确定删除该课本及全部关联课件、作业和试题吗？',
      '二次确认',
      {
        type: 'error',
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch {
    return
  }
  await deleteBook(tb.id)
}

async function deleteBook(id: number) {
  await textbookApi.delete(id)
  ElMessage.success('已删除')
  await load()
}

async function reparseBook(tb: Textbook) {
  reparsingId.value = tb.id
  try {
    await textbookApi.reparse(tb.id)
    ElMessage.success('已重新触发解析')
    await load()
  } finally {
    reparsingId.value = null
  }
}

function statusLabel(s: string) {
  return { pending: '待解析', processing: '解析中', done: '已解析', failed: '解析失败' }[s] || s
}

function formatSize(bytes: number) {
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1024 / 1024).toFixed(1) + 'MB'
}

onMounted(load)
</script>

<style scoped>
:deep(.el-dialog__body) {
  padding-top: 8px;
  padding-bottom: 16px;
}
</style>
