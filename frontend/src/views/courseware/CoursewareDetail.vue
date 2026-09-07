<template>
  <div class="page">
    <div class="flex items-center gap-3 mb-6">
      <el-button link :icon="ArrowLeft" @click="router.back()">返回</el-button>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-1.5 min-w-0">
          <h1 class="page-title truncate">{{ cw?.title }}</h1>
          <el-button
            v-if="cw"
            link
            :icon="EditPen"
            class="!px-1"
            title="重命名"
            @click="renameCw"
          />
          <el-button
            v-if="cw"
            link
            :icon="CopyDocument"
            class="!px-1"
            title="复制课件"
            :loading="copying"
            @click="copyCw"
          />
        </div>
        <div class="flex items-center gap-2 mt-1">
          <span v-if="cw" :class="`badge badge-${cw.gen_status}`">{{ statusLabel(cw?.gen_status) }}</span>
          <el-tag size="small" :type="isWebStyle ? 'primary' : 'info'">
            {{ isWebStyle ? '网页样式' : 'PPT 样式' }}
          </el-tag>
          <el-tag v-if="cw?.is_interactive" size="small" type="warning">互动课件</el-tag>
          <span class="inline-flex items-center gap-1.5 text-xs text-slate-500">
            <span class="w-3 h-3 rounded-full" :style="{ background: themeGradient }" />
            {{ theme.label }}
          </span>
        </div>
      </div>
      <!-- 操作：与课件的呈现样式对应，主按钮为该样式的默认打开方式 -->
      <div v-if="cw?.gen_status === 'done' && slides.length" class="flex items-center gap-2">
        <el-button :type="isWebStyle ? 'primary' : ''" :icon="Monitor" @click="openLessonPage">网页预览</el-button>
        <el-button :type="isWebStyle ? '' : 'primary'" :icon="VideoPlay" @click="openPresent">演示模式</el-button>
        <el-button :icon="Connection" @click="openInteraction">课堂互动</el-button>
        <el-button-group>
          <el-button :loading="downloadingPage" :icon="Link" @click="downloadLessonPage">下载 HTML</el-button>
          <el-button :loading="exporting === 'pptx'" :icon="Download" @click="doExport('pptx')">导出 PPT</el-button>
        </el-button-group>
      </div>
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
        <div class="w-52 flex-shrink-0 flex flex-col gap-2 max-h-[calc(100vh-160px)]">
          <div class="flex-1 overflow-y-auto flex flex-col gap-2 pr-0.5">
            <div
              v-for="(slide, i) in slides" :key="i"
              class="p-2.5 rounded-lg border-2 cursor-pointer transition-all text-xs"
              :class="activeSlide === i ? 'border-primary-500 bg-primary-50' : 'border-slate-100 bg-white hover:border-slate-300'"
              @click="selectSlide(i)"
            >
              <div class="flex items-center gap-1.5">
                <span class="text-slate-400">{{ i + 1 }}</span>
                <el-tag size="small" :type="slideTypeTag(slide.type)">{{ typeLabel(slide.type) }}</el-tag>
                <el-icon v-if="slide.edit_status === 'processing'" class="text-primary-500 animate-spin ml-auto"><Loading /></el-icon>
                <span v-else-if="slide.edit_status === 'failed'" class="ml-auto w-1.5 h-1.5 rounded-full bg-red-500" title="优化失败" />
              </div>
              <p class="font-medium text-slate-700 truncate mt-1">{{ slide.title || `第 ${i+1} 页` }}</p>
            </div>
          </div>
          <el-button size="small" :icon="Plus" :disabled="structureLocked" @click="insertSlide()">插入页面</el-button>
        </div>

        <!-- 幻灯片预览 / 编辑 -->
        <div class="flex-1 card min-h-[520px] flex flex-col relative">
          <div
            v-if="currentBusy"
            class="absolute inset-0 z-10 bg-white/80 rounded-xl flex flex-col items-center justify-center"
          >
            <el-icon class="text-4xl text-primary-500 animate-spin mb-2"><Loading /></el-icon>
            <p class="text-sm text-slate-600 font-medium">AI 正在优化本页…</p>
            <p class="text-xs text-slate-400 mt-1">整课状态不受影响，可先看其他页</p>
          </div>

          <div v-if="currentSlide" class="flex-1">
            <div class="flex items-start gap-2 mb-4 pb-4 border-b border-slate-100">
              <span class="text-xs text-slate-400 mt-2">{{ activeSlide + 1 }} / {{ slides.length }}</span>
              <el-tag size="small" class="mt-1.5" :type="slideTypeTag(currentSlide.type)">{{ typeLabel(currentSlide.type) }}</el-tag>
              <div class="ml-1 min-w-0 flex-1">
                <h2 class="text-lg font-bold text-slate-800 truncate">{{ currentSlide.title }}</h2>
                <p v-if="currentSlide.subtitle" class="text-sm text-slate-500 truncate">{{ currentSlide.subtitle }}</p>
              </div>
              <div class="flex items-center gap-1 flex-shrink-0">
                <el-button size="small" :type="panelMode === 'edit' ? 'primary' : ''" :icon="EditPen" @click="toggleEdit">编辑</el-button>
                <el-button size="small" :type="panelMode === 'ai' ? 'primary' : ''" :icon="MagicStick" @click="toggleAi">AI 优化</el-button>
                <el-button size="small" :icon="ArrowUp" :disabled="structureLocked || activeSlide === 0" title="上移" @click="moveSlide(-1)" />
                <el-button size="small" :icon="ArrowDown" :disabled="structureLocked || activeSlide === slides.length - 1" title="下移" @click="moveSlide(1)" />
                <el-button size="small" :icon="Delete" :disabled="structureLocked || slides.length <= 1" title="删除本页" @click="removeSlide" />
              </div>
            </div>

            <!-- 编辑表单 -->
            <div v-if="panelMode === 'edit'" class="space-y-3">
              <div class="grid grid-cols-2 gap-3">
                <el-select v-model="draft.type" size="small" class="w-full" @change="markDirty">
                  <el-option v-for="k in pageKinds" :key="k" :label="typeLabel(k)" :value="k" />
                </el-select>
                <el-input v-model="draft.subtitle" size="small" placeholder="副标题（可选）" @input="markDirty" />
              </div>
              <el-input v-model="draft.title" placeholder="页面标题" @input="markDirty" />
              <div>
                <p class="text-xs text-slate-500 mb-1">要点（每行一条）</p>
                <el-input v-model="draft.bulletsText" type="textarea" :rows="4" placeholder="每行一条要点" @input="markDirty" />
              </div>
              <div>
                <p class="text-xs text-slate-500 mb-1">正文（支持 Markdown）</p>
                <el-input v-model="draft.content" type="textarea" :rows="8" @input="markDirty" />
              </div>
              <div v-if="showExampleFields" class="grid grid-cols-1 gap-3">
                <el-input v-model="draft.prompt" type="textarea" :rows="2" placeholder="题干 / 情境" @input="markDirty" />
                <el-input v-model="draft.solution" type="textarea" :rows="3" placeholder="解析 / 答案" @input="markDirty" />
              </div>
              <div>
                <p class="text-xs text-slate-500 mb-1">教师讲稿</p>
                <el-input v-model="draft.notes" type="textarea" :rows="3" @input="markDirty" />
              </div>
              <p v-if="currentSlide.html" class="text-xs text-slate-400">互动 HTML 请用「AI 优化 → 重做互动页」重新生成，不在此处手改。</p>
              <div class="flex justify-end gap-2">
                <el-button size="small" @click="cancelEdit">取消</el-button>
                <el-button size="small" type="primary" :loading="saving" :disabled="!dirty" @click="saveSlide">保存本页</el-button>
              </div>
            </div>

            <!-- AI 优化 -->
            <div v-else-if="panelMode === 'ai'" class="space-y-3">
              <el-radio-group v-model="optMode" size="small">
                <el-radio-button value="rewrite">改写</el-radio-button>
                <el-radio-button value="shorten">精简</el-radio-button>
                <el-radio-button value="expand">扩充</el-radio-button>
                <el-radio-button value="examples">补例子</el-radio-button>
                <el-radio-button value="notes">只改讲稿</el-radio-button>
                <el-radio-button value="interactive">重做互动页</el-radio-button>
              </el-radio-group>
              <el-input
                v-model="optInstruction"
                type="textarea"
                :rows="3"
                placeholder="可选：补充要求，例如「语气再口语一点」「加一道选择题」"
              />
              <div class="flex justify-end">
                <el-button type="primary" :icon="MagicStick" :loading="optimizing" @click="runOptimize">开始优化本页</el-button>
              </div>
            </div>

            <!-- 只读预览 -->
            <template v-else>
              <ul v-if="currentSlide.bullets?.length" class="mb-4 space-y-1.5">
                <li v-for="(b, i) in currentSlide.bullets" :key="i" class="flex gap-2 text-slate-700">
                  <span class="text-primary-500 mt-0.5">▸</span><span>{{ b }}</span>
                </li>
              </ul>
              <div
                v-if="currentSlide.content"
                class="prose prose-sm max-w-none text-slate-700 leading-relaxed cw-content"
                v-html="renderMarkdown(currentSlide.content)"
              ></div>
              <div v-if="slideImages(currentSlide).length" class="mt-4 flex flex-wrap gap-3">
                <img
                  v-for="url in slideImages(currentSlide)" :key="url"
                  :src="url"
                  class="max-h-56 rounded-lg border border-slate-200 object-contain bg-slate-50"
                />
              </div>
              <div v-if="currentSlide.html" class="mt-5">
                <div class="flex items-center justify-between mb-2">
                  <p class="text-xs font-semibold text-violet-600">互动动画 / 可视化</p>
                  <el-button size="small" text :icon="FullScreen" @click="openFullscreen(currentSlide.html)">全屏</el-button>
                </div>
                <iframe
                  v-if="currentBlobUrl"
                  :src="currentBlobUrl"
                  sandbox="allow-scripts"
                  class="w-full h-[460px] rounded-lg border border-slate-200 bg-white"
                ></iframe>
              </div>
              <div v-if="currentSlide.notes" class="mt-6 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <p class="text-xs font-semibold text-amber-700 mb-1">教师讲稿 / 备注</p>
                <p class="text-sm text-amber-800 whitespace-pre-wrap">{{ currentSlide.notes }}</p>
              </div>
            </template>
          </div>

          <div class="flex items-center justify-between pt-4 border-t border-slate-100 mt-4">
            <el-button :disabled="activeSlide === 0" @click="selectSlide(activeSlide - 1)" :icon="ArrowLeft">上一页</el-button>
            <el-button :disabled="activeSlide === slides.length - 1" @click="selectSlide(activeSlide + 1)" type="primary">
              下一页<el-icon class="ml-1"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </template>

    <!-- 互动全屏预览 -->
    <el-dialog v-model="showFs" title="互动预览" width="92%" top="4vh" :destroy-on-close="true">
      <iframe
        v-if="fsBlobUrl"
        :src="fsBlobUrl"
        sandbox="allow-scripts"
        class="w-full rounded-lg border border-slate-200 bg-white"
        style="height:78vh"
      ></iframe>
    </el-dialog>

    <!-- 网页课件预览 -->
    <el-dialog v-model="showPage" width="94%" top="2vh" :destroy-on-close="true">
      <template #header>
        <div class="flex items-center gap-3">
          <span class="font-semibold">网页课件预览</span>
          <span class="text-xs text-slate-400 flex-1">单页滚动阅读 · 左侧目录跳转 · 可下载为独立 HTML 分享给学生</span>
          <el-button size="small" :loading="downloadingPage" :icon="Link" @click="downloadLessonPage">下载 HTML</el-button>
        </div>
      </template>
      <iframe
        v-if="pageBlobUrl"
        :src="pageBlobUrl"
        sandbox="allow-scripts allow-popups allow-modals"
        class="w-full rounded-lg border border-slate-200 bg-white"
        style="height:86vh"
      ></iframe>
    </el-dialog>

    <!-- 演示模式（reveal.js） -->
    <el-dialog v-model="showPresent" title="" width="98%" top="1vh" :destroy-on-close="true" class="present-dialog">
      <template #header>
        <div class="flex items-center gap-3">
          <span class="font-semibold">演示模式</span>
          <span class="text-xs text-slate-400 flex-1">方向键/空格翻页 · 按 F 全屏 · 按 S 打开演讲者视图（含讲稿） · 内容超长可在页内滚动</span>
          <el-button size="small" :icon="FullScreen" @click="fullscreenDeck">全屏演示</el-button>
        </div>
      </template>
      <iframe
        v-if="deckBlobUrl"
        ref="deckIframe"
        :src="deckBlobUrl"
        sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox"
        class="w-full rounded-lg border border-slate-200 bg-white"
        style="height:90vh"
      ></iframe>
    </el-dialog>

    <!-- 课堂互动 -->
    <el-dialog v-model="showInteraction" title="课堂互动" width="90%" top="4vh" :destroy-on-close="true">
      <el-tabs v-model="interactionTab">
        <!-- 分享作答 -->
        <el-tab-pane label="分享作答" name="share">
          <div class="flex items-center justify-between mb-3">
            <p class="text-sm text-slate-500">为本课件开启互动会话，把链接发给学生，学生用手机/平板打开即可作答。</p>
            <el-button type="primary" :icon="Plus" :loading="creatingSession" @click="createSession">新建互动会话</el-button>
          </div>
          <el-table :data="sessions" size="small" empty-text="暂无互动会话">
            <el-table-column label="名称" prop="title" min-width="160" show-overflow-tooltip />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.is_open ? 'success' : 'info'">{{ row.is_open ? '进行中' : '已关闭' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="参与" width="80">
              <template #default="{ row }">{{ row.student_count }} 人</template>
            </el-table-column>
            <el-table-column label="作答数" width="80" prop="record_count" />
            <el-table-column label="操作" width="320">
              <template #default="{ row }">
                <el-button size="small" :icon="CopyDocument" @click="copyLink(row)">复制链接</el-button>
                <el-button size="small" :icon="DataAnalysis" @click="openBoard(row)">数据看板</el-button>
                <el-button size="small" @click="toggleSession(row)">{{ row.is_open ? '关闭' : '开启' }}</el-button>
                <el-button size="small" type="danger" :icon="Delete" @click="removeSession(row)" />
              </template>
            </el-table-column>
          </el-table>
          <div v-if="shareLink" class="mt-4 p-3 bg-slate-50 rounded-lg border border-slate-200 flex gap-4 items-center">
            <img v-if="shareQr" :src="shareQr" alt="二维码" class="w-32 h-32 rounded-lg border border-slate-200 bg-white" />
            <div class="flex-1">
              <p class="text-xs text-slate-500 mb-1">学生扫码或打开链接即可作答</p>
              <div class="flex items-center gap-2">
                <el-input :model-value="shareLink" readonly size="small" />
                <el-button size="small" type="primary" @click="copyText(shareLink)">复制</el-button>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 数据看板 -->
        <el-tab-pane label="数据看板" name="board">
          <div v-if="!board" class="text-center text-slate-400 py-10">请在「分享作答」中选择一个会话查看数据看板</div>
          <div v-else>
            <div class="flex gap-4 mb-4">
              <div class="card flex-1 text-center py-3">
                <p class="text-2xl font-bold text-primary-600">{{ board.summary.student_count }}</p>
                <p class="text-xs text-slate-400">参与学生</p>
              </div>
              <div class="card flex-1 text-center py-3">
                <p class="text-2xl font-bold text-emerald-600">{{ board.summary.total_records }}</p>
                <p class="text-xs text-slate-400">作答次数</p>
              </div>
              <div class="card flex-1 text-center py-3">
                <p class="text-2xl font-bold text-amber-600">{{ overallRate }}%</p>
                <p class="text-xs text-slate-400">整体正确率</p>
              </div>
              <el-button class="self-center" :icon="Refresh" @click="refreshBoard">刷新</el-button>
            </div>

            <p class="text-sm font-semibold text-slate-700 mb-2">题目正确率</p>
            <el-table :data="board.questions" size="small" class="mb-5" empty-text="暂无作答数据">
              <el-table-column label="位置" width="70">
                <template #default="{ row }">第 {{ row.slide_index + 1 }} 页</template>
              </el-table-column>
              <el-table-column label="题目/操作" prop="question" min-width="200" show-overflow-tooltip />
              <el-table-column label="作答" width="70" prop="attempts" />
              <el-table-column label="正确率" width="160">
                <template #default="{ row }">
                  <div class="flex items-center gap-2">
                    <el-progress :percentage="row.correct_rate" :stroke-width="10" class="flex-1"
                      :color="rateColor(row.correct_rate)" />
                  </div>
                </template>
              </el-table-column>
            </el-table>

            <p class="text-sm font-semibold text-slate-700 mb-2">学生表现</p>
            <el-table :data="board.students" size="small" max-height="240" empty-text="暂无作答数据">
              <el-table-column label="姓名" prop="name" min-width="120" />
              <el-table-column label="作答" width="80" prop="attempts" />
              <el-table-column label="正确" width="80" prop="correct" />
              <el-table-column label="正确率" width="100">
                <template #default="{ row }">{{ row.correct_rate }}%</template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <el-dialog v-model="showInsert" title="插入页面" width="400px">
      <p class="text-sm text-slate-500 mb-3">新页会插在当前页后面，保存后再用 AI 优化或手写内容。</p>
      <el-select v-model="insertType" class="w-full">
        <el-option v-for="k in pageKinds" :key="k" :label="typeLabel(k)" :value="k" />
      </el-select>
      <template #footer>
        <el-button @click="showInsert = false">取消</el-button>
        <el-button type="primary" :loading="inserting" @click="confirmInsert">插入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { coursewareApi, textbookApi, interactionApi } from '@/api/modules'
