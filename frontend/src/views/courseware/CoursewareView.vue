<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4 sm:mb-6">
      <div>
        <h1 class="page-title">课件生成</h1>
        <p class="page-subtitle">基于课本章节，利用 AI 自动生成教学课件</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <el-button v-if="auth.can('courseware.edit')" @click="openBatchCollab">批量设置协作者</el-button>
        <el-button v-if="auth.can('courseware.create')" type="primary" :icon="MagicStick" @click="openCreate">生成课件</el-button>
      </div>
    </div>

    <!-- 课件卡片列表 -->
    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      <div v-for="cw in coursewares" :key="cw.id"
        class="card !p-4 hover:shadow-md transition-shadow cursor-pointer overflow-hidden relative"
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
              <el-tag v-if="cw.want_virtual_lab" size="small" type="success">实验</el-tag>
              <span class="text-xs text-slate-400">{{ formatDate(cw.created_at) }}</span>
              <span v-if="cw.creator_name" class="text-xs text-slate-400">{{ cw.creator_name }}</span>
            </div>
          </div>
        </div>
        <div class="flex items-center justify-between gap-1 mt-3 pt-3 border-t border-slate-50 min-w-0" @click.stop>
          <div class="flex items-center gap-1 min-w-0">
            <el-button size="small" link :icon="View" @click="router.push(`/courseware/${cw.id}`)">查看</el-button>
            <el-button
              v-if="cw.gen_status === 'done'"
              size="small" link :icon="Share"
              @click="openShare(cw)"
            >分享</el-button>
          </div>
          <el-dropdown trigger="click" placement="bottom-end" @command="(cmd: string) => onCardMore(cw, cmd)">
            <el-button
              size="small"
              link
              :icon="MoreFilled"
              :loading="copyingId === cw.id || regeneratingId === cw.id"
            />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="canEditCw(cw)" command="rename" :icon="EditPen">重命名</el-dropdown-item>
                <el-dropdown-item v-if="auth.can('courseware.create')" command="copy" :icon="CopyDocument">复制</el-dropdown-item>
                <el-dropdown-item v-if="canEditCw(cw)" command="regen" :icon="RefreshRight" :disabled="!canRegenerate(cw)">
                  重新生成
                </el-dropdown-item>
                <el-dropdown-item v-if="canManageCw(cw)" command="delete" :icon="Delete" divided>删除</el-dropdown-item>
                <el-dropdown-item v-if="canManageCw(cw)" command="collab" :icon="User">协作者</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
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

    <!-- 生成 / 重新生成弹窗 -->
    <el-dialog v-model="showCreate" :title="regenId ? '重新生成课件' : '生成课件'" width="560px" :close-on-click-modal="false">
      <p v-if="regenId" class="text-xs text-amber-600 mb-3 -mt-1">
        将按下方配置重新生成，并覆盖当前课件内容。
      </p>
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
        <el-form-item v-if="form.courseware_type === 'interactive'" label="虚拟实验">
          <el-checkbox v-model="form.want_virtual_lab">生成可操作的宏观实验台</el-checkbox>
          <p class="text-xs text-slate-400 mt-1">化学/科学课：选仪器、加药品、点燃或滴加、观察现象、安全操作。未指定实验时按本章内容匹配。</p>
          <el-select
            v-if="form.want_virtual_lab"
            v-model="form.virtual_lab_key"
            class="mt-2 w-full"
            placeholder="根据本章内容自动匹配"
            clearable
          >
            <el-option-group v-for="g in labGroups" :key="g.label" :label="g.label">
              <el-option
                v-for="item in g.items"
                :key="item.key"
                :value="item.key"
                :label="item.title"
              />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="教师想法">
          <el-input
            v-model="form.custom_prompt"
            type="textarea"
            :rows="3"
            placeholder="例如：多讲易错点、例题要分层、互动用生活情境、作业只要基础题……这些想法会贯穿知识点、讲解、互动和练习"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" :icon="MagicStick" @click="handleCreate">
          {{ regenId ? '重新生成' : '开始生成' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showCopy" title="复制课件" width="440px" :close-on-click-modal="false" @opened="focusCopyInput">
      <p class="text-sm text-slate-600 mb-2">复制后的课件名称</p>
      <el-input
        ref="copyInputRef"
        v-model="copyTitle"
        maxlength="256"
        show-word-limit
        placeholder="请输入课件名称"
        @keyup.enter="confirmCopy"
      />
      <template #footer>
        <el-button @click="showCopy = false">取消</el-button>
        <el-button type="primary" :loading="copyLoading" @click="confirmCopy">确认</el-button>
      </template>
    </el-dialog>

    <ShareDialog
      v-model="showShare"
      resource-type="courseware"
      :resource-id="shareTarget?.id || 0"
      :resource-title="shareTarget?.title"
    />
    <CollaboratorsDialog
      v-model="showCollab"
      resource-type="courseware"
      :options="collabOptions"
      :selected-ids="collabIds"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick, watch, computed } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { useRouter, useRoute } from 'vue-router'
import { coursewareApi, textbookApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, View, Delete, VideoPlay, RefreshRight, CopyDocument, EditPen, Share, MoreFilled, User } from '@element-plus/icons-vue'
import ShareDialog from '@/components/ShareDialog.vue'
import CollaboratorsDialog from '@/components/CollaboratorsDialog.vue'
import type { Courseware, Textbook, Chapter, RenderStyle, LabExperiment } from '@/types'
import { THEMES, DEFAULT_THEME, getTheme } from '@/utils/coursewareTheme'
import { isBusyStatus, useBusyPoll } from '@/utils/busyPoll'
import dayjs from 'dayjs'

const router = useRouter()
const route = useRoute()
const edu = useEducationStore()
const auth = useAuthStore()
const coursewares = ref<Courseware[]>([])
const textbooks = ref<Textbook[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 12
const loading = ref(false)
const showShare = ref(false)
const shareTarget = ref<Courseware | null>(null)
const showCollab = ref(false)
const collabIds = ref<number[]>([])
const collabOptions = computed(() =>
  coursewares.value.filter(c => c.can_manage_collab).map(c => ({ id: c.id, title: c.title })),
)
const showCreate = ref(false)
const creating = ref(false)
const regenId = ref<number | null>(null)
const regeneratingId = ref<number | null>(null)
const copyingId = ref<number | null>(null)
const showCopy = ref(false)
const copyTarget = ref<Courseware | null>(null)
const copyTitle = ref('')
const copyLoading = ref(false)
const copyInputRef = ref<{ focus?: () => void } | null>(null)
const formRef = ref()
const chapterOptions = ref<{ id: number; label: string }[]>([])
const chaptersLoading = ref(false)
const form = reactive({
  title: '', textbook_id: null as number | null, courseware_type: 'standard',
  render_style: 'html' as RenderStyle,
  theme: DEFAULT_THEME,
  gen_mode: 'chapter' as 'chapter' | 'page',
  chapter_ids: [] as number[],
  page_start: null as number | null, page_end: null as number | null,
  custom_prompt: '', want_virtual_lab: false, virtual_lab_key: '' as string,
  is_interactive: false,
})
const rules = { title: [{ required: true, message: '请填写课件标题' }] }
const labExperiments = ref<LabExperiment[]>([])
const labGroups = computed(() => {
  const map = new Map<string, LabExperiment[]>()
  for (const item of labExperiments.value) {
    const list = map.get(item.group) || []
    list.push(item)
    map.set(item.group, list)
  }
  return [...map.entries()].map(([label, items]) => ({ label, items }))
})

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

async function loadLabExperiments() {
  try {
    const data = await coursewareApi.listLabExperiments()
    labExperiments.value = data.items || []
  } catch {
    labExperiments.value = []
  }
}

async function loadChapters(textbookId: number) {
  chaptersLoading.value = true
  try {
    const data = (await textbookApi.getChapters(textbookId)) as Chapter[]
    chapterOptions.value = flattenChapters(data)
  } finally {
    chaptersLoading.value = false
  }
}

async function onTextbookChange() {
  form.chapter_ids = []
  form.page_start = null
  form.page_end = null
  chapterOptions.value = []
  if (form.textbook_id) await loadChapters(form.textbook_id)
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

function resetForm() {
  regenId.value = null
  form.title = ''
  form.textbook_id = null
  form.courseware_type = 'standard'
  form.render_style = 'html'
  form.theme = DEFAULT_THEME
  form.gen_mode = 'chapter'
  form.chapter_ids = []
  form.page_start = null
  form.page_end = null
  form.custom_prompt = ''
  form.want_virtual_lab = false
  form.virtual_lab_key = ''
  form.is_interactive = false
  chapterOptions.value = []
}

function canEditCw(cw: Courseware) {
  return auth.can('courseware.edit') && cw.can_edit !== false
}

function canManageCw(cw: Courseware) {
  return auth.can('courseware.edit') && cw.can_manage_collab !== false
}

function canRegenerate(cw: Courseware) {
  return cw.gen_status === 'done' || cw.gen_status === 'failed'
}

function openCreate() {
  resetForm()
  showCreate.value = true
}

function extractChapterIds(range?: Courseware['chapter_range']): number[] {
  if (!range || typeof range !== 'object') return []
  const ids = (range as { chapter_ids?: number[] }).chapter_ids
  return Array.isArray(ids) ? ids.filter((n) => Number.isFinite(n)) : []
}

async function fillFormFromCw(cw: Courseware) {
  form.title = cw.title
  form.textbook_id = cw.textbook_id || null
  form.courseware_type = cw.is_interactive ? 'interactive' : (cw.courseware_type || 'standard')
  form.render_style = (cw.render_style || 'html') as RenderStyle
  form.theme = cw.theme || DEFAULT_THEME
  form.custom_prompt = cw.custom_prompt || ''
  form.want_virtual_lab = !!cw.want_virtual_lab
  form.virtual_lab_key = cw.virtual_lab_key || ''
  form.is_interactive = !!cw.is_interactive
  const chapterIds = extractChapterIds(cw.chapter_range)
  const pageStart = cw.page_range?.start ?? null
  const pageEnd = cw.page_range?.end ?? null
  if (chapterIds.length) {
    form.gen_mode = 'chapter'
    form.chapter_ids = chapterIds
    form.page_start = null
    form.page_end = null
  } else if (pageStart && pageEnd) {
    form.gen_mode = 'page'
    form.chapter_ids = []
    form.page_start = pageStart
    form.page_end = pageEnd
  } else {
    form.gen_mode = 'chapter'
    form.chapter_ids = []
    form.page_start = pageStart
    form.page_end = pageEnd
  }
  chapterOptions.value = []
  if (form.textbook_id) await loadChapters(form.textbook_id)
}

async function openRegenerate(cw: Courseware) {
  if (!canRegenerate(cw) && cw.gen_status) {
    ElMessage.warning('正在生成中，请稍后再试')
    return
  }
  regeneratingId.value = cw.id
  try {
    const full = await coursewareApi.get(cw.id)
    if (!canRegenerate(full)) {
      ElMessage.warning('正在生成中，请稍后再试')
      return
    }
    regenId.value = full.id
    await fillFormFromCw(full)
    showCreate.value = true
  } catch {
    ElMessage.error('加载课件配置失败')
  } finally {
    regeneratingId.value = null
  }
}

watch(showCreate, (open) => {
  if (!open) regenId.value = null
})

async function maybeOpenRegenFromQuery() {
  const raw = route.query.regen
  const id = Number(Array.isArray(raw) ? raw[0] : raw)
  if (!id) return
  router.replace({ path: '/courseware' })
  await openRegenerate({ id } as Courseware)
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
      want_virtual_lab: form.courseware_type === 'interactive' && form.want_virtual_lab,
      virtual_lab_key: form.courseware_type === 'interactive' && form.want_virtual_lab
        ? (form.virtual_lab_key || null)
        : null,
      chapter_range: null,
      page_range: null,
    }
    if (form.textbook_id) {
      if (form.gen_mode === 'chapter' && form.chapter_ids.length) {
        payload.chapter_range = { chapter_ids: form.chapter_ids }
      } else if (form.gen_mode === 'page' && form.page_start && form.page_end) {
        payload.page_range = { start: form.page_start, end: form.page_end }
      }
    }
    if (regenId.value) {
      await coursewareApi.regenerate(regenId.value, payload)
      ElMessage.success('已提交重新生成')
    } else {
      await coursewareApi.create(payload)
      ElMessage.success('课件生成任务已提交')
    }
    showCreate.value = false
    await load()
  } finally { creating.value = false }
}

function openBatchCollab() {
  collabIds.value = []
  showCollab.value = true
}

function openShare(cw: Courseware) {
  shareTarget.value = cw
  showShare.value = true
}

async function openCopy(cw: Courseware) {
  copyingId.value = cw.id
  try {
    const res = await coursewareApi.suggestCopyTitle(cw.id)
    copyTarget.value = cw
    copyTitle.value = res.title
    showCopy.value = true
  } catch {
    ElMessage.error('复制失败，请稍后重试')
  } finally {
    copyingId.value = null
  }
}

function focusCopyInput() {
  nextTick(() => copyInputRef.value?.focus?.())
}

async function confirmCopy() {
  const src = copyTarget.value
  const title = copyTitle.value.trim()
  if (!src || copyLoading.value) return
  if (!title) { ElMessage.warning('请填写课件名称'); return }
  copyLoading.value = true
  try {
    const copied = await coursewareApi.copy(src.id, title)
    showCopy.value = false
    ElMessage.success(`已复制为「${copied.title}」`)
    await load()
  } catch {
    ElMessage.error('复制失败，请稍后重试')
  } finally {
    copyLoading.value = false
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

function onCardMore(cw: Courseware, cmd: string) {
  if (cmd === 'rename') void renameCw(cw)
  else if (cmd === 'copy') void openCopy(cw)
  else if (cmd === 'regen') void openRegenerate(cw)
  else if (cmd === 'collab') {
    collabIds.value = [cw.id]
    showCollab.value = true
  }
  else if (cmd === 'delete') void confirmDeleteCw(cw)
}

async function confirmDeleteCw(cw: Courseware) {
  try {
    await ElMessageBox.confirm('确定删除该课件？关联的课堂互动会话将一并删除。', '删除课件', { type: 'warning' })
  } catch {
    return
  }
  await deleteCw(cw.id)
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
  await loadLabExperiments()
  await maybeOpenRegenFromQuery()
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
