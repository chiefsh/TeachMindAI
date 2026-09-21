<template>
  <div class="min-h-screen bg-slate-100">
    <div class="bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-3 sticky top-0 z-10">
      <div class="flex-1 min-w-0">
        <p class="font-bold text-slate-800 truncate">{{ title || '分享内容' }}</p>
        <p v-if="expiresAt" class="text-xs text-slate-400">有效期至 {{ expiresAt }}</p>
      </div>
      <el-button
        v-if="kind === 'animation' && frameUrl"
        size="small"
        type="primary"
        @click="enterPresent"
      >全屏演示</el-button>
      <el-tag size="small" type="info">免登录预览</el-tag>
    </div>

    <div v-if="loading" class="text-center py-24 text-slate-400">
      <el-icon class="text-4xl animate-spin"><Loading /></el-icon>
      <p class="mt-3">正在打开分享…</p>
    </div>
    <div v-else-if="error" class="text-center py-24 text-slate-500">
      <el-icon class="text-4xl text-rose-400"><CircleClose /></el-icon>
      <p class="mt-3">{{ error }}</p>
    </div>

    <div v-else-if="needPassword && !payload" class="max-w-sm mx-auto mt-16 bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
      <p class="font-semibold text-slate-800 mb-1">此分享需要密码</p>
      <p class="text-sm text-slate-500 mb-4">请向分享人索取访问密码</p>
      <el-input
        v-model="password"
        type="password"
        show-password
        placeholder="请输入密码"
        @keyup.enter="unlock"
      />
      <el-button type="primary" class="w-full mt-4" :loading="unlocking" @click="unlock">打开</el-button>
    </div>

    <template v-else-if="payload">
      <iframe
        v-if="(kind === 'courseware' || kind === 'courseware_version') && frameUrl"
        ref="frameEl"
        :src="frameUrl"
        sandbox="allow-scripts allow-same-origin allow-popups allow-modals"
        allow="fullscreen *"
        allowfullscreen
        class="w-full border-0 bg-white"
        :style="{ height: 'calc(100vh - 56px)' }"
      />

      <iframe
        v-else-if="kind === 'animation' && frameUrl"
        :src="frameUrl"
        sandbox="allow-scripts allow-same-origin"
        allow="fullscreen"
        class="w-full border-0 bg-white"
        :style="{ height: 'calc(100vh - 56px)' }"
      />

      <div v-else-if="kind === 'question_analysis'" class="max-w-3xl mx-auto p-4 space-y-3">
        <div class="flex items-center gap-2 text-sm text-slate-500">
          <el-tag v-if="payload.grade_name" size="small" type="info">{{ payload.grade_name }}</el-tag>
          <el-tag v-if="payload.subject_name" size="small" type="success">{{ payload.subject_name }}</el-tag>
          <span>{{ questions.length }} 题</span>
        </div>
        <div v-for="q in questions" :key="q.id" class="bg-white rounded-xl border border-slate-200 p-4">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-sm font-semibold text-slate-800">第 {{ q.seq }} 题</span>
            <el-tag size="small" type="info">{{ typeLabel(q.question_type) }}</el-tag>
            <el-tag v-if="q.analysis_status === 'done' && q.analysis_content" size="small" type="success">已解析</el-tag>
          </div>
          <p class="text-sm text-slate-700 mt-2 math-text" v-html="renderMathText(q.content)" />
          <div v-if="q.options" class="mt-2 space-y-1">
            <p v-for="(v, k) in q.options" :key="k" class="text-sm text-slate-600 math-text">
              <span>{{ k }}. </span><span v-html="renderMathText(String(v))" />
            </p>
          </div>
          <el-button size="small" class="mt-3" :type="revealed.has(q.id) ? 'primary' : 'default'" @click="toggle(q.id)">
            答案解析
          </el-button>
          <div v-if="revealed.has(q.id)" class="mt-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
            <template v-if="q.analysis_content && q.analysis_status === 'done'">
              <iframe
                v-if="q.analysis_html && blobUrls[q.id]"
                :src="blobUrls[q.id]"
                class="w-full rounded-lg border border-slate-200 bg-white mb-3"
                style="height:360px" frameborder="0"
              />
              <div v-if="q.analysis_content?.思路" class="mb-2 math-text">
                <span class="font-semibold text-indigo-600">思路：</span>
                <span class="text-sm text-slate-700" v-html="renderMathText(q.analysis_content.思路)" />
              </div>
              <div v-for="(st, i) in q.analysis_content?.steps || []" :key="i" class="mb-2 math-text">
                <p class="text-sm font-medium text-slate-800">
                  步骤{{ i + 1 }}<span v-if="st.title">：</span>
                  <span v-if="st.title" v-html="renderMathText(st.title)" />
                </p>
                <p v-if="st.detail" class="text-sm text-slate-600" v-html="renderMathText(st.detail)" />
                <p v-if="st.formula" class="text-sm text-slate-600" v-html="renderMathText(wrapFormula(st.formula))" />
              </div>
              <div v-if="q.analysis_content?.知识点?.length" class="mb-2">
                <span class="font-semibold text-slate-700">知识点：</span>
                <el-tag v-for="(kp, i) in q.analysis_content.知识点" :key="i" size="small" class="mr-1">{{ kp }}</el-tag>
              </div>
              <div v-if="q.analysis_content?.易错点" class="mb-2 math-text">
                <span class="font-semibold text-amber-600">易错点：</span>
                <span class="text-sm text-slate-700" v-html="renderMathText(q.analysis_content.易错点)" />
              </div>
              <div v-if="q.analysis_content?.答案" class="math-text">
                <span class="font-semibold text-green-600">答案：</span>
                <span class="text-sm text-slate-700" v-html="renderMathText(q.analysis_content.答案)" />
              </div>
            </template>
            <template v-else>
              <span class="font-semibold text-green-600">答案：</span>
              <span v-if="q.answer" class="text-sm text-slate-700 math-text" v-html="renderMathText(q.answer)" />
              <span v-else class="text-sm text-slate-400">该题暂无答案</span>
            </template>
          </div>
        </div>
      </div>
    </template>
  </div>

  <Teleport to="body">
    <div
      v-if="presenting && presentSrc"
      ref="presentRoot"
      class="fixed inset-0 z-[4000] bg-black flex flex-col"
    >
      <div class="h-11 shrink-0 flex items-center gap-3 px-4 bg-black/80 text-white">
        <span class="truncate flex-1 text-sm">{{ presentTitle || title }}</span>
        <span class="text-xs text-white/50">Esc 退出全屏</span>
        <el-button size="small" @click="exitPresent">退出</el-button>
      </div>
      <iframe
        class="flex-1 w-full border-0 bg-black"
        :src="presentSrc"
        sandbox="allow-scripts allow-same-origin allow-popups allow-modals"
        allow="fullscreen"
      />
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { Loading, CircleClose } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { publicApi } from '@/api/modules'
import { createIframeBlob } from '@/utils/coursewareFrame'
import { buildRevealDeck } from '@/utils/revealDeck'
import { buildLessonPage } from '@/utils/lessonPage'
import { renderMathText } from '@/utils/mathText'
import { pageTypeLabel } from '@/utils/coursewarePages'

