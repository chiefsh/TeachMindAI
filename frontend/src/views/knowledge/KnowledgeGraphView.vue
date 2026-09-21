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

    <!-- 筛选 -->
    <div class="card mb-4 flex flex-wrap items-center gap-3 !py-3">
      <el-select v-model="filter.subject_id" placeholder="全部学科" clearable size="small"
        style="width:140px" @change="load">
        <el-option v-for="s in subjectOptions" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索知识点定位" size="small" clearable style="width:180px"
        @keyup.enter="locateByKeyword" />
      <el-button size="small" @click="locateByKeyword">定位</el-button>
      <el-radio-group v-model="viewMode" size="small" :disabled="!!focusedId">
        <el-radio-button value="core">只看核心</el-radio-button>
        <el-radio-button value="all">显示全部</el-radio-button>
      </el-radio-group>
      <el-button v-if="focusedId" size="small" @click="exitFocus">退出聚焦</el-button>
      <span class="text-xs" style="color: var(--ink-muted)">
        展示 {{ visibleGraph.nodes.length }} / {{ graph.nodes.length }}
        <template v-if="focusedId"> · 邻域</template>
      </span>
    </div>

    <!-- 图 -->
    <div class="card kg-stage !p-0 overflow-hidden">
      <div v-if="!graph.nodes.length && !loading" class="kg-empty">
        <div class="kg-empty-mark">
          <el-icon class="text-3xl"><Share /></el-icon>
        </div>
        <p class="kg-empty-title">还没有知识点</p>
        <p class="kg-empty-hint">生成课件，或从课本抽取，图谱会自动长出来。</p>
      </div>
      <div v-else class="relative w-full h-full kg-canvas">
        <div class="kg-overlay kg-overlay-top">
          <span class="kg-chip">{{ chartHint }}</span>
        </div>
        <div class="kg-overlay kg-overlay-legend">
          <span class="kg-leg"><i class="kg-leg-line kg-leg-pre" />前置</span>
          <span class="kg-leg"><i class="kg-leg-line kg-leg-part" />组成</span>
          <span class="kg-leg"><i class="kg-leg-line kg-leg-rel" />相关</span>
          <span class="kg-leg"><i class="kg-leg-line kg-leg-app" />应用</span>
          <span class="kg-leg"><i class="kg-leg-line kg-leg-cross" />跨学科</span>
          <span class="kg-leg kg-leg-note">点越大越核心</span>
        </div>
        <div v-if="graphIndex.subjects.length > 1" class="kg-overlay kg-overlay-subjects">
          <span v-for="(s, i) in graphIndex.subjects" :key="s" class="kg-sub">
            <i :style="{ background: subjectSwatch(i) }" />{{ s }}
          </span>
        </div>
        <VChart ref="chartRef" class="kg-chart" :option="chartOption" :update-options="{ notMerge: true }"
          autoresize v-loading="loading"
          @click="onChartClick" @finished="onChartFinished" @graphroam="onGraphRoam" />
      </div>
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
import { ref, reactive, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { knowledgeApi, textbookApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import { useAppearanceStore } from '@/stores/appearance'
import { ElMessage } from 'element-plus'
import { Plus, MagicStick, Connection, Share, Delete, ArrowDown, Right } from '@element-plus/icons-vue'
import type { KgGraph, KgNode, KgEdge, KgNeighbor, Textbook } from '@/types'

import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([GraphChart, TooltipComponent, CanvasRenderer])

const CORE_MAX = 96
const CORE_EXPAND_CAP = 120
const LABEL_CORE_COUNT = 36
const FOCUS_HOPS = 2

/** 多学科时的区分色（首色运行时用主题主色替换）。单学科不走彩虹，只用主色深浅。 */
const SUBJECT_HUES = ['#4f46e5', '#0f766e', '#b45309', '#9f1239', '#0369a1', '#57534e']

type ThemeTokens = {
  primary: string
  surface: string
  ink: string
  inkSecondary: string
  inkMuted: string
  border: string
  pill: string
}

function cssVar(name: string, fallback: string) {
  if (typeof document === 'undefined') return fallback
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

function readTheme(): ThemeTokens {
  return {
    primary: cssVar('--color-primary', '#4f46e5'),
    surface: cssVar('--surface', '#fffcf7'),
    ink: cssVar('--ink', '#1c1917'),
    inkSecondary: cssVar('--ink-secondary', '#57534e'),
    inkMuted: cssVar('--ink-muted', '#78716c'),
    border: cssVar('--border', '#e4e0d6'),
    pill: cssVar('--pill-bg', '#f3efe6'),
  }
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '').trim()
  const full = h.length === 3 ? h.split('').map(c => c + c).join('') : h
  const n = parseInt(full.slice(0, 6), 16)
  if (Number.isNaN(n)) return [79, 70, 229]
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

function rgbToHex(r: number, g: number, b: number) {
  const c = (n: number) => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, '0')
  return `#${c(r)}${c(g)}${c(b)}`
}

function mixHex(a: string, b: string, t: number) {
  const [ar, ag, ab] = hexToRgb(a)
  const [br, bg, bb] = hexToRgb(b)
  return rgbToHex(ar + (br - ar) * t, ag + (bg - ag) * t, ab + (bb - ab) * t)
}

function hexAlpha(hex: string, a: number) {
  const [r, g, b] = hexToRgb(hex)
  return `rgba(${r}, ${g}, ${b}, ${a})`
}

const edu = useEducationStore()
const appearance = useAppearanceStore()
const themeTokens = ref<ThemeTokens>(readTheme())
watch(() => appearance.theme, () => { themeTokens.value = readTheme() })

function subjectSwatch(i: number) {
  if (i === 0) return themeTokens.value.primary
  return SUBJECT_HUES[i % SUBJECT_HUES.length]
}
const loading = ref(false)
const submitting = ref(false)
const graph = ref<KgGraph>({ nodes: [], edges: [] })
const stats = ref({ point_count: 0, relation_count: 0 })
const textbooks = ref<Textbook[]>([])
const chartRef = ref<InstanceType<typeof VChart> | null>(null)

const filter = reactive({ subject_id: null as number | null })
const keyword = ref('')
const viewMode = ref<'core' | 'all'>('core')
const focusedId = ref<string | null>(null)
const pendingHighlight = ref<string | null>(null)
let extraLabelsOn = false
let freezeTimer: ReturnType<typeof setTimeout> | null = null

const subjectOptions = computed(() =>
  edu.selectedGradeId ? edu.subjectsOfGrade(edu.selectedGradeId) : edu.filteredSubjects)

const REL_META: Record<string, { label: string; color: string; dashed: boolean; tag: any; width: number }> = {
  prerequisite: { label: '前置', color: '#4f46e5', dashed: false, tag: 'primary', width: 2.4 },
  part_of: { label: '组成', color: '#0284c7', dashed: false, tag: 'info', width: 2.1 },
  related: { label: '相关', color: '#94a3b8', dashed: true, tag: 'info', width: 1 },
  application: { label: '应用', color: '#d97706', dashed: false, tag: 'warning', width: 2.2 },
  contrast: { label: '对比', color: '#dc2626', dashed: true, tag: 'danger', width: 1.6 },
}
const relLabel = (t: string) => REL_META[t]?.label || t
const relTagType = (t: string) => REL_META[t]?.tag || 'info'

function shortName(name: string, max = 14) {
  const s = (name || '').replace(/\s+/g, '')
  return s.length > max ? `${s.slice(0, max)}…` : s
}

function buildAdj(nodes: KgNode[], edges: KgEdge[]) {
  const ids = new Set(nodes.map(n => n.id))
  const degree = new Map<string, number>()
  const adj = new Map<string, Set<string>>()
  for (const n of nodes) {
    degree.set(n.id, 0)
    adj.set(n.id, new Set())
  }
  for (const e of edges) {
    if (!ids.has(e.source) || !ids.has(e.target) || e.source === e.target) continue
    degree.set(e.source, (degree.get(e.source) || 0) + 1)
    degree.set(e.target, (degree.get(e.target) || 0) + 1)
    adj.get(e.source)!.add(e.target)
    adj.get(e.target)!.add(e.source)
  }
  return { degree, adj }
}

function neighborhood(start: string, adj: Map<string, Set<string>>, hops: number) {
  const seen = new Set<string>([start])
  let frontier = [start]
  for (let h = 0; h < hops; h++) {
    const next: string[] = []
    for (const u of frontier) {
      for (const v of adj.get(u) || []) {
        if (!seen.has(v)) { seen.add(v); next.push(v) }
      }
    }
    frontier = next
  }
  return seen
}

function pickCore(nodes: KgNode[], degree: Map<string, number>, adj: Map<string, Set<string>>) {
  if (nodes.length <= CORE_MAX) return nodes
  const ranked = [...nodes].sort((a, b) => (degree.get(b.id) || 0) - (degree.get(a.id) || 0))
  const picked = new Set<string>()
  for (const n of ranked) {
    if ((degree.get(n.id) || 0) < 1) continue
    picked.add(n.id)
    if (picked.size >= CORE_MAX) break
  }
  const hubs = ranked.filter(n => picked.has(n.id)).slice(0, 8)
  for (const h of hubs) {
    for (const v of adj.get(h.id) || []) {
      if (picked.size >= CORE_EXPAND_CAP) break
      picked.add(v)
    }
  }
  if (picked.size < 20) {
    for (const n of nodes) {
      picked.add(n.id)
      if (picked.size >= 80) break
    }
  }
  return nodes.filter(n => picked.has(n.id))
}

const graphIndex = computed(() => {
  const { degree, adj } = buildAdj(graph.value.nodes, graph.value.edges)
  const subjects = Array.from(new Set(graph.value.nodes.map(n => n.subject_name || '未分类')))
  return { degree, adj, subjects }
})

const visibleGraph = computed(() => {
  const { degree, adj } = graphIndex.value
  let nodes = graph.value.nodes
  if (focusedId.value && adj.has(focusedId.value)) {
    const keep = neighborhood(focusedId.value, adj, FOCUS_HOPS)
    nodes = nodes.filter(n => keep.has(n.id))
  } else if (viewMode.value === 'core') {
    nodes = pickCore(nodes, degree, adj)
  }
  const ids = new Set(nodes.map(n => n.id))
  const edges = graph.value.edges.filter(e => ids.has(e.source) && ids.has(e.target))
  return { nodes, edges }
})

const chartHint = computed(() => {
  if (focusedId.value) return '已聚焦 2 跳邻域 · 点击其他点可继续游走'
  if (viewMode.value === 'all') return '全图概览 · 滚轮放大后显示更多名称 · 悬停查看邻接'
  return '核心主干 · 点击节点展开邻域'
})

function nodeFill(n: KgNode, degree: number, subjects: string[], tokens: ThemeTokens) {
  const multi = subjects.length > 1
  const subIdx = Math.max(0, subjects.indexOf(n.subject_name || '未分类'))
  const base = multi ? subjectSwatch(subIdx) : tokens.primary
  const pale = (multi ? 0.14 : 0.1) + (1 - Math.min(degree, 8) / 8) * (multi ? 0.28 : 0.5)
  return mixHex(base, tokens.surface, pale)
}

function nodeLabelStyle(
  show: boolean,
  opts: { isFocus: boolean; hub: boolean; focusing: boolean; tokens: ThemeTokens; name: string },
) {
  const { isFocus, hub, focusing, tokens, name } = opts
  return {
    show,
    position: 'bottom',
    distance: 6,
    fontSize: isFocus ? 12 : hub ? 11 : 10,
    fontWeight: isFocus || hub ? 600 : 500,
    color: tokens.ink,
    backgroundColor: hexAlpha(tokens.surface, isFocus ? 0.96 : 0.88),
    borderColor: isFocus ? tokens.primary : hexAlpha(tokens.border, 0.9),
    borderWidth: isFocus ? 1 : 0.5,
    borderRadius: 6,
    padding: [3, 7],
    formatter: shortName(name, focusing ? 16 : 14),
  }
}

function edgeLook(e: KgEdge, tokens: ThemeTokens) {
  const meta = REL_META[e.type] || REL_META.related
  if (e.cross_subject) {
    return { color: '#9f3860', dashed: true, width: 1.8, directed: true }
  }
  switch (e.type) {
    case 'prerequisite':
      return { color: tokens.primary, dashed: false, width: 2.2, directed: true }
    case 'part_of':
      return { color: '#3d6b8a', dashed: false, width: 1.8, directed: true }
    case 'application':
      return { color: '#b45309', dashed: false, width: 1.9, directed: true }
    case 'contrast':
      return { color: '#b91c1c', dashed: true, width: 1.4, directed: false }
    default:
      return { color: tokens.inkMuted, dashed: meta.dashed, width: 1, directed: false }
  }
}

const chartOption = computed(() => {
  const tokens = themeTokens.value
  const { degree, subjects } = graphIndex.value
  const rankedVisible = [...visibleGraph.value.nodes]
    .sort((a, b) => (degree.get(b.id) || 0) - (degree.get(a.id) || 0))
  const labelIds = new Set(rankedVisible.slice(0, LABEL_CORE_COUNT).map(n => n.id))
  const focusing = !!focusedId.value
  const overview = viewMode.value === 'all' && !focusing

  const nodes = visibleGraph.value.nodes.map(n => {
    const d = degree.get(n.id) || 0
    const isFocus = n.id === focusedId.value
    const hub = d >= 4
    const color = nodeFill(n, d, subjects, tokens)
    const sizeBase = overview ? 7 : focusing ? 16 : 12
    const symbolSize = sizeBase + Math.min(d, 12) * (overview ? 1.5 : 2.1) + (isFocus ? 8 : 0)
    const showLabel = focusing || (!overview && (labelIds.has(n.id) || hub || isFocus))
    return {
      id: n.id,
      name: n.name,
      shortName: shortName(n.name),
      degree: d,
      symbolSize,
      value: n.subject_name || '',
      z: d + (isFocus ? 50 : 0),
      itemStyle: {
        color,
        opacity: overview ? (d >= 2 ? 0.92 : 0.42) : (d >= 2 || isFocus ? 1 : 0.78),
        borderColor: isFocus ? tokens.primary : tokens.surface,
        borderWidth: isFocus ? 2.5 : 1.6,
        shadowBlur: isFocus ? 14 : hub ? 8 : 0,
        shadowColor: hexAlpha(color, isFocus ? 0.32 : 0.18),
      },
      label: nodeLabelStyle(showLabel, { isFocus, hub, focusing, tokens, name: n.name }),
    }
  })

  const links = visibleGraph.value.edges.map(e => {
    const look = edgeLook(e, tokens)
    const pending = e.status === 'pending'
    const hub = Math.min(degree.get(e.source) || 0, degree.get(e.target) || 0)
    const width = look.width + (e.weight || 0.5) * 0.45
    return {
      source: e.source, target: e.target,
      value: 48 + hub * 10,
      lineStyle: {
        color: look.color,
        width: overview ? Math.max(0.7, width * 0.55) : width,
        type: look.dashed ? 'dashed' as const : 'solid' as const,
        opacity: pending ? 0.28 : (overview ? 0.28 : (look.dashed ? 0.45 : 0.62)),
        curveness: look.dashed ? 0.18 : 0.1,
        cap: 'round' as const,
      },
      symbol: look.directed ? ['none', 'arrow'] : ['none', 'none'],
      symbolSize: look.directed ? (overview ? 6 : 8) : 0,
    }
  })

  const force = focusing
    ? { repulsion: 360, edgeLength: [88, 150], gravity: 0.1, friction: 0.58, layoutAnimation: true }
    : overview
      ? { repulsion: 140, edgeLength: [32, 78], gravity: 0.2, friction: 0.74, layoutAnimation: true }
      : { repulsion: 280, edgeLength: [56, 128], gravity: 0.16, friction: 0.62, layoutAnimation: true }

  return {
    backgroundColor: 'transparent',
    animationDuration: 600,
    animationEasingUpdate: 'cubicOut' as const,
    tooltip: {
      confine: true,
      backgroundColor: tokens.surface,
      borderColor: tokens.border,
      borderWidth: 1,
      padding: [10, 12],
      textStyle: { color: tokens.ink, fontSize: 12 },
      extraCssText: 'border-radius:10px;box-shadow:var(--shadow-card);',
      formatter: (p: any) => {
        if (p.dataType !== 'node') return ''
        const d = p.data
        return `<div style="font-weight:600;margin-bottom:4px">${d.name}</div>`
          + `<div style="color:${tokens.inkMuted};font-size:11px">${d.value || '未分类'} · 关联 ${d.degree || 0} 个</div>`
      },
    },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      data: nodes,
      links,
      top: 52,
      bottom: 68,
      left: 28,
      right: subjects.length > 1 ? 132 : 28,
      scaleLimit: { min: 0.35, max: 4 },
      edgeSymbol: ['none', 'none'],
      labelLayout: { hideOverlap: true },
      force,
      emphasis: {
        focus: 'adjacency',
        scale: true,
        label: {
          show: true,
          fontSize: 12,
          fontWeight: 600,
          formatter: (p: any) => p.data?.name || p.name,
          backgroundColor: hexAlpha(tokens.surface, 0.96),
          borderColor: tokens.primary,
          borderWidth: 1,
          borderRadius: 6,
          padding: [3, 7],
          color: tokens.ink,
        },
        itemStyle: { borderColor: tokens.primary, borderWidth: 2 },
        lineStyle: { width: 2.8, opacity: 1 },
      },
      blur: {
        itemStyle: { opacity: 0.14 },
        lineStyle: { opacity: 0.06 },
        label: { opacity: 0.12 },
      },
    }],
  }
})