import {
  ArrowLeft, ArrowRight, ArrowUp, ArrowDown, Loading, CircleClose, Download, FullScreen,
  VideoPlay, Connection, Plus, CopyDocument, DataAnalysis, Delete, Refresh, EditPen,
  Monitor, Link, MagicStick,
} from '@element-plus/icons-vue'
import QRCode from 'qrcode'
import { createIframeBlob } from '@/utils/coursewareFrame'
import { buildRevealDeck } from '@/utils/revealDeck'
import { buildLessonPage } from '@/utils/lessonPage'
import { getTheme } from '@/utils/coursewareTheme'
import { pageTypeLabel, PAGE_KINDS, normalizePageKind } from '@/utils/coursewarePages'
import { useEducationStore } from '@/stores/education'
import { renderMarkdown } from '@/utils/markdown'
import type { Courseware, CoursewareSession, SessionBoard } from '@/types'

const route = useRoute()
const router = useRouter()
const edu = useEducationStore()
const cw = ref<Courseware | null>(null)
const activeSlide = ref(0)
const exporting = ref<string>('')
const copying = ref(false)
const imageMap = ref<Record<string, string>>({})
const showFs = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null
let optTimer: ReturnType<typeof setInterval> | null = null

type PanelMode = 'view' | 'edit' | 'ai'
const panelMode = ref<PanelMode>('view')
const pageKinds = PAGE_KINDS
const dirty = ref(false)
const saving = ref(false)
const optimizing = ref(false)
const optMode = ref('rewrite')
const optInstruction = ref('')
const showInsert = ref(false)
const insertType = ref('knowledge')
const inserting = ref(false)
const draft = ref({
  type: 'knowledge',
  title: '',
  subtitle: '',
  bulletsText: '',
  content: '',
  notes: '',
  prompt: '',
  solution: '',
})