const route = useRoute()
const token = String(route.params.token || '')

const loading = ref(true)
const unlocking = ref(false)
const error = ref('')
const needPassword = ref(false)
const password = ref('')
const title = ref('')
const expiresAt = ref('')
const kind = ref('')
const payload = ref<Record<string, any> | null>(null)
const frameUrl = ref('')
const frameEl = ref<HTMLIFrameElement | null>(null)
const presenting = ref(false)
const presentRoot = ref<HTMLElement | null>(null)
const presentTitle = ref('')
const presentLabUrl = ref('')
const presentSrc = computed(() => presentLabUrl.value || (kind.value === 'animation' ? frameUrl.value : ''))
const revealed = reactive(new Set<number>())
const blobUrls = reactive<Record<number, string>>({})

const questions = computed<any[]>(() => payload.value?.questions || [])

function wrapFormula(f: string): string {
  const s = String(f || '').trim()
  if (!s) return ''
  return s.includes('$') ? s : `$${s}$`
}

function typeLabel(t: string) {
  return ({
    single_choice: '单选', multi_choice: '多选', fill_blank: '填空',
    short_answer: '简答', essay: '论述', true_false: '判断', calculation: '计算',
  } as Record<string, string>)[t] || pageTypeLabel(t)
}

function toggle(id: number) {
  if (revealed.has(id)) revealed.delete(id)
  else revealed.add(id)
}

