<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4 sm:mb-6">
      <div>
        <h1 class="page-title">互动动画</h1>
        <p class="page-subtitle">按知识点预置的实验台、数学探究、分子反应、生物与物理示意图。物理实验台（电学、光学）可从器材库自由搭建，另存为我的后能保存搭建结果。可单独预览，生成课件时手动引入或自动匹配。</p>
      </div>
      <el-button v-if="auth.can('animation.edit')" type="primary" :icon="Plus" @click="openCreate">
        从模板创建
      </el-button>
    </div>

    <div class="flex flex-wrap gap-2 mb-4">
      <el-select v-model="subject" placeholder="全部科目" clearable class="w-36" @change="onSubjectChange">
        <el-option label="物理" value="物理" />
        <el-option label="化学" value="化学" />
        <el-option label="科学" value="科学" />
        <el-option label="数学" value="数学" />
        <el-option label="生物" value="生物" />
      </el-select>
    </div>

    <div v-loading="loading" class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      <div v-for="item in pagedItems" :key="item.id" class="card !p-4 hover:shadow-md transition-shadow">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <p class="text-sm font-semibold text-slate-800 truncate">{{ item.title }}</p>
            <div class="flex flex-wrap gap-1.5 mt-1.5">
              <el-tag size="small" type="success">{{ item.subject }}</el-tag>
              <el-tag v-if="kindLabel(item)" size="small">{{ kindLabel(item) }}</el-tag>
              <el-tag v-if="item.group" size="small" type="info">{{ item.group }}</el-tag>
              <el-tag size="small" :type="item.origin === 'system' ? 'warning' : 'primary'">
                {{ item.origin === 'system' ? '系统' : '我的' }}
              </el-tag>
            </div>
          </div>
        </div>
        <p v-if="item.knowledge_tags?.length" class="text-xs text-slate-500 mt-2 truncate">
          知识点：{{ item.knowledge_tags.join('、') }}
        </p>
        <div class="flex items-center gap-1 mt-3 pt-3 border-t border-slate-50">
          <el-button size="small" link type="primary" @click="preview(item)">预览</el-button>
          <el-button size="small" link type="primary" @click="present(item)">全屏演示</el-button>
          <el-button size="small" link @click="openShare(item)">分享</el-button>
          <el-button
            v-if="auth.can('animation.edit')"
            size="small" link
            @click="openSaveAs(item)"
          >另存为我的</el-button>
          <el-button
            v-if="canEdit(item)"
            size="small" link
            @click="openEdit(item)"
          >编辑</el-button>
          <el-button
            v-if="canEdit(item)"
            size="small" link type="danger"
            @click="remove(item)"
          >删除</el-button>
        </div>
      </div>
    </div>
    <p v-if="!loading && !items.length" class="text-sm text-slate-400 text-center py-12">暂无动画</p>
    <div v-if="items.length > pageSize" class="mt-4 flex justify-end">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="items.length"
        layout="prev, pager, next, total"
      />
    </div>

    <el-drawer v-model="showPreview" size="86%" :title="previewItem?.title || '预览'">
      <template #header>
        <div class="flex items-center gap-2 w-full pr-6">
          <span class="font-semibold truncate flex-1">{{ previewItem?.title || '预览' }}</span>
          <template v-if="sceneEditable && previewItem">
            <el-button
              v-if="canEdit(previewItem)"
              size="small" type="success" :loading="savingScene"
              @click="saveScene"
            >保存搭建</el-button>
            <el-button
              v-if="auth.can('animation.edit')"
              size="small" :loading="savingScene"
              @click="saveSceneAs"
            >另存为我的（含搭建）</el-button>
          </template>
          <el-button size="small" :disabled="!previewUrl || previewing" @click="openShare(previewItem)">分享链接</el-button>
          <el-button size="small" type="primary" :disabled="!previewUrl || previewing" @click="enterPresent">全屏演示</el-button>
        </div>
      </template>
      <div v-if="previewing" class="text-sm text-slate-400 py-16 text-center">正在加载动画，首次生成可能需要几十秒…</div>
      <iframe
        v-else-if="previewUrl"
        ref="previewFrame"
        class="w-full border-0 rounded-lg bg-white"
        style="min-height: 78vh; height: 78vh"
        :src="previewUrl"
        sandbox="allow-scripts allow-same-origin"
        allow="fullscreen"
      />
    </el-drawer>

    <Teleport to="body">
      <div
        v-if="presenting && previewUrl"
        ref="presentRoot"
        class="fixed inset-0 z-[4000] bg-black flex flex-col"
      >
        <div class="h-11 shrink-0 flex items-center gap-3 px-4 bg-black/80 text-white">
          <span class="truncate flex-1 text-sm">{{ previewItem?.title }}</span>
          <span class="text-xs text-white/50">Esc 退出全屏</span>
          <el-button
            v-if="sceneEditable && previewItem && canEdit(previewItem)"
            size="small" type="success" :loading="savingScene"
            @click="saveScene"
          >保存搭建</el-button>
          <el-button size="small" @click="exitPresent">退出</el-button>
        </div>
        <iframe
          ref="presentFrame"
          class="flex-1 w-full border-0 bg-black"
          :src="previewUrl"
          sandbox="allow-scripts allow-same-origin"
          allow="fullscreen"
        />
      </div>
    </Teleport>

    <ShareDialog
      v-model="showShare"
      resource-type="animation"
      :resource-id="shareTarget?.id || 0"
      :resource-title="shareTarget?.title"
    />

    <el-dialog v-model="showForm" :title="formMode === 'create' ? '从模板创建' : '编辑动画'" width="480px">
      <el-form label-position="top">
        <el-form-item v-if="formMode === 'create'" label="模板">
          <el-select v-model="form.template_key" class="w-full" filterable>
            <el-option-group v-for="g in templateGroups" :key="g.label" :label="g.label">
              <el-option v-for="t in g.items" :key="t.key" :value="t.key" :label="t.title" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="匹配关键词（出课自动推荐）">
          <el-select v-model="form.keywords" multiple filterable allow-create default-first-option class="w-full" />
        </el-form-item>
        <el-form-item label="关联知识点名称">
          <el-select v-model="form.knowledge_tags" multiple filterable allow-create default-first-option class="w-full" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForm = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { animationApi } from '@/api/modules'