// ──────────────────────────────────────────────────
// Blob URL 统一管理：避免 srcdoc 内嵌 script 标签被浏览器解析器截断的 bug
// ──────────────────────────────────────────────────
const _blobUrls: string[] = []
function makeBlobUrl(html: string): string {
  const url = createIframeBlob(html)
  _blobUrls.push(url)
  return url
}

// 当前 slide 的互动 iframe blob url（由 watch 维护，见下方）
const currentBlobUrl = ref('')

// 全屏预览
const fsBlobUrl = ref('')

// 演示模式
const showPresent = ref(false)
const deckBlobUrl = ref('')
const deckIframe = ref<HTMLIFrameElement | null>(null)
function openPresent() {
  if (deckBlobUrl.value) { URL.revokeObjectURL(deckBlobUrl.value) }
  deckBlobUrl.value = makeBlobUrl(
    buildRevealDeck(cw.value?.content, imageMap.value, {
      theme: cw.value?.theme,
      subject: cw.value?.subject_id ? edu.subjectName(cw.value.subject_id) : '',
    })
  )
  showPresent.value = true
}

function fullscreenDeck() {
  const el = deckIframe.value as any
  if (!el) return
  const req = el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen
  if (req) req.call(el)
}

// 网页样式课件：单页滚动网页，可预览也可下载为独立 HTML
const showPage = ref(false)
const pageBlobUrl = ref('')
const downloadingPage = ref(false)
const isWebStyle = computed(() => cw.value?.render_style === 'html')
const theme = computed(() => getTheme(cw.value?.theme))
const themeGradient = computed(() => `linear-gradient(135deg, ${theme.value.coverFrom}, ${theme.value.coverTo})`)

