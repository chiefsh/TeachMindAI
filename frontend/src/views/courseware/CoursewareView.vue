<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4 sm:mb-6">
      <div>
        <h1 class="page-title">课件生成</h1>
        <p class="page-subtitle">基于课本章节，利用 AI 自动生成教学课件</p>
      </div>
      <el-button type="primary" :icon="MagicStick" @click="openCreate">生成课件</el-button>
    </div>

    <!-- 课件卡片列表 -->
    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      <div v-for="cw in coursewares" :key="cw.id"
        class="card !p-4 hover:shadow-md transition-shadow cursor-pointer"
        @click="router.push(`/courseware/${cw.id}`)"
      >
        <div class="flex items-start gap-3">
          <!-- 图标底色即课件主题色，列表里一眼可辨 -->
          <div
            class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
            :style="{ background: themeGradient(cw.theme) }"
          >
            <el-icon class="text-xl text-white"><VideoPlay /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold text-slate-800 truncate">{{ cw.title }}</p>
            <div class="flex items-center flex-wrap gap-1.5 mt-1.5">
              <el-tag v-if="cw.grade_id" size="small" type="info">{{ edu.gradeName(cw.grade_id) }}</el-tag>
              <el-tag v-if="cw.subject_id" size="small" type="success">{{ edu.subjectName(cw.subject_id) }}</el-tag>
            </div>
            <div class="flex items-center flex-wrap gap-2 mt-1.5">
              <span :class="`badge badge-${cw.gen_status}`">{{ statusLabel(cw.gen_status) }}</span>
              <el-tag size="small" :type="cw.render_style === 'html' ? 'primary' : 'info'">
                {{ cw.render_style === 'html' ? '网页样式' : 'PPT 样式' }}
              </el-tag>
              <el-tag v-if="cw.is_interactive" size="small" type="warning">互动</el-tag>
              <span class="text-xs text-slate-400">{{ formatDate(cw.created_at) }}</span>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2 mt-3 pt-3 border-t border-slate-50" @click.stop>
          <el-button size="small" link :icon="View" @click="router.push(`/courseware/${cw.id}`)">查看</el-button>
          <el-button
            v-if="cw.gen_status === 'done'"
            size="small" link :icon="Share"
            @click="openShare(cw)"
          >分享</el-button>
          <el-button size="small" link :icon="EditPen" @click="renameCw(cw)">重命名</el-button>
          <el-button
            size="small"
            link
            :icon="CopyDocument"
            :loading="copyingId === cw.id"
            @click="copyCw(cw)"
          >复制</el-button>
          <el-popconfirm
            title="重新生成将覆盖当前课件内容，确定继续吗？"
            width="240"
            @confirm="regenerateCw(cw)"
          >
            <template #reference>
              <el-button
                size="small"
                link
                :icon="RefreshRight"
                :loading="regeneratingId === cw.id"
                :disabled="cw.gen_status === 'processing'"
              >重新生成</el-button>
            </template>
          </el-popconfirm>
          <div class="flex-1" />
          <el-popconfirm title="确定删除该课件？关联的课堂互动会话将一并删除。" @confirm="deleteCw(cw.id)">
            <template #reference>
              <el-button size="small" link type="danger" :icon="Delete">删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
      <div v-if="!loading && !coursewares.length" class="col-span-full">
        <el-empty description="还没有课件，点击右上角生成" />
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

    <!-- 生成课件弹窗 -->
    <el-dialog v-model="showCreate" title="生成课件" width="560px" :close-on-click-modal="false">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="课件标题" prop="title">
          <el-input v-model="form.title" placeholder="如：第一章 春 — 精讲课件" />
        </el-form-item>
        <el-form-item label="关联课本">
          <el-select v-model="form.textbook_id" placeholder="选择课本（可选）" style="width:100%" clearable @change="onTextbookChange">
            <el-option v-for="tb in textbooks" :key="tb.id" :label="tb.title" :value="tb.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.textbook_id" label="生成范围">
          <el-radio-group v-model="form.gen_mode">
            <el-radio value="chapter">按章节</el-radio>
            <el-radio value="page">按页码</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.textbook_id && form.gen_mode === 'chapter'" label="选择章节">
          <el-select
            v-model="form.chapter_ids" multiple filterable collapse-tags collapse-tags-tooltip
            placeholder="可多选章节" style="width:100%" :loading="chaptersLoading"
            no-data-text="该课本暂无解析出的章节"
          >
            <el-option v-for="c in chapterOptions" :key="c.id" :label="c.label" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.textbook_id && form.gen_mode === 'page'" label="页码范围">
          <div class="flex items-center gap-2">
            <el-input-number v-model="form.page_start" :min="1" placeholder="起始页" style="width:120px" />
            <span class="text-slate-400">至</span>
            <el-input-number v-model="form.page_end" :min="1" placeholder="结束页" style="width:120px" />
          </div>
        </el-form-item>
        <el-form-item label="呈现样式">
          <div>
            <el-radio-group v-model="form.render_style">
              <el-radio value="ppt">PPT 样式</el-radio>
              <el-radio value="html">网页样式</el-radio>
            </el-radio-group>
            <p class="text-xs text-slate-400 mt-1 leading-relaxed">
              {{ form.render_style === 'ppt'
                ? '按页组织，支持演示模式与导出 PPT/Word/PDF，适合课堂讲授。'
                : '生成单页滚动网页，讲解更完整、可内嵌互动，适合学生自主阅读与分享。' }}
            </p>
          </div>
        </el-form-item>
        <el-form-item label="课件主题">
          <div class="flex flex-wrap gap-2">
            <button
              v-for="t in THEMES" :key="t.key" type="button"
              class="theme-swatch"
              :class="{ active: form.theme === t.key }"
              :title="t.label"
              :style="{ background: t.bg }"
              @click="form.theme = t.key"
            >
              <span class="theme-dot" :style="{ background: themeGradient(t.key) }" />
              <span>{{ t.label }}</span>
            </button>
          </div>
        </el-form-item>
        <el-form-item label="课件类型">
          <el-radio-group v-model="form.courseware_type">
            <el-radio value="standard">标准课件</el-radio>
            <el-radio value="interactive">互动课件</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="互动功能" v-if="form.courseware_type === 'interactive'">
          <el-checkbox-group v-model="form.interactive_features">
            <el-checkbox value="animation">教学动画</el-checkbox>
            <el-checkbox value="ai_companion">AI 伴学</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="教师想法">
          <el-input
            v-model="form.custom_prompt"
            type="textarea"
            :rows="3"
            placeholder="可以输入您的教学思路、重点难点要求等，AI 会结合您的想法生成课件..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" :icon="MagicStick" @click="handleCreate">
          开始生成
        </el-button>
      </template>
    </el-dialog>

    <ShareDialog
      v-model="showShare"
      resource-type="courseware"
      :resource-id="shareTarget?.id || 0"
      :resource-title="shareTarget?.title"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { useRouter } from 'vue-router'
