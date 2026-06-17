<template>
  <div class="p-6">
    <div class="mb-6">
      <h1 class="page-title">系统设置</h1>
      <p class="page-subtitle">配置 AI 大模型供应商和教学科目</p>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <!-- 左栏：LLM 配置 -->
      <div class="xl:col-span-2 space-y-4">
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-sm font-semibold text-slate-700">大模型配置</h2>
            <el-button size="small" type="primary" :icon="Plus" @click="openAddDialog">添加模型</el-button>
          </div>

          <div v-if="!configs.length" class="py-8 text-center text-slate-400 text-sm">
            尚未配置 AI 模型，请添加
          </div>

          <div v-for="cfg in configs" :key="cfg.id" class="flex items-center gap-3 p-3 rounded-xl border border-slate-100 mb-2 hover:border-primary-200 transition-colors">
            <!-- 供应商图标 -->
            <div class="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
              <span class="text-xs font-bold text-slate-500 uppercase">{{ cfg.provider.slice(0, 2) }}</span>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <p class="text-sm font-semibold text-slate-800">{{ cfg.display_name }}</p>
                <el-tag v-if="cfg.is_default" size="small" type="success">默认</el-tag>
                <el-tag v-if="!cfg.is_active" size="small" type="info">已禁用</el-tag>
              </div>
              <p class="text-xs text-slate-400 mt-0.5">{{ cfg.provider }} / {{ cfg.model_name }}</p>
            </div>
            <div class="flex items-center gap-1">
              <el-button size="small" link @click="testConfig(cfg)">测试</el-button>
              <el-button size="small" link type="primary" @click="editConfig(cfg)">编辑</el-button>
              <el-popconfirm title="确定删除该配置？" @confirm="deleteConfig(cfg.id)">
                <template #reference>
                  <el-button size="small" link type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </div>

      <!-- 右栏：教学科目 -->
      <div class="card">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-slate-700">我的教学科目</h2>
          <el-button size="small" :icon="Plus" @click="showAddSubject = true">添加</el-button>
        </div>

        <div v-for="ts in mySubjects" :key="ts.id" class="flex items-center gap-2 mb-2 p-2 rounded-lg hover:bg-slate-50">
          <div class="flex-1">
            <span class="text-xs text-slate-500">{{ ts.grade.name }}</span>
            <span class="mx-1 text-slate-300">·</span>
            <span class="text-sm font-medium text-slate-700">{{ ts.subject.name }}</span>
          </div>
          <el-button size="small" link type="danger" @click="removeSubject(ts.id)">移除</el-button>
        </div>

        <el-empty v-if="!mySubjects.length" :image-size="60" description="暂无科目" />
      </div>
    </div>

    <!-- 科目课件提示词 -->
    <div class="card mt-6">
      <div class="flex items-center justify-between mb-1">
        <h2 class="text-sm font-semibold text-slate-700">科目课件生成提示词</h2>
        <el-button size="small" text :loading="promptsLoading" @click="loadSubjectPrompts">刷新</el-button>
      </div>
      <p class="page-subtitle mb-4">为每个科目定制课件生成的教学侧重与互动形式，AI 生成课件时会按所选课本科目自动应用。</p>

      <div v-loading="promptsLoading" class="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div
          v-for="sp in subjectPrompts" :key="sp.subject_name"
          class="border border-slate-100 rounded-xl p-3 hover:border-primary-200 transition-colors"
        >
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-sm font-semibold text-slate-800">{{ sp.subject_name }}</span>
            <el-tag size="small" :type="sp.is_custom ? 'success' : 'info'">
              {{ sp.is_custom ? '已自定义' : '系统默认' }}
            </el-tag>
            <div class="flex-1" />
            <el-button size="small" link type="primary" @click="editPrompt(sp)">编辑</el-button>
            <el-popconfirm
              v-if="sp.is_custom"
              title="确定恢复为系统默认提示词？"
              @confirm="resetPrompt(sp)"
            >
              <template #reference>
                <el-button size="small" link type="warning">恢复默认</el-button>
              </template>
            </el-popconfirm>
          </div>
          <p class="text-xs text-slate-500 line-clamp-2">{{ sp.prompt }}</p>
          <p v-if="sp.interactive_guidance" class="text-xs text-slate-400 mt-1 line-clamp-1">
            互动：{{ sp.interactive_guidance }}
          </p>
        </div>
      </div>
      <el-empty v-if="!promptsLoading && !subjectPrompts.length" :image-size="60" description="暂无科目提示词" />
    </div>

    <!-- 编辑科目提示词弹窗 -->
    <el-dialog v-model="showPrompt" :title="`编辑「${promptForm.subject_name}」提示词`" width="600px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="教学侧重（告诉 AI 这门课怎么教）">
          <el-input v-model="promptForm.prompt" type="textarea" :rows="5" placeholder="例如：强调概念推导、例题分步讲解、数形结合……" />
        </el-form-item>
        <el-form-item label="互动形式建议（可选，适合本科目的互动/动画类型）">
          <el-input v-model="promptForm.interactive_guidance" type="textarea" :rows="3" placeholder="例如：数轴动画、函数图像演示、几何作图、随堂演算……" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPrompt = false">取消</el-button>
        <el-button type="primary" :loading="promptSaving" @click="savePrompt">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加 LLM 弹窗 -->
    <el-dialog v-model="showAdd" :title="editingCfg ? '编辑模型配置' : '添加模型'" width="500px" :close-on-click-modal="false">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="90px">
        <el-form-item label="供应商" prop="provider">
          <el-select v-model="form.provider" placeholder="选择供应商" style="width:100%" @change="onProviderChange">
            <el-option v-for="p in providers" :key="p.provider" :label="p.label" :value="p.provider">
              <span class="font-medium">{{ p.label }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" type="password" show-password placeholder="输入 API Key（加密存储）" />
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="form.base_url" placeholder="自定义接入地址（可选，留空用默认）" />
        </el-form-item>
        <el-form-item label="模型" prop="model_name">
          <div class="flex gap-2 w-full">
            <el-select
              v-model="form.model_name"
              :placeholder="availableModels.length ? '选择模型' : '请先获取模型列表'"
              style="flex:1"
              :allow-create="true"
              filterable
              :disabled="!form.provider"
            >
              <el-option v-for="m in availableModels" :key="m" :label="m" :value="m" />
            </el-select>
            <el-button :loading="fetchingModels" :disabled="!form.provider" @click="handleFetchModels">
              获取模型
            </el-button>
          </div>
          <p v-if="modelSource" class="text-xs mt-1" :class="modelSource === 'api' ? 'text-green-600' : 'text-slate-400'">
            {{ modelSource === 'api' ? '已从供应商接口获取最新模型列表' : '当前为预设模型列表，填入 API Key 后点击获取可拉取最新列表' }}
          </p>
        </el-form-item>
        <el-form-item label="显示名称" prop="display_name">
          <el-input v-model="form.display_name" placeholder="如：GPT-4o 主力模型" />
        </el-form-item>
        <el-form-item label="Temperature">
          <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" show-input :input-size="'small'" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加科目弹窗 -->
    <el-dialog v-model="showAddSubject" title="添加教学科目" width="400px">
      <el-form label-width="80px">
        <el-form-item label="学段">
          <el-select v-model="subForm.school_level_id" @change="subForm.grade_id = null; subForm.subject_id = null" style="width:100%">
            <el-option v-for="l in edu.schoolLevels" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="subForm.grade_id" :disabled="!subForm.school_level_id" style="width:100%" @change="subForm.subject_id = null">
            <el-option
              v-for="g in edu.grades.filter(g => g.school_level_id === subForm.school_level_id).sort((a, b) => a.sort_order - b.sort_order)"
              :key="g.id" :label="g.name" :value="g.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="科目">
          <el-select v-model="subForm.subject_id" :disabled="!subForm.grade_id" style="width:100%">
            <el-option v-for="s in edu.subjectsOfGrade(subForm.grade_id)" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddSubject = false">取消</el-button>
        <el-button type="primary" @click="handleAddSubject">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { settingsApi, educationApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import type { LLMConfig, TeacherSubject, SubjectPrompt } from '@/types'

const edu = useEducationStore()
const configs = ref<LLMConfig[]>([])
const providers = ref<any[]>([])
const mySubjects = ref<TeacherSubject[]>([])
const showAdd = ref(false)
const showAddSubject = ref(false)
const saving = ref(false)
const formRef = ref()
const editingCfg = ref<LLMConfig | null>(null)

const form = reactive({
  provider: '', model_name: '', display_name: '', api_key: '',
  base_url: '', temperature: 0.7, max_tokens: 4096, is_default: false,
})
const formRules = {
  provider: [{ required: true, message: '请选择供应商' }],
  model_name: [{ required: true, message: '请选择或输入模型名' }],
  display_name: [{ required: true, message: '请填写显示名称' }],
}
const subForm = reactive({ school_level_id: null as any, grade_id: null as any, subject_id: null as any })
const availableModels = ref<string[]>([])
const fetchingModels = ref(false)
const modelSource = ref<'' | 'api' | 'preset'>('')

function onProviderChange() {
  form.model_name = ''
  availableModels.value = []
  modelSource.value = ''
  const p = providers.value.find(p => p.provider === form.provider)
  form.display_name = p?.label ? `${p.label} - ` : ''
  // 自动带出供应商默认 base_url（用户可覆盖）
  if (p?.base_url && !form.base_url) form.base_url = p.base_url
}

async function handleFetchModels() {
  if (!form.provider) { ElMessage.warning('请先选择供应商'); return }
  fetchingModels.value = true
  try {
    const res: any = await settingsApi.fetchModels({
      provider: form.provider,
      api_key: form.api_key || undefined,
      base_url: form.base_url || undefined,
    })
    availableModels.value = res.models || []
    modelSource.value = res.source || 'preset'
    if (!availableModels.value.includes(form.model_name)) form.model_name = ''
    if (res.source === 'api') ElMessage.success(`获取到 ${availableModels.value.length} 个模型`)
  } finally {
    fetchingModels.value = false
  }
}

async function load() {
  configs.value = (await settingsApi.listConfigs()) as any
  mySubjects.value = (await educationApi.getMySubjects()) as any
}

function openAddDialog() {
  editingCfg.value = null
  Object.assign(form, {
    provider: '', model_name: '', display_name: '', api_key: '',
    base_url: '', temperature: 0.7, max_tokens: 4096, is_default: false,
  })
  availableModels.value = []
  modelSource.value = ''
  showAdd.value = true
}

function editConfig(cfg: LLMConfig) {
  editingCfg.value = cfg
  Object.assign(form, { ...cfg, api_key: '' })
  // 预填模型选项，保证已选模型在下拉中可见
  const preset = providers.value.find(p => p.provider === cfg.provider)?.models || []
  availableModels.value = Array.from(new Set([cfg.model_name, ...preset]))
  modelSource.value = 'preset'
  showAdd.value = true
}

async function handleSave() {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editingCfg.value) {
      await settingsApi.updateConfig(editingCfg.value.id, form)
    } else {
      await settingsApi.createConfig(form)
    }
    ElMessage.success('保存成功')
    showAdd.value = false
    editingCfg.value = null
    await load()
  } finally { saving.value = false }
}