function lessonPageHtml(images: Record<string, string> = imageMap.value): string {
  const ctx = [
    cw.value?.grade_id ? edu.gradeName(cw.value.grade_id) : '',
    cw.value?.subject_id ? edu.subjectName(cw.value.subject_id) : '',
  ].filter(Boolean).join(' · ')
  return buildLessonPage(cw.value?.content, images, {
    subtitle: ctx,
    theme: cw.value?.theme,
    subject: cw.value?.subject_id ? edu.subjectName(cw.value.subject_id) : '',
  })
}

function openLessonPage() {
  if (pageBlobUrl.value) { URL.revokeObjectURL(pageBlobUrl.value) }
  // 预览用带时效的 URL 即可，无需为此把图片全量内联
  pageBlobUrl.value = makeBlobUrl(lessonPageHtml())
  showPage.value = true
}

/** 下载的 HTML 会脱离平台长期保存，图片改为内联 base64，避免 presigned URL 过期后丢图。 */
async function downloadLessonPage() {
  downloadingPage.value = true
  try {
    const ids = referencedImageIds()
    let images = imageMap.value
    if (ids.length) {
      try {
        const inlined = (await textbookApi.resolveImagesInline(ids)) as any as Record<string, string>
        images = { ...imageMap.value, ...inlined }
        const missing = ids.filter((id) => !inlined[String(id)])
        if (missing.length) {
          ElMessage.warning(`有 ${missing.length} 张图片体积过大未内联，离线保存后可能无法显示`)
        }
      } catch {
        ElMessage.warning('图片内联失败，已改用临时链接，链接过期后图片会失效')
      }
    }

    const blob = new Blob([lessonPageHtml(images)], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${cw.value?.title || '网页课件'}.html`
    a.click()
    URL.revokeObjectURL(url)
  } finally {
    downloadingPage.value = false
  }
}

// 课堂互动
const showInteraction = ref(false)
const interactionTab = ref('share')
const sessions = ref<CoursewareSession[]>([])
const creatingSession = ref(false)
const shareLink = ref('')
const shareQr = ref('')
const board = ref<SessionBoard | null>(null)
const currentBoardSession = ref<number | null>(null)

function sessionUrl(token: string) {
  return `${window.location.origin}/s/${token}`
}

async function setShare(token: string) {
  shareLink.value = sessionUrl(token)
  try {
    shareQr.value = await QRCode.toDataURL(shareLink.value, { width: 256, margin: 1 })
  } catch { shareQr.value = '' }
}

async function openInteraction() {
  showInteraction.value = true
  interactionTab.value = 'share'
  shareLink.value = ''
  shareQr.value = ''
  await loadSessions()
}

async function loadSessions() {
  if (!cw.value) return
  try { sessions.value = await interactionApi.listSessions(cw.value.id) as any } catch { /* ignore */ }
}

async function createSession() {
  if (!cw.value) return
  creatingSession.value = true
  try {
    const s = await interactionApi.createSession(cw.value.id) as any as CoursewareSession
    await loadSessions()
    await setShare(s.token)
    ElMessage.success('已创建互动会话')
  } catch { /* handled */ } finally { creatingSession.value = false }
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}
async function copyLink(row: CoursewareSession) {
  await setShare(row.token)
  copyText(shareLink.value)
}

async function toggleSession(row: CoursewareSession) {
  try {
    await interactionApi.toggleSession(row.id, !row.is_open)
    await loadSessions()
  } catch { /* handled */ }
}

async function removeSession(row: CoursewareSession) {
  try {
    await ElMessageBox.confirm('确定删除该互动会话及其作答数据？', '提示', { type: 'warning' })
  } catch { return }
  try {
    await interactionApi.deleteSession(row.id)
    if (currentBoardSession.value === row.id) { board.value = null; currentBoardSession.value = null }
    await loadSessions()
    ElMessage.success('已删除')
  } catch { /* handled */ }
}

async function openBoard(row: CoursewareSession) {
  currentBoardSession.value = row.id
  interactionTab.value = 'board'
  await refreshBoard()
}

async function refreshBoard() {
  if (!currentBoardSession.value) return
  try { board.value = await interactionApi.board(currentBoardSession.value) as any } catch { /* handled */ }
}

const overallRate = computed(() => {
  const qs = board.value?.questions || []
  const attempts = qs.reduce((a, q) => a + q.attempts, 0)
  const correct = qs.reduce((a, q) => a + q.correct, 0)
  return attempts ? Math.round((correct / attempts) * 1000) / 10 : 0
})
function rateColor(rate: number) {
  if (rate >= 80) return '#16a34a'
  if (rate >= 60) return '#f59e0b'
  return '#dc2626'
}

function openFullscreen(html: string) {
  if (fsBlobUrl.value) { URL.revokeObjectURL(fsBlobUrl.value) }
  fsBlobUrl.value = createIframeBlob(html, cw.value?.theme)
  showFs.value = true
}

// 兜底：旧数据可能把整段 JSON 当成单页正文存了下来，这里尝试还原为结构化内容
const normalizedContent = computed<any>(() => {
  const c: any = cw.value?.content || {}
  const ss: any[] = c.slides || []
  if (ss.length === 1 && typeof ss[0]?.content === 'string') {
    let txt = ss[0].content.trim()
    if (txt.startsWith('```')) {
      txt = txt.replace(/^```[a-zA-Z]*\n?/, '').replace(/```$/, '').trim()
    }
    if (txt.startsWith('{') && txt.includes('"slides"')) {
      try {
        const parsed = JSON.parse(txt)
        if (parsed?.slides?.length) return parsed
      } catch { /* 无法解析则维持原样 */ }
    }
  }
  return c
})
const slides = computed<any[]>(() => normalizedContent.value?.slides || [])
const meta = computed<any>(() => normalizedContent.value?.meta || {})
const hasMeta = computed(() => !!(meta.value.objectives?.length || meta.value.key_points?.length || meta.value.difficulties?.length))
const currentSlide = computed(() => slides.value[activeSlide.value] || null)
const currentBusy = computed(() => currentSlide.value?.edit_status === 'processing')
const showExampleFields = computed(() => {
  const t = normalizePageKind(draft.value.type)
  return t === 'example' || t === 'exercise' || t === 'homework'
})
const structureLocked = computed(() =>
  sessions.value.some(s => s.is_open) || slides.value.some((s: any) => s.edit_status === 'processing'),
)

