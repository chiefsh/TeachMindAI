<template>
  <div class="p-6">
    <div class="flex items-start justify-between mb-6">
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
          <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
            :class="cw.is_interactive ? 'bg-purple-50' : 'bg-blue-50'">
            <el-icon class="text-xl" :class="cw.is_interactive ? 'text-purple-500' : 'text-blue-500'">
              <VideoPlay />
            </el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold text-slate-800 truncate">{{ cw.title }}</p>
            <div class="flex items-center flex-wrap gap-1.5 mt-1.5">
              <el-tag v-if="cw.grade_id" size="small" type="info">{{ edu.gradeName(cw.grade_id) }}</el-tag>
              <el-tag v-if="cw.subject_id" size="small" type="success">{{ edu.subjectName(cw.subject_id) }}</el-tag>
            </div>
            <div class="flex items-center flex-wrap gap-2 mt-1.5">
              <span :class="`badge badge-${cw.gen_status}`">{{ statusLabel(cw.gen_status) }}</span>
              <el-tag v-if="cw.is_interactive" size="small" type="warning">互动</el-tag>
              <span class="text-xs text-slate-400">{{ formatDate(cw.created_at) }}</span>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2 mt-3 pt-3 border-t border-slate-50" @click.stop>
          <el-button size="small" link :icon="View" @click="router.push(`/courseware/${cw.id}`)">查看</el-button>
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
          <el-popconfirm title="确定删除该课件？" @confirm="deleteCw(cw.id)">
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

    <!-- 生成课件弹窗 -->
    <el-dialog v-model="showCreate" title="生成课件" width="560px" :close-on-click-modal="false">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="课件标题" prop="title">
          <el-input v-model="form.title" placeholder="如：第一章 春 — 精讲课件" />
        </el-form-item>
        <el-form-item label="关联课本">
          <el-select v-model="form.textbook_id" placeholder="选择课本（可选）" style="width:100%" clearable>
            <el-option v-for="tb in textbooks" :key="tb.id" :label="tb.title" :value="tb.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.textbook_id" label="页码范围">
          <div class="flex items-center gap-2">
            <el-input-number v-model="form.page_start" :min="1" placeholder="起始页" style="width:120px" />
            <span class="text-slate-400">至</span>
            <el-input-number v-model="form.page_end" :min="1" placeholder="结束页" style="width:120px" />
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { coursewareApi, textbookApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { ElMessage } from 'element-plus'
import { MagicStick, View, Delete, VideoPlay, RefreshRight } from '@element-plus/icons-vue'
import type { Courseware, Textbook } from '@/types'
import dayjs from 'dayjs'

const router = useRouter()
const edu = useEducationStore()
const coursewares = ref<Courseware[]>([])
const textbooks = ref<Textbook[]>([])
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const regeneratingId = ref<number | null>(null)
const formRef = ref()
const form = reactive({
  title: '', textbook_id: null as number | null, courseware_type: 'standard',
  page_start: null as number | null, page_end: null as number | null,
  custom_prompt: '', interactive_features: [] as string[], is_interactive: false,
})
const rules = { title: [{ required: true, message: '请填写课件标题' }] }

async function load() {
  loading.value = true
  try {
    coursewares.value = (await coursewareApi.list({
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
    })) as any
  }
  finally { loading.value = false }
}

async function loadTextbooks() {
  textbooks.value = (await textbookApi.list({
    grade_id: edu.selectedGradeId || undefined,
    subject_id: edu.selectedSubjectId || undefined,
  })) as any
}

function openCreate() { showCreate.value = true }

// 顶部全局年级/科目变化时同步刷新课件与可选课本
watch(() => [edu.selectedGradeId, edu.selectedSubjectId], () => { load(); loadTextbooks() })

async function handleCreate() {
  await formRef.value?.validate()
  creating.value = true
  try {
    const payload: any = {
      title: form.title,
      textbook_id: form.textbook_id,
      courseware_type: form.courseware_type,
      custom_prompt: form.custom_prompt,
      is_interactive: form.courseware_type === 'interactive',
    }
    if (form.page_start && form.page_end) {
      payload.page_range = { start: form.page_start, end: form.page_end }
    }
    await coursewareApi.create(payload)
    ElMessage.success('课件生成任务已提交，请稍候查看')
    showCreate.value = false
    await load()
  } finally { creating.value = false }
}

async function regenerateCw(cw: Courseware) {
  regeneratingId.value = cw.id
  try {
    await coursewareApi.regenerate(cw.id)
    ElMessage.success('已重新触发生成，请稍候查看')
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

function statusLabel(s: string) {
  return { pending: '待生成', processing: '生成中', done: '已完成', failed: '生成失败' }[s] || s
}
function formatDate(d: string) { return dayjs(d).format('MM-DD HH:mm') }

onMounted(async () => {
  await load()
  await loadTextbooks()
})
</script>
