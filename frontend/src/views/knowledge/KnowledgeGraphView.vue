<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4">
      <div>
        <h1 class="page-title">知识图谱</h1>
        <p class="page-subtitle">
          知识点系统化沉淀与跨学科串联（全站共用） · 共 {{ stats.point_count }} 个知识点 / {{ stats.relation_count }} 条关系
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <el-button :icon="Plus" @click="openCreate">新建知识点</el-button>
        <el-dropdown trigger="click" @command="extractTextbook">
          <el-button :icon="MagicStick">
            从课本抽取<el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="tb in textbooks" :key="tb.id" :command="tb.id">
                {{ tb.title }}
              </el-dropdown-item>
              <el-dropdown-item v-if="!textbooks.length" disabled>暂无课本</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button :icon="Connection" @click="suggestCross">发现跨学科关联</el-button>
      </div>
    </div>

    <!-- 筛选 + 图例 -->
    <div class="card mb-4 flex flex-wrap items-center gap-3 !py-3">
      <el-select v-model="filter.subject_id" placeholder="全部学科" clearable size="small"
        style="width:140px" @change="load">
        <el-option v-for="s in subjectOptions" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索知识点定位" size="small" clearable style="width:180px"
        @keyup.enter="locateByKeyword" />
      <el-button size="small" @click="locateByKeyword">定位</el-button>
      <div class="flex-1" />
      <div class="flex items-center gap-3 text-xs text-slate-500">
        <span><i class="inline-block w-4 h-0.5 align-middle" style="background:#6366f1" /> 前置</span>
        <span><i class="inline-block w-4 h-0.5 align-middle" style="background:#0ea5e9" /> 组成</span>
        <span><i class="inline-block w-4 border-t border-dashed align-middle" style="border-color:#94a3b8" /> 相关</span>
        <span><i class="inline-block w-4 h-0.5 align-middle" style="background:#f59e0b" /> 应用</span>
        <span><i class="inline-block w-4 border-t border-dashed align-middle" style="border-color:#ec4899" /> 跨学科</span>
      </div>
    </div>

    <!-- 图 -->
    <div class="card !p-0 overflow-hidden h-[55vh] sm:h-[60vh] lg:h-[calc(100vh-260px)]">
      <div v-if="!graph.nodes.length && !loading"
        class="h-full flex flex-col items-center justify-center text-slate-400 gap-2">
        <el-icon class="text-4xl"><Share /></el-icon>
        <p>暂无知识点。生成课件或点击「从课本抽取」即可自动构建图谱。</p>
      </div>
      <VChart v-else ref="chartRef" :option="chartOption" autoresize
        v-loading="loading" @click="onChartClick" style="height:100%" />
    </div>

    <!-- 知识点详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="current?.name || '知识点'" size="420px">
      <div v-if="current" class="space-y-4">
        <div class="flex flex-wrap gap-1.5">
          <el-tag v-if="current.subject_name" type="success" size="small">{{ current.subject_name }}</el-tag>
          <el-tag size="small" type="info">难度 {{ current.difficulty || 3 }}</el-tag>
          <el-tag v-for="t in current.tags || []" :key="t" size="small">{{ t }}</el-tag>
        </div>
        <div v-if="current.description">
          <p class="text-xs font-semibold text-slate-500 mb-1">说明</p>
          <p class="text-sm text-slate-700 whitespace-pre-wrap">{{ current.description }}</p>
        </div>

        <div v-if="current.prerequisite_path?.length">
          <p class="text-xs font-semibold text-slate-500 mb-1">建议先掌握（前置链）</p>
          <div class="flex flex-wrap items-center gap-1">
            <template v-for="(p, i) in current.prerequisite_path" :key="p.id">
              <el-tag size="small" class="cursor-pointer" @click="focusNode(p.id)">{{ p.name }}</el-tag>
              <el-icon v-if="i < current.prerequisite_path.length - 1" class="text-slate-300"><Right /></el-icon>
            </template>
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1">
            <p class="text-xs font-semibold text-slate-500">关联知识点</p>
            <el-button link type="primary" size="small" :icon="Plus" @click="openAddRelation">加关系</el-button>
          </div>
          <div v-if="current.neighbors?.length" class="space-y-1.5">
            <div v-for="(n, i) in current.neighbors" :key="i"
              class="flex items-center gap-2 text-sm bg-slate-50 rounded px-2 py-1.5">
              <el-tag size="small" :type="relTagType(n.type)">{{ relLabel(n.type) }}</el-tag>
              <span class="text-slate-400 text-xs">{{ n.direction === 'out' ? '→' : '←' }}</span>
              <span class="flex-1 truncate cursor-pointer hover:text-primary-600" @click="focusNode(n.other.id)">
                {{ n.other.name }}
                <span v-if="n.other.subject_name" class="text-xs text-slate-400">({{ n.other.subject_name }})</span>
              </span>
              <el-tag v-if="n.status === 'pending'" size="small" type="warning">待审核</el-tag>
              <template v-if="n.status === 'pending'">
                <el-button link type="success" size="small" @click="reviewRelation(n, 'approved')">通过</el-button>
                <el-button link type="danger" size="small" @click="reviewRelation(n, 'rejected')">拒绝</el-button>
              </template>
              <el-button v-else link type="danger" size="small" :icon="Delete" @click="removeRelation(n)" />
            </div>
          </div>
          <p v-else class="text-xs text-slate-400">暂无关联，点击「加关系」建立联系。</p>
        </div>

        <div v-if="current.courseware_ids?.length" class="text-xs text-slate-400">
          被 {{ current.courseware_ids.length }} 个课件引用
        </div>

        <div class="pt-2 border-t border-slate-100">
          <el-popconfirm title="确定删除该知识点及其关系？" @confirm="removeNode">
            <template #reference>
              <el-button type="danger" plain size="small" :icon="Delete">删除知识点</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
    </el-drawer>

    <!-- 新建知识点 -->
    <el-dialog v-model="createVisible" title="新建知识点" width="480px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="如：一元二次方程的解法" />
        </el-form-item>
        <el-form-item label="学科">
          <el-select v-model="createForm.subject_id" placeholder="选择学科" clearable style="width:100%">
            <el-option v-for="s in subjectOptions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-rate v-model="createForm.difficulty" :max="5" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 添加关系 -->
    <el-dialog v-model="relVisible" title="添加关系" width="480px">
      <el-form label-width="80px">
        <el-form-item label="源">
          <el-input :model-value="current?.name" disabled />
        </el-form-item>
        <el-form-item label="关系">
          <el-select v-model="relForm.rel_type" style="width:100%">
            <el-option label="前置（先学源，再学目标）" value="prerequisite" />
            <el-option label="组成（源是目标的一部分）" value="part_of" />
            <el-option label="相关" value="related" />
            <el-option label="应用（源应用于目标）" value="application" />
            <el-option label="对比（易混）" value="contrast" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标">
          <el-select v-model="relForm.to_id" filterable remote :remote-method="searchTargets"
            :loading="searching" placeholder="搜索目标知识点" style="width:100%">
            <el-option v-for="o in targetOptions" :key="o.id" :label="o.name" :value="o.id"
              :disabled="o.id === current?.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="relVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRelation">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { knowledgeApi, textbookApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { ElMessage } from 'element-plus'