function markDirty() { dirty.value = true }

function syncDraft(s: any) {
  draft.value = {
    type: normalizePageKind(s?.type),
    title: s?.title || '',
    subtitle: s?.subtitle || '',
    bulletsText: (s?.bullets || []).join('\n'),
    content: s?.content || '',
    notes: s?.notes || '',
    prompt: s?.prompt || '',
    solution: s?.solution || '',
  }
  dirty.value = false
}

async function selectSlide(i: number) {
  if (i === activeSlide.value) return
  if (dirty.value) {
    try {
      await ElMessageBox.confirm('当前页有未保存的修改，切换将丢弃。', '提示', { type: 'warning' })
    } catch { return }
  }
  activeSlide.value = i
  panelMode.value = 'view'
  dirty.value = false
  if (currentSlide.value) syncDraft(currentSlide.value)
}

function toggleEdit() {
  if (panelMode.value === 'edit') {
    if (dirty.value) {
      ElMessageBox.confirm('放弃未保存的修改？', '提示', { type: 'warning' })
        .then(() => { panelMode.value = 'view'; dirty.value = false; if (currentSlide.value) syncDraft(currentSlide.value) })
        .catch(() => {})
      return
    }
    panelMode.value = 'view'
    return
  }
  if (currentSlide.value) syncDraft(currentSlide.value)
  panelMode.value = 'edit'
}

