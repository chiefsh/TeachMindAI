<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4 sm:mb-6">
      <div>
        <h1 class="page-title">互动动画</h1>
        <p class="page-subtitle">预置实验台与自建动画。生成课件时可自动匹配或手动引入，不必每次重出。</p>
      </div>
      <el-button v-if="auth.can('animation.edit')" type="primary" :icon="Plus" @click="openCreate">
        从模板创建
      </el-button>
    </div>

    <div class="flex flex-wrap gap-2 mb-4">
      <el-select v-model="subject" placeholder="全部科目" clearable class="w-36" @change="load">
        <el-option label="化学" value="化学" />
        <el-option label="科学" value="科学" />
        <el-option label="数学" value="数学" />
      </el-select>
    </div>

    <div v-loading="loading" class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      <div v-for="item in items" :key="item.id" class="card !p-4 hover:shadow-md transition-shadow">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <p class="text-sm font-semibold text-slate-800 truncate">{{ item.title }}</p>
            <div class="flex flex-wrap gap-1.5 mt-1.5">
              <el-tag size="small" type="success">{{ item.subject }}</el-tag>
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

    <el-drawer v-model="showPreview" size="72%" :title="previewItem?.title || '预览'">
      <div v-if="previewing" class="text-sm text-slate-400 py-16 text-center">正在加载实验台…</div>
      <iframe
        v-else-if="previewUrl"
        class="w-full border-0 rounded-lg bg-white"
        style="min-height: 78vh; height: 78vh"
        :src="previewUrl"
        sandbox="allow-scripts allow-same-origin"
      />
    </el-drawer>

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
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { animationApi } from '@/api/modules'
import { createIframeBlob } from '@/utils/coursewareFrame'
import { useAuthStore } from '@/stores/auth'
import type { InteractiveAsset } from '@/types'

const auth = useAuthStore()
const loading = ref(false)
const items = ref<InteractiveAsset[]>([])
const subject = ref<string>('')
const showPreview = ref(false)
const previewItem = ref<InteractiveAsset | null>(null)
const previewUrl = ref('')
const previewing = ref(false)
const showForm = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const saving = ref(false)
const form = reactive({
  template_key: '',
  title: '',
  keywords: [] as string[],
  knowledge_tags: [] as string[],
})

const templates = computed(() => items.value.filter(i => i.origin === 'system'))
const templateGroups = computed(() => {
  const map = new Map<string, InteractiveAsset[]>()
  for (const item of templates.value) {
    const list = map.get(item.group || '其他') || []
    list.push(item)
    map.set(item.group || '其他', list)
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

async function load() {
  loading.value = true
  try {
    const data = await animationApi.list(subject.value ? { subject: subject.value } : undefined)
    items.value = data.items || []
  } finally {
    loading.value = false
  }
}

function revokePreview() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
}

async function preview(item: InteractiveAsset) {
  revokePreview()
  previewItem.value = item
  showPreview.value = true
  previewing.value = true
  try {
    const html = await animationApi.getHtml(item.id)
    if (typeof html !== 'string' || !html.trim()) {
      ElMessage.error('动画尚未生成')
      return
    }
    previewUrl.value = createIframeBlob(html)
  } catch {
    ElMessage.error('预览失败')
  } finally {
    previewing.value = false
  }
}

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  form.template_key = templates.value[0]?.key || ''
  form.title = ''
  form.keywords = []
  form.knowledge_tags = []
  showForm.value = true
}

function openSaveAs(item: InteractiveAsset) {
  formMode.value = 'create'
  editingId.value = null
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
      })
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

onMounted(load)
onUnmounted(revokePreview)
</script>
