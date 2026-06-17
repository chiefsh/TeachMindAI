<template>
  <div class="p-6">
    <div class="flex items-center gap-3 mb-6">
      <el-button link :icon="ArrowLeft" @click="router.back()">返回</el-button>
      <div class="flex-1">
        <h1 class="page-title">{{ cw?.title }}</h1>
        <div class="flex items-center gap-2 mt-1">
          <span v-if="cw" :class="`badge badge-${cw.gen_status}`">{{ statusLabel(cw?.gen_status) }}</span>
          <el-tag v-if="cw?.is_interactive" size="small" type="warning">互动课件</el-tag>
        </div>
      </div>
      <!-- 导出 -->
      <el-button-group v-if="cw?.gen_status === 'done' && slides.length">
        <el-button :loading="exporting === 'pptx'" :icon="Download" @click="doExport('pptx')">导出 PPT</el-button>
        <el-button :loading="exporting === 'docx'" :icon="Document" @click="doExport('docx')">导出 Word</el-button>
        <el-button :loading="exporting === 'pdf'" :icon="Tickets" @click="doExport('pdf')">导出 PDF</el-button>
      </el-button-group>
    </div>

    <!-- 生成中状态 -->
    <div v-if="cw?.gen_status === 'processing' || cw?.gen_status === 'pending'" class="card text-center py-16">
      <el-icon class="text-5xl text-primary-500 animate-spin mb-4"><Loading /></el-icon>
      <p class="text-slate-600 font-medium">AI 正在生成完整课件，请稍候...</p>
      <p class="text-sm text-slate-400 mt-1">生成一节完整教学内容通常需要 1 ~ 3 分钟</p>
    </div>

    <!-- 生成失败 -->
    <div v-else-if="cw?.gen_status === 'failed'" class="card text-center py-16">
      <el-icon class="text-5xl text-red-400 mb-4"><CircleClose /></el-icon>
      <p class="text-slate-600 font-medium">课件生成失败，请尝试重新生成</p>
    </div>

    <template v-else-if="slides.length">
      <!-- 课程概览 -->
      <div v-if="hasMeta" class="card mb-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div v-if="meta.objectives?.length">
          <p class="text-xs font-semibold text-primary-600 mb-1.5">教学目标</p>
          <ul class="text-sm text-slate-600 space-y-1 list-disc list-inside">
            <li v-for="(o, i) in meta.objectives" :key="i">{{ o }}</li>
          </ul>
        </div>
        <div v-if="meta.key_points?.length">
          <p class="text-xs font-semibold text-emerald-600 mb-1.5">教学重点</p>
          <ul class="text-sm text-slate-600 space-y-1 list-disc list-inside">
            <li v-for="(o, i) in meta.key_points" :key="i">{{ o }}</li>
          </ul>
        </div>
        <div v-if="meta.difficulties?.length">
          <p class="text-xs font-semibold text-rose-600 mb-1.5">教学难点</p>
          <ul class="text-sm text-slate-600 space-y-1 list-disc list-inside">
            <li v-for="(o, i) in meta.difficulties" :key="i">{{ o }}</li>
          </ul>
        </div>
      </div>

      <!-- 课件内容 -->
      <div class="flex gap-4">
        <!-- 幻灯片缩略图列表 -->
        <div class="w-52 flex-shrink-0 flex flex-col gap-2 overflow-y-auto max-h-[calc(100vh-160px)]">
          <div
            v-for="(slide, i) in slides" :key="i"
            class="p-2.5 rounded-lg border-2 cursor-pointer transition-all text-xs"
            :class="activeSlide === i ? 'border-primary-500 bg-primary-50' : 'border-slate-100 bg-white hover:border-slate-300'"
            @click="activeSlide = i"
          >
            <div class="flex items-center gap-1.5">
              <span class="text-slate-400">{{ i + 1 }}</span>
              <el-tag size="small" :type="slideTypeTag(slide.type)">{{ typeLabel(slide.type) }}</el-tag>
            </div>
            <p class="font-medium text-slate-700 truncate mt-1">{{ slide.title || `第 ${i+1} 页` }}</p>
          </div>
        </div>

        <!-- 幻灯片预览 -->
        <div class="flex-1 card min-h-[520px] flex flex-col">
          <div v-if="currentSlide" class="flex-1">
            <div class="flex items-center gap-2 mb-4 pb-4 border-b border-slate-100">
              <span class="text-xs text-slate-400">{{ activeSlide + 1 }} / {{ slides.length }}</span>
              <el-tag size="small" :type="slideTypeTag(currentSlide.type)">{{ typeLabel(currentSlide.type) }}</el-tag>
              <div class="ml-2">
                <h2 class="text-lg font-bold text-slate-800">{{ currentSlide.title }}</h2>
                <p v-if="currentSlide.subtitle" class="text-sm text-slate-500">{{ currentSlide.subtitle }}</p>
              </div>
            </div>

            <!-- 要点 -->
            <ul v-if="currentSlide.bullets?.length" class="mb-4 space-y-1.5">
              <li v-for="(b, i) in currentSlide.bullets" :key="i" class="flex gap-2 text-slate-700">
                <span class="text-primary-500 mt-0.5">▸</span><span>{{ b }}</span>
              </li>
            </ul>

            <!-- 正文（markdown） -->
            <div
              v-if="currentSlide.content"
              class="prose prose-sm max-w-none text-slate-700 leading-relaxed cw-content"
              v-html="renderMarkdown(currentSlide.content)"
            ></div>

            <!-- 课本插图 -->
            <div v-if="slideImages(currentSlide).length" class="mt-4 flex flex-wrap gap-3">
              <img
                v-for="url in slideImages(currentSlide)" :key="url"
                :src="url"
                class="max-h-56 rounded-lg border border-slate-200 object-contain bg-slate-50"
              />
            </div>

            <!-- HTML 互动动画 -->
            <div v-if="currentSlide.html" class="mt-5">
              <div class="flex items-center justify-between mb-2">
                <p class="text-xs font-semibold text-violet-600">互动动画 / 可视化</p>
                <el-button size="small" text :icon="FullScreen" @click="openFullscreen(currentSlide.html)">全屏</el-button>
              </div>
              <iframe
                :srcdoc="wrapInteractiveHtml(currentSlide.html)"
                sandbox="allow-scripts"
                class="w-full h-[460px] rounded-lg border border-slate-200 bg-white"
              ></iframe>
            </div>

            <!-- 教师讲稿 -->
            <div v-if="currentSlide.notes" class="mt-6 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <p class="text-xs font-semibold text-amber-700 mb-1">教师讲稿 / 备注</p>
              <p class="text-sm text-amber-800 whitespace-pre-wrap">{{ currentSlide.notes }}</p>
            </div>
          </div>

          <!-- 翻页 -->
          <div class="flex items-center justify-between pt-4 border-t border-slate-100 mt-4">
            <el-button :disabled="activeSlide === 0" @click="activeSlide--" :icon="ArrowLeft">上一页</el-button>
            <el-button :disabled="activeSlide === slides.length - 1" @click="activeSlide++" type="primary">
              下一页<el-icon class="ml-1"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </template>

    <!-- 互动全屏预览 -->
    <el-dialog v-model="showFs" title="互动预览" width="92%" top="4vh" :destroy-on-close="true">
      <iframe
        :srcdoc="fsHtml"
        sandbox="allow-scripts"
        class="w-full rounded-lg border border-slate-200 bg-white"
        style="height:78vh"
      ></iframe>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { coursewareApi, textbookApi } from '@/api/modules'