async function load() {
  loading.value = true
  focusedId.value = null
  pendingHighlight.value = null
  extraLabelsOn = false
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
    await nextTick()
    try { chartInst()?.resize?.() } catch { /* ignore */ }
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

const drawerVisible = ref(false)
const current = ref<KgNode | null>(null)

function chartInst() {
  const c = chartRef.value as any
  if (!c) return null
  return c.chart?.value ?? c.chart ?? c
}

function clearFreezeTimer() {
  if (freezeTimer) {
    clearTimeout(freezeTimer)
    freezeTimer = null
  }
}

function freezeLayoutIfSettled() {
  const inst = chartInst()
  const data = inst?.getOption?.()?.series?.[0]?.data
  if (!Array.isArray(data) || !data.length) return
  const ready = data.every((d: any) => Number.isFinite(d?.x) && Number.isFinite(d?.y))
  if (!ready) return
  try { inst.setOption({ series: [{ layout: 'none' }] }, { lazyUpdate: true }) } catch { /* ignore */ }
}

function highlightNode(id: string) {
  const chart = chartInst()
  if (!chart?.dispatchAction) return
  const idx = visibleGraph.value.nodes.findIndex(n => n.id === id)
  if (idx < 0) return
  chart.dispatchAction({ type: 'downplay', seriesIndex: 0 })
  chart.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: idx })
  chart.dispatchAction({ type: 'focusNodeAdjacency', seriesIndex: 0, dataIndex: idx })
}