import { createIframeBlob } from '@/utils/coursewareFrame'
import { useAuthStore } from '@/stores/auth'
import ShareDialog from '@/components/ShareDialog.vue'
import type { InteractiveAsset } from '@/types'

const auth = useAuthStore()
const loading = ref(false)
const items = ref<InteractiveAsset[]>([])
const subject = ref<string>('')
const page = ref(1)
const pageSize = 12
const showPreview = ref(false)
const previewItem = ref<InteractiveAsset | null>(null)
const previewUrl = ref('')
const previewing = ref(false)
const showForm = ref(false)
const showShare = ref(false)
const shareTarget = ref<InteractiveAsset | null>(null)
const presenting = ref(false)
const presentRoot = ref<HTMLElement | null>(null)
const formMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const saving = ref(false)
const form = reactive({
  template_key: '',
  title: '',
  keywords: [] as string[],
  knowledge_tags: [] as string[],
})
const previewFrame = ref<HTMLIFrameElement | null>(null)
const presentFrame = ref<HTMLIFrameElement | null>(null)
const sceneEditable = ref(false)
const savingScene = ref(false)
const pendingScene = ref<Record<string, unknown> | null>(null)

const KIND_LABEL: Record<string, string> = {
  physics_lab: '物理实验台',
  chem_lab: '实验台',
  solid_explore: '立体探究',
  curve_explore: '曲线画板',
  chem_reaction: '分子 3D',
  bio_explore: '生物探究',
  physics_explore: '物理探究',
}

function kindLabel(item: InteractiveAsset) {
  return KIND_LABEL[item.kind] || ''
}

const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize
  return items.value.slice(start, start + pageSize)
})

const templates = computed(() => items.value.filter(i => i.origin === 'system'))
const templateGroups = computed(() => {
  const map = new Map<string, InteractiveAsset[]>()
  for (const item of templates.value) {
    const label = [item.subject, item.group].filter(Boolean).join(' · ') || '其他'
    const list = map.get(label) || []
    list.push(item)
    map.set(label, list)
  }
  return [...map.entries()].map(([label, groupItems]) => ({ label, items: groupItems }))
})

function isAdminUser() {
  return !!auth.teacher?.is_super || (auth.teacher?.roles || []).some(r => r.code === 'admin')
}

function canEdit(item: InteractiveAsset) {
  if (!auth.can('animation.edit') || item.origin !== 'teacher') return false
  return item.teacher_id === auth.teacher?.id || isAdminUser()
}

function clampPage() {
  const maxPage = Math.max(1, Math.ceil(items.value.length / pageSize) || 1)
  if (page.value > maxPage) page.value = maxPage
}

async function load() {
  loading.value = true
  try {
    const data = await animationApi.list(subject.value ? { subject: subject.value } : undefined)
    items.value = data.items || []
    clampPage()
  } finally {
    loading.value = false
  }
}

function onSubjectChange() {
  page.value = 1
  load()
}

function revokePreview() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
  sceneEditable.value = false
}

/* 动画页外壳协议：iframe 内 NB 外壳收 {nb:'call'}，回 {nb:'reply'} / {nb:'event'} */
let callSeq = 0
const pendingCalls = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>()

function activeFrame(): HTMLIFrameElement | null {
  return (presenting.value ? presentFrame.value : previewFrame.value) || previewFrame.value || presentFrame.value
}

function isOurFrame(src: MessageEventSource | null) {
  return !!src && [previewFrame.value, presentFrame.value].some(f => f?.contentWindow === src)
}

function onFrameMessage(e: MessageEvent) {
  const m = e.data
  if (!m || typeof m !== 'object' || !isOurFrame(e.source)) return
  if (m.nb === 'event' && m.type === 'onload') {
    sceneEditable.value = !!m.data?.sceneEditable
  } else if (m.nb === 'reply' && pendingCalls.has(m.id)) {
    const p = pendingCalls.get(m.id)!
    pendingCalls.delete(m.id)
    if (m.error) p.reject(new Error(m.error))
    else p.resolve(m.result)
  }
}