import { coursewareApi, textbookApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, View, Delete, VideoPlay, RefreshRight, CopyDocument, EditPen, Share } from '@element-plus/icons-vue'
import ShareDialog from '@/components/ShareDialog.vue'
import type { Courseware, Textbook, Chapter, RenderStyle } from '@/types'
import { THEMES, DEFAULT_THEME, getTheme } from '@/utils/coursewareTheme'
import { isBusyStatus, useBusyPoll } from '@/utils/busyPoll'
import dayjs from 'dayjs'

const router = useRouter()
const edu = useEducationStore()
const coursewares = ref<Courseware[]>([])
const textbooks = ref<Textbook[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 12
const loading = ref(false)
const showShare = ref(false)
const shareTarget = ref<Courseware | null>(null)
const showCreate = ref(false)
const creating = ref(false)
const regeneratingId = ref<number | null>(null)
const copyingId = ref<number | null>(null)
const formRef = ref()
const chapterOptions = ref<{ id: number; label: string }[]>([])
const chaptersLoading = ref(false)
const form = reactive({
  title: '', textbook_id: null as number | null, courseware_type: 'standard',
  render_style: 'ppt' as RenderStyle,
  theme: DEFAULT_THEME,
  gen_mode: 'chapter' as 'chapter' | 'page',
  chapter_ids: [] as number[],
  page_start: null as number | null, page_end: null as number | null,
  custom_prompt: '', interactive_features: [] as string[], is_interactive: false,
})
const rules = { title: [{ required: true, message: '请填写课件标题' }] }

// 章节树可能含子节点，扁平化为「层级缩进 + 页码」的下拉项
function flattenChapters(list: Chapter[], depth = 0): { id: number; label: string }[] {
  const out: { id: number; label: string }[] = []
  for (const c of list || []) {
    const indent = '　'.repeat(depth)
    const pages = c.page_start ? `（P${c.page_start}${c.page_end && c.page_end !== c.page_start ? '-' + c.page_end : ''}）` : ''
    out.push({ id: c.id, label: `${indent}${c.title}${pages}` })
    if (c.children?.length) out.push(...flattenChapters(c.children, depth + 1))
  }
  return out
}

async function onTextbookChange() {
  form.chapter_ids = []
  form.page_start = null
  form.page_end = null
  chapterOptions.value = []
  if (!form.textbook_id) return
  chaptersLoading.value = true
  try {
    const data = (await textbookApi.getChapters(form.textbook_id)) as Chapter[]
    chapterOptions.value = flattenChapters(data)
  } finally {
    chaptersLoading.value = false
  }
}

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const res = await coursewareApi.list({
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
      page: page.value, page_size: pageSize,
    }) as any
    coursewares.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
    busyPoll.sync()
  }
}

