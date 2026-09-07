<template>
  <div class="min-h-screen bg-slate-100">
    <!-- 顶栏 -->
    <div class="bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-3 sticky top-0 z-10">
      <div class="flex-1 min-w-0">
        <p class="font-bold text-slate-800 truncate">{{ session?.title || '课堂互动' }}</p>
        <p class="text-xs text-slate-400">{{ studentName ? `作答人：${studentName}` : '请先填写姓名' }}</p>
      </div>
      <el-tag v-if="session && !session.is_open" type="info" size="small">已关闭</el-tag>
      <el-tag v-else-if="session" type="success" size="small">进行中</el-tag>
    </div>

    <!-- 加载/错误 -->
    <div v-if="loading" class="text-center py-24 text-slate-400">
      <el-icon class="text-4xl animate-spin"><Loading /></el-icon>
      <p class="mt-3">正在加载互动内容…</p>
    </div>
    <div v-else-if="loadError" class="text-center py-24 text-slate-500">
      <el-icon class="text-4xl text-rose-400"><CircleClose /></el-icon>
      <p class="mt-3">{{ loadError }}</p>
    </div>

    <template v-else>
      <!-- 互动主体 -->
      <div class="max-w-3xl mx-auto p-4">
        <div v-if="!interactiveSlides.length" class="bg-white rounded-xl p-10 text-center text-slate-400">
          本课件暂无互动环节
        </div>
        <template v-else>
          <div class="flex items-center justify-between mb-3">
            <span class="text-sm text-slate-500">互动 {{ current + 1 }} / {{ interactiveSlides.length }}</span>
            <span class="text-xs text-slate-400">{{ activeSlide?.title }}</span>
          </div>

          <div class="bg-white rounded-xl overflow-hidden shadow-sm border border-slate-200">
            <iframe
              v-if="activeSlide"
              :key="activeSlide.pos"
              ref="frameEl"
              :srcdoc="wrapInteractiveHtml(activeSlide.html, session?.theme || undefined)"
              sandbox="allow-scripts"
              class="w-full bg-white"
              style="height:72vh;border:0"
            ></iframe>
          </div>

          <div class="flex items-center justify-between mt-4">
            <el-button :disabled="current === 0" @click="current--" :icon="ArrowLeft">上一个</el-button>
            <span class="text-xs text-emerald-600" v-if="lastSavedAt">已记录你的作答 ✓</span>
            <el-button
              v-if="current < interactiveSlides.length - 1"
              type="primary" @click="current++"
            >下一个<el-icon class="ml-1"><ArrowRight /></el-icon></el-button>
            <el-button v-else type="success" @click="done = true">完成</el-button>
          </div>
        </template>
      </div>
    </template>

    <!-- 姓名输入 -->
    <el-dialog v-model="askName" title="开始前，请填写你的姓名" width="86%" :show-close="false"
               :close-on-click-modal="false" :close-on-press-escape="false" style="max-width:380px">
      <el-input v-model="nameInput" placeholder="请输入姓名" maxlength="20" @keyup.enter="confirmName" />
      <template #footer>
        <el-button type="primary" class="w-full" @click="confirmName">进入互动</el-button>
      </template>
    </el-dialog>

    <!-- 完成 -->
    <el-dialog v-model="done" title="互动完成" width="86%" style="max-width:380px">
      <p class="text-slate-600 text-center py-4">你已完成全部互动，作答已提交给老师 🎉</p>
      <template #footer>
        <el-button class="w-full" @click="done = false">返回继续查看</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ArrowRight, Loading, CircleClose } from '@element-plus/icons-vue'
import { publicApi } from '@/api/modules'
import { wrapInteractiveHtml } from '@/utils/coursewareFrame'
import type { PublicSession } from '@/types'

const route = useRoute()
const token = String(route.params.token || '')

const session = ref<PublicSession | null>(null)
const loading = ref(true)
const loadError = ref('')
const current = ref(0)
const done = ref(false)
const askName = ref(false)
const nameInput = ref('')
const studentName = ref('')
const lastSavedAt = ref(0)
const slideStart = ref(Date.now())

const interactiveSlides = computed<any[]>(() => {
  // 后端已仅下发含互动的页，并用 pos 标注其在原课件中的页序
  return (session.value?.content?.slides || []).filter((s: any) => !!s.html)
})
const activeSlide = computed(() => interactiveSlides.value[current.value] || null)

watch(current, () => { slideStart.value = Date.now() })

function confirmName() {
  const n = nameInput.value.trim()
  if (!n) { ElMessage.warning('请输入姓名'); return }
  studentName.value = n
  localStorage.setItem(`cw_name_${token}`, n)
  askName.value = false
  slideStart.value = Date.now()
}

async function onMessage(e: MessageEvent) {
  const d: any = e.data
  if (!d || d.__cw !== true || d.type !== 'interaction') return
  if (!studentName.value || !activeSlide.value) return
  const p = d.payload || {}
  try {
    await publicApi.submitRecord(token, {
      student_name: studentName.value,
      slide_index: activeSlide.value.pos ?? 0,
      component: p.component ?? activeSlide.value.type ?? null,
      question: p.question ?? null,
      answer: p.answer != null ? String(p.answer) : null,
      is_correct: typeof p.correct === 'boolean' ? p.correct : null,
      duration_ms: typeof p.duration_ms === 'number' ? p.duration_ms : (Date.now() - slideStart.value),
    })
    lastSavedAt.value = Date.now()
  } catch { /* 提交失败静默，避免打断学生 */ }
}

async function load() {
  loading.value = true
  try {
    session.value = await publicApi.getSession(token) as any
    if (!session.value?.is_open) {
      loadError.value = '本次互动已被老师关闭'
    }
  } catch {
    loadError.value = '互动会话不存在或已结束'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  window.addEventListener('message', onMessage)
  await load()
  if (!loadError.value) {
    const saved = localStorage.getItem(`cw_name_${token}`)
    if (saved) { studentName.value = saved } else { askName.value = true }
  }
})
onUnmounted(() => window.removeEventListener('message', onMessage))
</script>
