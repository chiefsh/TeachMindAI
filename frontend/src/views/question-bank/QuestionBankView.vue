<template>
  <div class="p-6">
    <div class="flex items-start justify-between mb-6">
      <div>
        <h1 class="page-title">题库管理</h1>
        <p class="page-subtitle">管理题目，支持文件批量导入和图片 OCR 识别</p>
      </div>
      <div class="flex gap-2">
        <el-button :icon="Upload" @click="openImport">导入题库</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">手动录入</el-button>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="card mb-4 flex flex-wrap items-center gap-3 !py-3">
      <el-select v-model="filter.question_type" placeholder="题型" clearable size="small" style="width:100px">
        <el-option v-for="t in questionTypes" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>
      <el-select v-model="filter.difficulty" placeholder="难度" clearable size="small" style="width:90px">
        <el-option v-for="d in difficulties" :key="d.value" :label="d.label" :value="d.value" />
      </el-select>
      <el-input v-model="filter.keyword" placeholder="搜索题目" size="small" clearable style="width:160px" />
      <el-button size="small" type="primary" @click="load">查询</el-button>
      <span class="text-xs text-slate-400 ml-auto">共 {{ total }} 道</span>
    </div>

    <!-- 题目列表 -->
    <div class="card !p-0 overflow-hidden">
      <el-table :data="questions" v-loading="loading" row-class-name="hover:bg-slate-50">
        <el-table-column type="index" width="55" align="center" />
        <el-table-column label="题干" min-width="280">
          <template #default="{ row }">
            <p class="text-sm line-clamp-2">{{ row.content }}</p>
          </template>
        </el-table-column>
        <el-table-column label="题型" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTag(row.question_type)">{{ typeLabel(row.question_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="难度" width="80">
          <template #default="{ row }">
            <span :class="`text-xs font-medium ${diffColor(row.difficulty)}`">{{ diffLabel(row.difficulty) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-popconfirm title="确定删除该题目？" @confirm="deleteQ(row.id)">
              <template #reference>
                <el-button size="small" link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="p-4 flex justify-end">
        <el-pagination
          v-model:current-page="filter.page"
          :page-size="filter.page_size"
          :total="total"
          layout="prev, pager, next"
          @current-change="load"
        />
      </div>
    </div>

    <!-- 手动录入弹窗 -->
    <el-dialog v-model="showCreate" title="手动录入题目" width="720px" :close-on-click-modal="false" top="6vh">
      <div class="flex flex-wrap items-center gap-3 mb-3">
        <el-select v-model="createForm.grade_id" placeholder="年级" size="small" style="width:110px" @change="createForm.subject_id = null">
          <el-option v-for="g in edu.sortedGrades" :key="g.id" :label="g.name" :value="g.id" />
        </el-select>
        <el-select v-model="createForm.subject_id" placeholder="科目" size="small" style="width:110px" :disabled="!createForm.grade_id">
          <el-option v-for="s in edu.subjectsOfGrade(createForm.grade_id)" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-switch v-model="createForm.use_ai" active-text="AI 智能识别" inactive-text="纯文本拆分" size="small" />
      </div>

      <RichEditor
        ref="editorRef"
        v-model="createForm.html"
        @update:text="(t: string) => createForm.text = t"
        placeholder="在此输入或粘贴题目，可一次录入一道或多道题。例如：&#10;1. 下列哪个是质数？ A.4 B.6 C.7 D.9  答案：C&#10;2. 计算 3+5= ____  答案：8"
      />
      <p class="text-xs text-slate-400 mt-2">
        开启「AI 智能识别」后，系统会自动拆分多道题，并识别题型、选项与答案；关闭则按题号拆分为简答题。
      </p>

      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :icon="MagicStick" :loading="creating" @click="handleCreate">
          {{ createForm.use_ai ? '智能识别并保存' : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 导入弹窗 -->
    <el-dialog v-model="showImport" title="导入题库" width="460px">
      <el-form :model="importForm" label-width="80px" class="mb-2">
        <el-form-item label="年级">
          <el-select v-model="importForm.grade_id" placeholder="选择年级" style="width:100%" @change="importForm.subject_id = null">
            <el-option v-for="g in edu.sortedGrades" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="科目">
          <el-select
            v-model="importForm.subject_id"
            :placeholder="importForm.grade_id ? '选择科目' : '请先选择年级'"
            :disabled="!importForm.grade_id"
            style="width:100%"
          >
            <el-option v-for="s in edu.subjectsOfGrade(importForm.grade_id)" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <el-upload :auto-upload="false" :limit="1" accept=".pdf,.doc,.docx,.txt,.epub,.mobi,.jpg,.jpeg,.png"
            :on-change="(f: any) => importForm.file = f.raw">
            <el-button>选择文件</el-button>
            <template #tip>
              <p class="text-xs text-slate-400 mt-1">支持 PDF/Word/TXT/EPUB/MOBI 及图片格式</p>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showImport = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="handleImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { questionApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { ElMessage } from 'element-plus'
import { Upload, Plus, MagicStick } from '@element-plus/icons-vue'
import type { Question } from '@/types'
import RichEditor from '@/components/RichEditor.vue'

const edu = useEducationStore()
const questions = ref<Question[]>([])
const total = ref(0)
const loading = ref(false)
const showImport = ref(false)
const showCreate = ref(false)
const importing = ref(false)
const creating = ref(false)
const editorRef = ref<any>(null)
const filter = reactive({ question_type: null as any, difficulty: null as any, keyword: '', page: 1, page_size: 20 })
const importForm = reactive({ grade_id: null as any, subject_id: null as any, file: null as File | null })
const createForm = reactive({ grade_id: null as any, subject_id: null as any, use_ai: true, html: '', text: '' })

const questionTypes = [
  { value: 'single_choice', label: '单选题' }, { value: 'multi_choice', label: '多选题' },
  { value: 'fill_blank', label: '填空题' }, { value: 'short_answer', label: '简答题' },
  { value: 'essay', label: '作文' }, { value: 'true_false', label: '判断题' },
  { value: 'calculation', label: '计算题' },
]
const difficulties = [
  { value: 'easy', label: '简单' }, { value: 'medium', label: '中等' },
  { value: 'hard', label: '较难' }, { value: 'very_hard', label: '特难' },
]

async function load() {
  loading.value = true
  try {
    const res: any = await questionApi.list({
      ...filter,
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
    })
    questions.value = res.items
    total.value = res.total
  } finally { loading.value = false }
}

// 顶部全局年级/科目变化时回到第一页并刷新
watchDebounced(() => [edu.selectedGradeId, edu.selectedSubjectId], () => { filter.page = 1; load() }, { debounce: 250 })

function openCreate() {
  createForm.grade_id = edu.selectedGradeId || null
  createForm.subject_id = edu.selectedSubjectId || null
  showCreate.value = true
}

function openImport() {
  importForm.grade_id = edu.selectedGradeId || null
  importForm.subject_id = edu.selectedSubjectId || null
  showImport.value = true
}

async function handleImport() {
  if (!importForm.file) { ElMessage.warning('请选择文件'); return }
  const fd = new FormData()
  fd.append('file', importForm.file)
  fd.append('subject_id', String(importForm.subject_id))
  fd.append('grade_id', String(importForm.grade_id))
  importing.value = true
  try {
    await questionApi.importFile(fd)
    ElMessage.success('导入任务已提交，正在后台处理')
    showImport.value = false
    setTimeout(load, 3000)
  } finally { importing.value = false }
}

async function handleCreate() {
  const text = (createForm.text || editorRef.value?.getText() || '').trim()
  if (!createForm.grade_id || !createForm.subject_id) { ElMessage.warning('请选择年级和科目'); return }
  if (!text) { ElMessage.warning('请输入题目内容'); return }
  creating.value = true
  try {
    const res: any = await questionApi.manual({
      text,
      subject_id: createForm.subject_id,
      grade_id: createForm.grade_id,
      use_ai: createForm.use_ai,
    })
    ElMessage.success(`已录入 ${res.count} 道题目`)
    showCreate.value = false
    createForm.html = ''
    createForm.text = ''
    editorRef.value?.clear()
    await load()
  } finally { creating.value = false }
}

async function deleteQ(id: number) {
  await questionApi.delete(id)
  ElMessage.success('已删除')
  await load()
}

function typeLabel(t: string) {
  return { single_choice: '单选', multi_choice: '多选', fill_blank: '填空', short_answer: '简答', essay: '作文', true_false: '判断', calculation: '计算' }[t] || t
}
function typeTag(t: string): any {
  return { single_choice: '', multi_choice: 'warning', fill_blank: 'success', short_answer: 'info' }[t] || ''
}
function diffLabel(d: string) {
  return { easy: '简单', medium: '中等', hard: '较难', very_hard: '特难' }[d] || d
}
function diffColor(d: string) {
  return { easy: 'text-green-600', medium: 'text-blue-600', hard: 'text-orange-600', very_hard: 'text-red-600' }[d] || ''
}

onMounted(load)
</script>