const busyPoll = useBusyPoll(
  () => load(true),
  () => coursewares.value.some(c => isBusyStatus(c.gen_status)),
)

async function loadTextbooks() {
  const res = await textbookApi.list({
    grade_id: edu.selectedGradeId || undefined,
    subject_id: edu.selectedSubjectId || undefined,
    page: 1, page_size: 500,
  }) as any
  textbooks.value = res.items || []
}

function openCreate() {
  form.title = ''
  form.textbook_id = null
  form.courseware_type = 'standard'
  form.render_style = 'ppt'
  form.theme = DEFAULT_THEME
  form.gen_mode = 'chapter'
  form.chapter_ids = []
  form.page_start = null
  form.page_end = null
  form.custom_prompt = ''
  form.interactive_features = []
  chapterOptions.value = []
  showCreate.value = true
}

// 顶部全局年级/科目变化时同步刷新课件与可选课本
watchDebounced(() => [edu.selectedGradeId, edu.selectedSubjectId], () => { page.value = 1; load(); loadTextbooks() }, { debounce: 250 })

async function handleCreate() {
  await formRef.value?.validate()
  creating.value = true
  try {
    const payload: any = {
      title: form.title,
      textbook_id: form.textbook_id,
      courseware_type: form.courseware_type,
      render_style: form.render_style,
      theme: form.theme,
      custom_prompt: form.custom_prompt,
      is_interactive: form.courseware_type === 'interactive',
    }
    if (form.textbook_id) {
      if (form.gen_mode === 'chapter' && form.chapter_ids.length) {
        payload.chapter_range = { chapter_ids: form.chapter_ids }
      } else if (form.gen_mode === 'page' && form.page_start && form.page_end) {
        payload.page_range = { start: form.page_start, end: form.page_end }
      }
    }
    await coursewareApi.create(payload)
    ElMessage.success('课件生成任务已提交')
    showCreate.value = false
    await load()
  } finally { creating.value = false }
}

function openShare(cw: Courseware) {
  shareTarget.value = cw
  showShare.value = true
}

async function copyCw(cw: Courseware) {
  copyingId.value = cw.id
  try {
    const copied = await coursewareApi.copy(cw.id)
    ElMessage.success(`已复制为「${copied.title}」`)
    await load()
  } catch {
    ElMessage.error('复制失败，请稍后重试')
  } finally {
    copyingId.value = null
  }
}

async function renameCw(cw: Courseware) {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的课件名称', '重命名', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: cw.title,
      inputPattern: /\S/,
      inputErrorMessage: '名称不能为空',
    })
    const title = String(value || '').trim()
    if (!title || title === cw.title) return
    await coursewareApi.rename(cw.id, title)
    ElMessage.success('已重命名')
    await load()
  } catch (e: any) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error('重命名失败，请稍后重试')
  }
}

async function regenerateCw(cw: Courseware) {
  regeneratingId.value = cw.id
  try {
    await coursewareApi.regenerate(cw.id)
    ElMessage.success('已重新触发生成')
    await load()
  } finally {
    regeneratingId.value = null
  }
}

async function deleteCw(id: number) {
  await coursewareApi.delete(id)
  ElMessage.success('已删除')
  await load()
}

function themeGradient(key?: string) {
  const t = getTheme(key)
  return `linear-gradient(135deg, ${t.coverFrom}, ${t.coverTo})`
}

function statusLabel(s: string) {
  return { pending: '待生成', processing: '生成中', done: '已完成', failed: '生成失败' }[s] || s
}
function formatDate(d: string) { return dayjs(d).format('MM-DD HH:mm') }

onMounted(async () => {
  await load()
  await loadTextbooks()
})
</script>

<style scoped>
.theme-swatch {
  @apply flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200
         text-xs text-slate-600 transition-all hover:border-slate-300;
}
.theme-swatch.active {
  @apply border-primary-500 text-primary-700 font-medium;
}
.theme-dot {
  @apply w-4 h-4 rounded-full flex-shrink-0;
}
</style>