import { ArrowLeft, ArrowRight, Loading, CircleClose, Download, Document, Tickets, FullScreen } from '@element-plus/icons-vue'
import { wrapInteractiveHtml } from '@/utils/coursewareFrame'
import type { Courseware } from '@/types'

const route = useRoute()
const router = useRouter()
const cw = ref<Courseware | null>(null)
const activeSlide = ref(0)
const exporting = ref<string>('')
const imageMap = ref<Record<string, string>>({})
const showFs = ref(false)
const fsHtml = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null

function openFullscreen(html: string) {
  fsHtml.value = wrapInteractiveHtml(html)
  showFs.value = true
}

const slides = computed<any[]>(() => (cw.value?.content as any)?.slides || [])
const meta = computed<any>(() => (cw.value?.content as any)?.meta || {})
const hasMeta = computed(() => !!(meta.value.objectives?.length || meta.value.key_points?.length || meta.value.difficulties?.length))
const currentSlide = computed(() => slides.value[activeSlide.value] || null)

const TYPE_LABELS: Record<string, string> = {
  title: '封面', objectives: '教学目标', intro: '情境导入', content: '新知讲解',
  example: '例题精讲', activity: '课堂活动', interactive: '互动环节', summary: '课堂小结',
  homework: '课后作业', board: '板书设计', quiz: '随堂测验', exercise: '练习',
}
function typeLabel(t: string) { return TYPE_LABELS[t] || t || '内容' }
function slideTypeTag(t: string): any {
  return ({
    title: 'primary', objectives: 'success', summary: 'success', homework: 'info',
    example: 'warning', interactive: 'warning', quiz: 'warning', exercise: 'info',
  } as Record<string, string>)[t] || ''
}