function toggleAi() {
  panelMode.value = panelMode.value === 'ai' ? 'view' : 'ai'
}

function cancelEdit() {
  if (currentSlide.value) syncDraft(currentSlide.value)
  panelMode.value = 'view'
}

function applySlide(index: number, slide: any) {
  if (!cw.value || !slide) return
  const content: any = { ...(cw.value.content || {}) }
  const arr = [...(content.slides || [])]
  if (!arr[index]) return
  arr[index] = slide
  content.slides = arr
  cw.value = { ...cw.value, content }
}

async function saveSlide() {
  if (!cw.value || !currentSlide.value) return
  saving.value = true
  try {
    const payload = {
      type: draft.value.type,
      title: draft.value.title,
      subtitle: draft.value.subtitle,
      bullets: draft.value.bulletsText.split('\n').map(t => t.trim()).filter(Boolean),
      content: draft.value.content,
      notes: draft.value.notes,
      prompt: draft.value.prompt,
      solution: draft.value.solution,
    }
    const res = await coursewareApi.patchSlide(cw.value.id, activeSlide.value, payload)
    applySlide(res.index, res.slide)
    dirty.value = false
    panelMode.value = 'view'
    ElMessage.success('本页已保存')
  } catch { /* interceptor */ } finally {
    saving.value = false
  }
}