function callFrame<T = unknown>(method: string, args?: unknown): Promise<T> {
  const win = activeFrame()?.contentWindow
  if (!win) return Promise.reject(new Error('动画未加载'))
  const id = ++callSeq
  return new Promise<T>((resolve, reject) => {
    pendingCalls.set(id, { resolve: resolve as (v: unknown) => void, reject })
    win.postMessage({ nb: 'call', id, method, args }, '*')
    setTimeout(() => {
      if (pendingCalls.delete(id)) reject(new Error('动画无响应'))
    }, 5000)
  })
}

async function readScene(): Promise<Record<string, unknown> | null> {
  try {
    const scene = await callFrame<Record<string, unknown> | null>('getData')
    if (scene && typeof scene === 'object') return scene
    ElMessage.error('当前动画没有可保存的搭建')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '读取搭建失败')
  }
  return null
}

async function saveScene() {
  const item = previewItem.value
  if (!item) return
  savingScene.value = true
  try {
    const scene = await readScene()
    if (!scene) return
    await animationApi.update(item.id, { scene })
    ElMessage.success('已保存当前搭建，下次打开和出课引用都会使用它')
  } finally {
    savingScene.value = false
  }
}

async function saveSceneAs() {
  const item = previewItem.value
  if (!item) return
  savingScene.value = true
  try {
    const scene = await readScene()
    if (!scene) return
    openSaveAs(item)
    pendingScene.value = scene
  } finally {
    savingScene.value = false
  }
}

function openShare(item: InteractiveAsset | null) {
  if (!item) return
  shareTarget.value = item
  showShare.value = true
}

async function loadPreview(item: InteractiveAsset) {
  revokePreview()
  previewItem.value = item
  previewing.value = true
  try {
    const html = await animationApi.getHtml(item.id)
    if (typeof html !== 'string' || !html.trim()) {
      ElMessage.error('动画尚未生成')
      return false
    }
    previewUrl.value = createIframeBlob(html)
    return true
  } catch {
    ElMessage.error('预览失败')
    return false
  } finally {
    previewing.value = false
  }
}

async function preview(item: InteractiveAsset) {
  showPreview.value = true
  await loadPreview(item)
}

async function present(item: InteractiveAsset) {
  showPreview.value = false
  const ok = await loadPreview(item)
  if (ok) await enterPresent()
}

async function enterPresent() {
  if (!previewUrl.value) return
  presenting.value = true
  await nextTick()
  const el = presentRoot.value as any
  const req = el?.requestFullscreen || el?.webkitRequestFullscreen || el?.msRequestFullscreen
  if (req) {
    try { await req.call(el) } catch { /* 浏览器拒绝时仍用铺满遮罩 */ }
  }
}

function exitPresent() {
  presenting.value = false
  const doc = document as any
  if (document.fullscreenElement || doc.webkitFullscreenElement) {
    const exit = document.exitFullscreen || doc.webkitExitFullscreen
    if (exit) exit.call(document)
  }
}

function onPresentKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && presenting.value) exitPresent()
}

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  pendingScene.value = null
  form.template_key = templates.value[0]?.key || ''
  form.title = ''
  form.keywords = []
  form.knowledge_tags = []
  showForm.value = true
}

function openSaveAs(item: InteractiveAsset) {
  formMode.value = 'create'
  editingId.value = null
  pendingScene.value = null
  form.template_key = item.origin === 'system' ? item.key : item.problem_type
  form.title = `${item.title}（我的）`
  form.keywords = [...(item.keywords || [])]
  form.knowledge_tags = [...(item.knowledge_tags || [])]
  showForm.value = true
}

function openEdit(item: InteractiveAsset) {
  formMode.value = 'edit'
  editingId.value = item.id
  form.template_key = item.key
  form.title = item.title
  form.keywords = [...(item.keywords || [])]
  form.knowledge_tags = [...(item.knowledge_tags || [])]
  showForm.value = true
}

async function submitForm() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  saving.value = true
  try {
    if (formMode.value === 'create') {
      if (!form.template_key) {
        ElMessage.warning('请选择模板')
        return
      }
      await animationApi.create({
        template_key: form.template_key,
        title: form.title.trim(),
        keywords: form.keywords,
        knowledge_tags: form.knowledge_tags,
        ...(pendingScene.value ? { scene: pendingScene.value } : {}),
      })
      pendingScene.value = null
      ElMessage.success('已创建')
    } else if (editingId.value) {
      await animationApi.update(editingId.value, {
        title: form.title.trim(),
        keywords: form.keywords,
        knowledge_tags: form.knowledge_tags,
      })
      ElMessage.success('已保存')
    }
    showForm.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(item: InteractiveAsset) {
  await ElMessageBox.confirm(`删除「${item.title}」？`, '确认', { type: 'warning' })
  await animationApi.delete(item.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onPresentKey)
  window.addEventListener('message', onFrameMessage)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onPresentKey)
  window.removeEventListener('message', onFrameMessage)
  showPreview.value = false
  exitPresent()
  revokePreview()
})
</script>