async function deleteConfig(id: number) {
  await settingsApi.deleteConfig(id)
  ElMessage.success('已删除')
  await load()
}

async function testConfig(cfg: LLMConfig) {
  const res: any = await settingsApi.testConfig(cfg.id)
  if (res.success) ElMessage.success(`测试成功：${res.reply}`)
  else ElMessage.error(`测试失败：${res.error}`)
}

async function handleAddSubject() {
  if (!subForm.grade_id || !subForm.subject_id) { ElMessage.warning('请选择年级和科目'); return }
  await educationApi.addMySubject({ grade_id: subForm.grade_id, subject_id: subForm.subject_id })
  ElMessage.success('已添加')
  showAddSubject.value = false
  await edu.init()
  mySubjects.value = (await educationApi.getMySubjects()) as any
}

async function removeSubject(id: number) {
  await educationApi.removeMySubject(id)
  ElMessage.success('已移除')
  await load()
}

// ─── 科目课件提示词 ───────────────────────────────
const subjectPrompts = ref<SubjectPrompt[]>([])
const promptsLoading = ref(false)
const showPrompt = ref(false)
const promptSaving = ref(false)
const promptForm = reactive({ subject_name: '', prompt: '', interactive_guidance: '' })

async function loadSubjectPrompts() {
  promptsLoading.value = true
  try { subjectPrompts.value = (await settingsApi.listSubjectPrompts()) as any }
  finally { promptsLoading.value = false }
}

function editPrompt(sp: SubjectPrompt) {
  promptForm.subject_name = sp.subject_name
  promptForm.prompt = sp.prompt
  promptForm.interactive_guidance = sp.interactive_guidance || ''
  showPrompt.value = true
}

async function savePrompt() {
  if (!promptForm.prompt.trim()) { ElMessage.warning('请填写教学侧重内容'); return }
  promptSaving.value = true
  try {
    await settingsApi.updateSubjectPrompt(promptForm.subject_name, {
      prompt: promptForm.prompt.trim(),
      interactive_guidance: promptForm.interactive_guidance.trim() || null,
    })
    ElMessage.success('已保存')
    showPrompt.value = false
    await loadSubjectPrompts()
  } finally { promptSaving.value = false }
}

async function resetPrompt(sp: SubjectPrompt) {
  await settingsApi.resetSubjectPrompt(sp.subject_name)
  ElMessage.success('已恢复系统默认')
  await loadSubjectPrompts()
}

onMounted(async () => {
  providers.value = (await settingsApi.getProviders()) as any
  await load()
  await loadSubjectPrompts()
})
</script>