function stopOptPoll() {
  if (optTimer) { clearInterval(optTimer); optTimer = null }
}

function startOptPoll(index: number) {
  stopOptPoll()
  optTimer = setInterval(async () => {
    if (!cw.value) return
    try {
      const st = await coursewareApi.getSlide(cw.value.id, index)
      applySlide(index, st.slide)
      const status = st.edit_status || st.slide?.edit_status
      if (status === 'processing' || status === 'pending') return
      stopOptPoll()
      optimizing.value = false
      if (status === 'failed') {
        ElMessage.error(st.slide?.edit_error || '本页 AI 优化失败')
      } else {
        ElMessage.success('本页已优化')
        panelMode.value = 'view'
        resolveImages()
      }
    } catch { /* 下次再试 */ }
  }, 2500)
}

async function runOptimize() {
  if (!cw.value) return
  optimizing.value = true
  try {
    const idx = activeSlide.value
    await coursewareApi.optimizeSlide(cw.value.id, idx, {
      instruction: optInstruction.value,
      mode: optMode.value,
    })
    applySlide(idx, { ...currentSlide.value, edit_status: 'processing' })
    startOptPoll(idx)
  } catch {
    optimizing.value = false
  }
}

async function insertSlide() {
  insertType.value = 'knowledge'
  showInsert.value = true
}

async function confirmInsert() {
  if (!cw.value) return
  inserting.value = true
  try {
    const index = activeSlide.value + 1
    const res = await coursewareApi.insertSlide(cw.value.id, { index, type: insertType.value })
    dirty.value = false
    showInsert.value = false
    await load()
    activeSlide.value = res.index
    panelMode.value = 'edit'
    if (currentSlide.value) syncDraft(currentSlide.value)
    ElMessage.success('已插入空白页，可直接编辑')
  } catch { /* interceptor */ } finally {
    inserting.value = false
  }
}

async function removeSlide() {
  if (!cw.value) return
  try {
    await ElMessageBox.confirm('确定删除当前页？此操作不可恢复。', '删除页面', { type: 'warning' })
  } catch { return }
  try {
    const idx = activeSlide.value
    await coursewareApi.deleteSlide(cw.value.id, idx)
    dirty.value = false
    await load()
    activeSlide.value = Math.min(idx, Math.max(0, slides.value.length - 1))
    panelMode.value = 'view'
    ElMessage.success('已删除')
  } catch { /* interceptor */ }
}

async function moveSlide(delta: number) {
  if (!cw.value) return
  const from = activeSlide.value
  const to = from + delta
  if (to < 0 || to >= slides.value.length) return
  const order = slides.value.map((_: any, i: number) => i)
  const [moved] = order.splice(from, 1)
  order.splice(to, 0, moved)
  try {
    await coursewareApi.reorderSlides(cw.value.id, order)
    dirty.value = false
    await load()
    activeSlide.value = to
  } catch { /* interceptor */ }
}