function applyPayload(data: { title: string; expires_at: string; resource_type: string; payload: Record<string, any> }) {
  title.value = data.title
  expiresAt.value = dayjs(data.expires_at).format('YYYY-MM-DD HH:mm')
  kind.value = data.resource_type
  payload.value = data.payload
  if (data.resource_type === 'courseware' || data.resource_type === 'courseware_version') {
    const p = data.payload
    const ctx = [p.grade_name, p.subject_name].filter(Boolean).join(' · ')
    const html = p.render_style === 'html'
      ? buildLessonPage(p.content, p.images || {}, { subtitle: ctx, theme: p.theme, subject: p.subject_name || '' })
      : buildRevealDeck(p.content, p.images || {}, { theme: p.theme, subject: p.subject_name || '' })
    if (frameUrl.value) URL.revokeObjectURL(frameUrl.value)
    frameUrl.value = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }))
  } else if (data.resource_type === 'animation') {
    if (frameUrl.value) URL.revokeObjectURL(frameUrl.value)
    frameUrl.value = createIframeBlob(data.payload?.html || '')
  } else {
    for (const q of data.payload.questions || []) {
      if (q.analysis_html) blobUrls[q.id] = createIframeBlob(q.analysis_html)
    }
  }
}

async function enterPresent(html?: string, labTitle?: string) {
  if (typeof html === 'string' && html) {
    if (presentLabUrl.value) URL.revokeObjectURL(presentLabUrl.value)
    presentLabUrl.value = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }))
    presentTitle.value = labTitle || '实验台'
  } else {
    presentTitle.value = title.value
  }
  if (!presentSrc.value) return
  presenting.value = true
  await nextTick()
  const el = presentRoot.value as any
  const req = el?.requestFullscreen || el?.webkitRequestFullscreen || el?.msRequestFullscreen
  if (req) {
    try { await req.call(el) } catch { /* 铺满遮罩即可 */ }
  }
}

function exitPresent() {
  presenting.value = false
  const doc = document as any
  if (document.fullscreenElement || doc.webkitFullscreenElement) {
    const exit = document.exitFullscreen || doc.webkitExitFullscreen
    if (exit) exit.call(document)
  }
  if (presentLabUrl.value) {
    URL.revokeObjectURL(presentLabUrl.value)
    presentLabUrl.value = ''
  }
}

function onPresentKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && presenting.value) exitPresent()
}

async function unlock(pwd?: string) {
  const usePwd = (pwd ?? password.value).trim()
  if (needPassword.value && !usePwd) return
  unlocking.value = true
  try {
    const data = await publicApi.shareAccess(token, usePwd || undefined)
    if (usePwd) sessionStorage.setItem(`share_pwd_${token}`, usePwd)
    applyPayload(data)
  } catch {
    sessionStorage.removeItem(`share_pwd_${token}`)
  } finally {
    unlocking.value = false
  }
}

function onCwFullscreenMessage(e: MessageEvent) {
  const d: any = e.data
  if (!d || d.__cw !== true || d.type !== 'fullscreen') return
  if (frameEl.value && e.source !== frameEl.value.contentWindow) return
  if (d.action === 'exit') {
    exitPresent()
    return
  }
  void enterPresent(d.srcdoc || '', d.title)
}

onMounted(async () => {
  window.addEventListener('keydown', onPresentKey)
  window.addEventListener('message', onCwFullscreenMessage)
  loading.value = true
  try {
    const meta = await publicApi.shareMeta(token)
    title.value = meta.title || ''
    if (meta.expires_at) expiresAt.value = dayjs(meta.expires_at).format('YYYY-MM-DD HH:mm')
    if (meta.status === 'not_found') error.value = '分享链接不存在'
    else if (meta.status === 'revoked') error.value = '分享链接已被取消'
    else if (meta.status === 'expired') error.value = '分享链接已过期'
    else if (meta.status === 'need_password') {
      needPassword.value = true
      const saved = sessionStorage.getItem(`share_pwd_${token}`) || ''
      if (saved) {
        password.value = saved
        await unlock(saved)
      }
    }
    else await unlock()
  } catch {
    error.value = '分享链接不存在或已失效'
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onPresentKey)
  window.removeEventListener('message', onCwFullscreenMessage)
  exitPresent()
  if (frameUrl.value) URL.revokeObjectURL(frameUrl.value)
  for (const u of Object.values(blobUrls)) URL.revokeObjectURL(u)
})
</script>