import { Plus, MagicStick, Connection, Share, Delete, ArrowDown, Right } from '@element-plus/icons-vue'
import type { KgGraph, KgNode, KgNeighbor, Textbook } from '@/types'

import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([GraphChart, TooltipComponent, LegendComponent, CanvasRenderer])

const edu = useEducationStore()
const loading = ref(false)
const submitting = ref(false)
const graph = ref<KgGraph>({ nodes: [], edges: [] })
const stats = ref({ point_count: 0, relation_count: 0 })
const textbooks = ref<Textbook[]>([])
const chartRef = ref()

const filter = reactive({ subject_id: null as number | null })
const keyword = ref('')

// 学科选项与年级联动（跟随全局年级）
const subjectOptions = computed(() =>
  edu.selectedGradeId ? edu.subjectsOfGrade(edu.selectedGradeId) : edu.filteredSubjects)

const REL_META: Record<string, { label: string; color: string; dashed: boolean; tag: any }> = {
  prerequisite: { label: '前置', color: '#6366f1', dashed: false, tag: 'primary' },
  part_of: { label: '组成', color: '#0ea5e9', dashed: false, tag: 'info' },
  related: { label: '相关', color: '#94a3b8', dashed: true, tag: 'info' },
  application: { label: '应用', color: '#f59e0b', dashed: false, tag: 'warning' },
  contrast: { label: '对比', color: '#ef4444', dashed: true, tag: 'danger' },
}
const relLabel = (t: string) => REL_META[t]?.label || t
const relTagType = (t: string) => REL_META[t]?.tag || 'info'