// 当 currentSlide.html 变化（切换 slide / 课件加载完成），刷新 Blob URL
watch(
  () => [currentSlide.value?.html, cw.value?.theme] as const,
  ([html]) => {
    if (currentBlobUrl.value) { URL.revokeObjectURL(currentBlobUrl.value); currentBlobUrl.value = '' }
    if (html) currentBlobUrl.value = createIframeBlob(html, cw.value?.theme)
  },
  { immediate: true }
)

function typeLabel(t: string) { return pageTypeLabel(t) }
function slideTypeTag(t: string): any {
  return ({
    title: 'primary', cover: 'primary', objectives: 'success', summary: 'success', homework: 'info',
    example: 'warning', interactive: 'warning', quiz: 'warning', exercise: 'info',
    comparison: 'warning', process: 'success', knowledge: 'info', content: 'info',
  } as Record<string, string>)[t] || 'info'
}

function slideImages(slide: any): string[] {
  return (slide?.images || [])
    .map((id: any) => imageMap.value[String(id)])
    .filter(Boolean)
}

function referencedImageIds(): number[] {
  const ids: number[] = []
  for (const s of slides.value) {
    for (const id of s.images || []) {
      const n = Number(id)
      if (!Number.isNaN(n)) ids.push(n)
    }
  }
  return [...new Set(ids)]
}

async function resolveImages() {
  const ids = referencedImageIds()
  if (!ids.length) return
  try {
    imageMap.value = (await textbookApi.resolveImages(ids)) as any
  } catch { /* 图片解析失败忽略 */ }
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
    startStatusPoll()
  } else {
    stopStatusPoll()
    if (cw.value?.gen_status === 'done') {
      resolveImages()
      loadSessions()
      const busyIdx = slides.value.findIndex((s: any) => s.edit_status === 'processing')
      if (busyIdx >= 0) startOptPoll(busyIdx)
    }
  }
}

async function renameCw() {
  if (!cw.value) return
  try {
    const { value } = await ElMessageBox.prompt('请输入新的课件名称', '重命名', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: cw.value.title,
      inputPattern: /\S/,
      inputErrorMessage: '名称不能为空',
    })
    const title = String(value || '').trim()
    if (!title || title === cw.value.title) return
    const updated = await coursewareApi.rename(cw.value.id, title)
    const keepSlide = activeSlide.value
    await load()
    if (cw.value) cw.value.title = updated.title
    activeSlide.value = keepSlide
    ElMessage.success('已重命名')
  } catch (e: any) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error('重命名失败，请稍后重试')
  }
}

async function copyCw() {
  if (!cw.value) return
  copying.value = true
  try {
    const copied = await coursewareApi.copy(cw.value.id)
    ElMessage.success(`已复制为「${copied.title}」`)
    router.push(`/courseware/${copied.id}`)
  } catch {
    ElMessage.error('复制失败，请稍后重试')
  } finally {
    copying.value = false
  }
}

/** 生成中只轮询轻量 status，完成后再拉一次完整详情，避免反复传输 slides/html */
function startStatusPoll() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    try {
      const st = await coursewareApi.getStatus(Number(route.params.id)) as any
      if (st.gen_status === 'done' || st.gen_status === 'failed') {
        stopStatusPoll()
        await load()
      } else if (cw.value) {
        cw.value.gen_status = st.gen_status
      }
    } catch { /* 下次再试 */ }
  }, 4000)
}
function stopStatusPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

function statusLabel(s?: string) {
  return ({ pending: '待生成', processing: '生成中', done: '已完成', failed: '生成失败' } as Record<string, string>)[s || ''] || s
}

onMounted(load)
onUnmounted(() => {
  stopStatusPoll()
  stopOptPoll()
  // 释放所有 Blob URL，防止内存泄漏
  ;[currentBlobUrl, fsBlobUrl, deckBlobUrl, pageBlobUrl].forEach(r => {
    if (r.value) { URL.revokeObjectURL(r.value); r.value = '' }
  })
  _blobUrls.forEach(u => URL.revokeObjectURL(u))
})
</script>

<style scoped>
.cw-content :deep(h3) { @apply text-base font-bold text-slate-800 mt-3 mb-1.5; }
.cw-content :deep(h4) { @apply text-sm font-semibold text-slate-700 mt-2 mb-1; }
.cw-content :deep(p) { @apply my-1.5; }
.cw-content :deep(ul) { @apply list-disc list-inside my-1.5 space-y-1; }
.cw-content :deep(code) { @apply px-1 py-0.5 bg-slate-100 rounded text-rose-600 text-xs; }
</style>