function onChartFinished() {
  clearFreezeTimer()
  freezeTimer = setTimeout(freezeLayoutIfSettled, 1200)
  if (pendingHighlight.value) {
    highlightNode(pendingHighlight.value)
    pendingHighlight.value = null
  }
}

function onGraphRoam(ev: any) {
  if (viewMode.value !== 'all' || focusedId.value) return
  const zoom = Number(ev?.zoom ?? 1)
  const want = zoom >= 1.55
  if (want === extraLabelsOn) return
  extraLabelsOn = want
  const chart = chartInst()
  if (!chart?.getOption) return
  const series = chart.getOption()?.series?.[0]
  if (!series?.data) return
  const data = series.data.map((d: any) => ({
    ...d,
    label: {
      ...(typeof d.label === 'object' ? d.label : {}),
      show: want && (d.degree || 0) >= 2,
    },
  }))
  chart.setOption({ series: [{ layout: 'none', data }] })
}

function enterFocus(id: string) {
  extraLabelsOn = false
  const same = focusedId.value === id
  focusedId.value = id
  pendingHighlight.value = id
  if (same) highlightNode(id)
}

function exitFocus() {
  extraLabelsOn = false
  focusedId.value = null
  pendingHighlight.value = null
  const chart = chartInst()
  chart?.dispatchAction?.({ type: 'downplay', seriesIndex: 0 })
}