const SUBJECT_COLORS = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6']

const chartOption = computed(() => {
  const subjects = Array.from(new Set(graph.value.nodes.map(n => n.subject_name || '未分类')))
  const categories = subjects.map(s => ({ name: s }))
  const catIndex = (s?: string) => Math.max(0, subjects.indexOf(s || '未分类'))
  const nodes = graph.value.nodes.map(n => ({
    id: n.id,
    name: n.name,
    category: catIndex(n.subject_name),
    symbolSize: 22 + (n.difficulty || 3) * 4,
    value: n.subject_name || '',
    itemStyle: { color: SUBJECT_COLORS[catIndex(n.subject_name) % SUBJECT_COLORS.length] },
  }))
  const links = graph.value.edges.map(e => {
    const meta = REL_META[e.type] || REL_META.related
    const color = e.cross_subject ? '#ec4899' : meta.color
    const pending = e.status === 'pending'
    return {
      source: e.source, target: e.target,
      lineStyle: {
        color, width: 1 + (e.weight || 0.5) * 2,
        type: (e.cross_subject || meta.dashed) ? 'dashed' : 'solid',
        opacity: pending ? 0.45 : 0.8, curveness: 0.08,
      },
    }
  })
  return {
    tooltip: { formatter: (p: any) => (p.dataType === 'node' ? `${p.data.name}<br/>${p.data.value}` : '') },
    legend: [{ data: subjects, top: 8, textStyle: { fontSize: 11 } }],
    series: [{
      type: 'graph', layout: 'force', roam: true, draggable: true,
      categories, data: nodes, links,
      label: { show: true, position: 'right', fontSize: 11, formatter: '{b}' },
      edgeSymbol: ['none', 'arrow'], edgeSymbolSize: 7,
      force: { repulsion: 260, edgeLength: 120, gravity: 0.08 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 4 } },
    }],
  }
})

async function load() {
  loading.value = true
  try {
    const [g, s] = await Promise.all([
      knowledgeApi.getGraph({
        subject_id: filter.subject_id || undefined,
        grade_id: edu.selectedGradeId || undefined,
        limit: 400,
      }) as any,
      knowledgeApi.getStats() as any,
    ])
    graph.value = g
    stats.value = s
  } catch (e: any) {
    if (e?.response?.status === 503) ElMessage.warning('知识图谱功能未启用')
  } finally {
    loading.value = false
  }
}

async function loadTextbooks() {
  const res = await textbookApi.list({
    grade_id: edu.selectedGradeId || undefined,
    subject_id: edu.selectedSubjectId || undefined,
    page: 1, page_size: 200,
  }) as any
  textbooks.value = res.items || []
}

watchDebounced(() => [edu.selectedGradeId, edu.selectedSubjectId], () => {
  filter.subject_id = edu.selectedSubjectId || null
  load(); loadTextbooks()
}, { debounce: 250 })

// ── 详情抽屉 ──
const drawerVisible = ref(false)
const current = ref<KgNode | null>(null)

async function openNode(id: string) {
  try {
    current.value = await knowledgeApi.getPoint(id) as any
    drawerVisible.value = true
  } catch {
    ElMessage.error('知识点不存在')
  }
}
function onChartClick(p: any) {
  if (p.dataType === 'node') openNode(p.data.id)
}
function focusNode(id: string) { openNode(id) }