function slideImages(slide: any): string[] {
  return (slide?.images || [])
    .map((id: any) => imageMap.value[String(id)])
    .filter(Boolean)
}

async function resolveImages() {
  const ids: number[] = []
  for (const s of slides.value) {
    for (const id of s.images || []) {
      const n = Number(id)
      if (!Number.isNaN(n)) ids.push(n)
    }
  }
  if (!ids.length) return
  try {
    imageMap.value = (await textbookApi.resolveImages([...new Set(ids)])) as any
  } catch { /* 图片解析失败忽略 */ }
}

// 极简 markdown 渲染（标题/加粗/斜体/行内代码/无序列表）
function renderMarkdown(src: string): string {
  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const lines = (src || '').split('\n')
  const html: string[] = []
  let inList = false
  const inline = (t: string) => esc(t)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
  for (const raw of lines) {
    const line = raw.trim()
    if (!line) { if (inList) { html.push('</ul>'); inList = false } continue }
    const h = line.match(/^(#{1,4})\s+(.*)$/)
    const li = line.match(/^[-*]\s+(.*)$/)
    if (h) {
      if (inList) { html.push('</ul>'); inList = false }
      const lvl = h[1].length + 2
      html.push(`<h${lvl}>${inline(h[2])}</h${lvl}>`)
    } else if (li) {
      if (!inList) { html.push('<ul>'); inList = true }
      html.push(`<li>${inline(li[1])}</li>`)
    } else {
      if (inList) { html.push('</ul>'); inList = false }
      html.push(`<p>${inline(line)}</p>`)
    }
  }
  if (inList) html.push('</ul>')
  return html.join('')
}

async function doExport(fmt: 'pptx' | 'docx' | 'pdf') {
  if (!cw.value) return
  exporting.value = fmt
  try {
    const blob = (await coursewareApi.exportFile(cw.value.id, fmt)) as unknown as Blob
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${cw.value.title}.${fmt}`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('导出失败，请稍后重试')
  } finally {
    exporting.value = ''
  }
}

async function load() {
  cw.value = (await coursewareApi.get(Number(route.params.id))) as any
  if (cw.value?.gen_status === 'processing' || cw.value?.gen_status === 'pending') {
    if (!pollTimer) pollTimer = setInterval(load, 5000)
  } else {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    if (cw.value?.gen_status === 'done') resolveImages()
  }
}

function statusLabel(s?: string) {
  return ({ pending: '待生成', processing: '生成中', done: '已完成', failed: '生成失败' } as Record<string, string>)[s || ''] || s
}

onMounted(load)
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped>
.cw-content :deep(h3) { @apply text-base font-bold text-slate-800 mt-3 mb-1.5; }
.cw-content :deep(h4) { @apply text-sm font-semibold text-slate-700 mt-2 mb-1; }
.cw-content :deep(p) { @apply my-1.5; }
.cw-content :deep(ul) { @apply list-disc list-inside my-1.5 space-y-1; }
.cw-content :deep(code) { @apply px-1 py-0.5 bg-slate-100 rounded text-rose-600 text-xs; }
</style>