async function openNode(id: string) {
  try {
    current.value = await knowledgeApi.getPoint(id) as any
    drawerVisible.value = true
  } catch {
    ElMessage.error('知识点不存在')
  }
}

function onChartClick(p: any) {
  if (p.dataType !== 'node' || !p.data?.id) return
  enterFocus(p.data.id)
  openNode(p.data.id)
}

function focusNode(id: string) {
  if (graph.value.nodes.some(n => n.id === id)) enterFocus(id)
  openNode(id)
}

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
  if (!rs.length) { ElMessage.info('未找到匹配的知识点'); return }
  const id = rs[0].id as string
  if (!graph.value.nodes.some(n => n.id === id)) {
    ElMessage.info('已打开详情，但该点不在当前筛选图中')
    await openNode(id)
    return
  }
  enterFocus(id)
  await openNode(id)
  await nextTick()
}

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
  themeTokens.value = readTheme()
  filter.subject_id = edu.selectedSubjectId || null
  load()
  loadTextbooks()
})
onBeforeUnmount(() => {
  clearFreezeTimer()
})
</script>

<style scoped>
.kg-stage {
  height: min(68vh, calc(100vh - 220px));
  min-height: 420px;
  background: var(--surface);
}
.kg-stage:hover {
  box-shadow: var(--shadow-card), inset 0 1px 0 rgba(255, 255, 255, 0.72);
}
.kg-canvas {
  background:
    radial-gradient(ellipse 70% 60% at 50% 42%, var(--login-orb-a), transparent 62%),
    var(--surface);
}
.kg-chart,
.kg-stage :deep(x-vue-echarts) {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 420px;
  background: transparent;
}
.kg-overlay {
  position: absolute;
  z-index: 2;
  pointer-events: none;
}
.kg-overlay-top {
  top: 12px;
  left: 12px;
}
.kg-chip {
  display: inline-block;
  padding: 5px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--surface) 86%, transparent);
  border: 1px solid var(--border-subtle);
  color: var(--ink-muted);
  font-size: 11px;
  letter-spacing: 0.01em;
}
.kg-overlay-legend {
  left: 12px;
  bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  max-width: min(92%, 520px);
  padding: 8px 10px;
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  border: 1px solid var(--border-subtle);
}
.kg-overlay-subjects {
  top: 12px;
  right: 12px;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
  max-width: 46%;
}
.kg-leg {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--ink-secondary);
}
.kg-leg-note {
  color: var(--ink-muted);
}
.kg-leg-line {
  display: inline-block;
  width: 16px;
  height: 0;
  border-top-width: 2px;
  border-top-style: solid;
}
.kg-leg-pre { border-color: var(--color-primary); }
.kg-leg-part { border-color: #3d6b8a; border-top-width: 3px; }
.kg-leg-rel { border-color: var(--ink-muted); border-top-style: dashed; }
.kg-leg-app { border-color: #b45309; }
.kg-leg-cross { border-color: #9f3860; border-top-style: dashed; }
.kg-sub {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  border: 1px solid var(--border-subtle);
  font-size: 11px;
  color: var(--ink-secondary);
}
.kg-sub i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.kg-empty {
  height: 100%;
  min-height: 420px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background:
    radial-gradient(ellipse 60% 50% at 50% 48%, var(--login-orb-a), transparent 64%),
    var(--surface);
}
.kg-empty-mark {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--pill-bg);
  color: var(--color-primary);
}
.kg-empty-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}
.kg-empty-hint {
  font-size: 13px;
  color: var(--ink-muted);
}
@media (prefers-reduced-transparency: reduce) {
  .kg-chip,
  .kg-overlay-legend,
  .kg-sub {
    background: var(--surface);
  }
}
@media (max-width: 767px) {
  .kg-overlay-subjects {
    max-width: 58%;
  }
  .kg-stage {
    min-height: 360px;
    height: min(58vh, calc(100vh - 200px));
  }
}
</style>