// ── 抽取 / 发现 ──
async function extractTextbook(textbookId: number) {
  await knowledgeApi.extractTextbook(textbookId)
  ElMessage.success('已提交抽取任务，知识点将陆续入图')
  setTimeout(() => { void load() }, 4000)
}
async function suggestCross() {
  await knowledgeApi.suggestCrossSubject()
  ElMessage.success('已提交跨学科关联发现任务，完成后可在节点中审核')
  setTimeout(() => { void load() }, 4000)
}
async function locateByKeyword() {
  if (!keyword.value.trim()) return
  const rs = await knowledgeApi.searchPoints({
    keyword: keyword.value, subject_id: filter.subject_id || undefined, limit: 1,
  }) as any
  if (rs.length) openNode(rs[0].id)
  else ElMessage.info('未找到匹配的知识点')
}

// ── 新建知识点 ──
const createVisible = ref(false)
const createForm = reactive({
  name: '', subject_id: null as number | null, difficulty: 3, description: '',
})
function openCreate() {
  createForm.name = ''
  createForm.subject_id = edu.selectedSubjectId || null
  createForm.difficulty = 3
  createForm.description = ''
  createVisible.value = true
}
async function submitCreate() {
  if (!createForm.name.trim()) { ElMessage.warning('请填写名称'); return }
  submitting.value = true
  try {
    await knowledgeApi.createPoint({
      name: createForm.name, subject_id: createForm.subject_id,
      grade_id: edu.selectedGradeId || null,
      difficulty: createForm.difficulty, description: createForm.description,
    })
    ElMessage.success('已创建')
    createVisible.value = false
    await load()
  } finally { submitting.value = false }
}

// ── 关系 ──
const relVisible = ref(false)
const relForm = reactive({ rel_type: 'related', to_id: '' })
const targetOptions = ref<KgNode[]>([])
const searching = ref(false)
function openAddRelation() {
  relForm.rel_type = 'related'
  relForm.to_id = ''
  targetOptions.value = []
  relVisible.value = true
}
async function searchTargets(q: string) {
  searching.value = true
  try {
    targetOptions.value = await knowledgeApi.searchPoints({ keyword: q, limit: 20 }) as any
  } finally { searching.value = false }
}
async function submitRelation() {
  if (!current.value || !relForm.to_id) { ElMessage.warning('请选择目标知识点'); return }
  const target = targetOptions.value.find(o => o.id === relForm.to_id)
  const crossSubject = !!(target && current.value.subject_id && target.subject_id
    && target.subject_id !== current.value.subject_id)
  submitting.value = true
  try {
    await knowledgeApi.createRelation({
      from_id: current.value.id, to_id: relForm.to_id,
      rel_type: relForm.rel_type, cross_subject: crossSubject,
    })
    ElMessage.success('已建立关系')
    relVisible.value = false
    await openNode(current.value.id)
    await load()
  } finally { submitting.value = false }
}
async function removeRelation(n: KgNeighbor) {
  if (!current.value) return
  const from = n.direction === 'out' ? current.value.id : n.other.id
  const to = n.direction === 'out' ? n.other.id : current.value.id
  await knowledgeApi.deleteRelation({ from_id: from, to_id: to, rel_type: n.type })
  ElMessage.success('已删除关系')
  await openNode(current.value.id)
  await load()
}
async function reviewRelation(n: KgNeighbor, status: string) {
  if (!current.value) return
  const from = n.direction === 'out' ? current.value.id : n.other.id
  const to = n.direction === 'out' ? n.other.id : current.value.id
  await knowledgeApi.updateRelationStatus({ from_id: from, to_id: to, rel_type: n.type, status })
  ElMessage.success(status === 'approved' ? '已通过' : '已拒绝')
  await openNode(current.value.id)
  await load()
}
async function removeNode() {
  if (!current.value) return
  await knowledgeApi.deletePoint(current.value.id)
  ElMessage.success('已删除')
  drawerVisible.value = false
  await load()
}

onMounted(() => {
  filter.subject_id = edu.selectedSubjectId || null
  load()
  loadTextbooks()
})
</script>
