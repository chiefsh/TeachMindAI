<template>
  <div class="min-h-screen bg-slate-100">
    <div class="bg-white border-b border-slate-200 px-4 py-3 sticky top-0 z-10">
      <p class="font-bold text-slate-800 truncate">{{ meta?.title || '作业录入' }}</p>
      <p class="text-xs text-slate-400 mt-0.5">
        {{ meta?.paper_type === 'exam' ? '考试' : '作业' }}
        <template v-if="meta?.class_name"> · {{ meta.class_name }}</template>
      </p>
    </div>

    <div v-if="loading" class="text-center py-24 text-slate-400">加载中…</div>
    <div v-else-if="loadError" class="text-center py-24 text-slate-500 px-6">{{ loadError }}</div>

    <div v-else-if="!student" class="max-w-lg mx-auto p-4">
      <p class="text-sm font-medium text-slate-700 mb-2">请先选择学生</p>
      <el-input v-model="keyword" placeholder="搜索姓名或学号" clearable class="mb-3" />
      <p v-if="!filtered.length" class="text-center text-sm text-slate-400 py-10">没有匹配的学生</p>
      <button
        v-for="s in filtered"
        :key="s.id"
        type="button"
        class="w-full mb-2 px-4 py-3 rounded-xl bg-white border border-slate-200 text-left active:bg-slate-50"
        @click="pickStudent(s)"
      >
        <span class="text-base font-medium text-slate-800">{{ s.name }}</span>
        <span class="text-xs text-slate-400 ml-2">{{ s.student_no }}</span>
        <span class="float-right text-xs mt-1" :class="s.page_count ? 'text-green-600' : 'text-slate-400'">
          {{ s.page_count ? `已传 ${s.page_count} 页` : '未传' }}
        </span>
      </button>
    </div>

    <div v-else class="max-w-lg mx-auto p-4 pb-28">
      <div class="flex items-center justify-between mb-3">
        <div>
          <p class="text-base font-semibold text-slate-800">{{ student.name }}</p>
          <p class="text-xs text-slate-400">{{ student.student_no }} · 已上传 {{ student.page_count }} 页</p>
        </div>
        <el-button size="small" @click="student = null">换学生</el-button>
      </div>

      <div class="grid grid-cols-2 gap-3 mb-4">
        <button
          type="button"
          class="rounded-xl bg-white border border-slate-200 py-6 text-center active:bg-slate-50"
          @click="cameraRef?.click()"
        >
          <p class="text-base font-medium text-slate-800">拍照上传</p>
          <p class="text-xs text-slate-400 mt-1">打开后置摄像头</p>
        </button>
        <button
          type="button"
          class="rounded-xl bg-white border border-slate-200 py-6 text-center active:bg-slate-50"
          @click="albumRef?.click()"
        >
          <p class="text-base font-medium text-slate-800">相册多选</p>
          <p class="text-xs text-slate-400 mt-1">可一次选多张</p>
        </button>
      </div>
      <input ref="cameraRef" type="file" accept="image/*" capture="environment" class="hidden" @change="onPick($event, false)" />
      <input ref="albumRef" type="file" accept="image/*" multiple class="hidden" @change="onPick($event, true)" />

      <div v-if="pending.length" class="grid grid-cols-3 gap-2 mb-4">
        <div v-for="(p, i) in pending" :key="p.url" class="relative">
          <img :src="p.url" alt="" class="w-full h-24 object-cover rounded-lg bg-slate-200" />
          <button
            type="button"
            class="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/60 text-white text-xs"
            @click="removePending(i)"
          >×</button>
        </div>
      </div>
      <p v-else class="text-center text-xs text-slate-400 py-6">先拍照或从相册选图，可多次添加</p>
    </div>

    <div v-if="student" class="fixed bottom-0 inset-x-0 bg-white border-t border-slate-200 p-3">
      <el-button
        type="primary"
        class="w-full !h-11"
        :disabled="!pending.length || uploading"
        :loading="uploading"
        @click="submit"
      >
        {{ uploading ? '正在上传…' : `上传 ${pending.length} 张` }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { publicApi } from '@/api/modules'
import type { CollectMeta, CollectStudent } from '@/types'

const route = useRoute()
const token = String(route.params.token || '')
const loading = ref(true)
const loadError = ref('')
const meta = ref<CollectMeta | null>(null)
const keyword = ref('')
const student = ref<CollectStudent | null>(null)
const pending = ref<{ file: File; url: string }[]>([])
const uploading = ref(false)
const cameraRef = ref<HTMLInputElement | null>(null)
const albumRef = ref<HTMLInputElement | null>(null)

const filtered = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  const rows = meta.value?.students || []
  if (!q) return rows
  return rows.filter(s => s.name.toLowerCase().includes(q) || s.student_no.toLowerCase().includes(q))
})

function storageKey() {
  return `collect_stu_${token}`
}

function pickStudent(s: CollectStudent) {
  student.value = s
  sessionStorage.setItem(storageKey(), String(s.id))
}

function revokeAll() {
  pending.value.forEach(p => URL.revokeObjectURL(p.url))
  pending.value = []
}

function removePending(i: number) {
  const [row] = pending.value.splice(i, 1)
  if (row) URL.revokeObjectURL(row.url)
}

function loadImage(file: File) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => { URL.revokeObjectURL(url); resolve(img) }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('读图失败')) }
    img.src = url
  })
}

async function compressImage(file: File) {
  if (!file.type.startsWith('image/') || file.type === 'image/gif') return file
  try {
    const img = await loadImage(file)
    const max = 2000
    const { width, height } = img
    if (width <= max && height <= max && file.size < 1.2 * 1024 * 1024) return file
    const scale = Math.min(1, max / Math.max(width, height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(width * scale))
    canvas.height = Math.max(1, Math.round(height * scale))
    const ctx = canvas.getContext('2d')
    if (!ctx) return file
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise<Blob | null>(r => canvas.toBlob(r, 'image/jpeg', 0.82))
    if (!blob) return file
    return new File([blob], file.name.replace(/\.[^.]+$/, '.jpg'), { type: 'image/jpeg' })
  } catch {
    return file
  }
}

async function onPick(ev: Event, _multi: boolean) {
  const input = ev.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length) return
  if (pending.value.length + files.length > 20) {
    ElMessage.warning('一次最多准备 20 张')
    return
  }
  for (const raw of files) {
    const file = await compressImage(raw)
    pending.value.push({ file, url: URL.createObjectURL(file) })
  }
}

async function submit() {
  if (!student.value || !pending.value.length) return
  uploading.value = true
  try {
    const fd = new FormData()
    pending.value.forEach((p, i) => fd.append('files', p.file, p.file.name || `page-${i + 1}.jpg`))
    const res = await publicApi.collectPages(token, student.value.id, fd)
    ElMessage.success(`已上传，${res.student_name} 现有 ${res.page_count} 页`)
    revokeAll()
    await load(true)
    const again = meta.value?.students.find(s => s.id === student.value?.id)
    if (again) student.value = again
  } finally {
    uploading.value = false
  }
}

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    meta.value = await publicApi.collectMeta(token)
    loadError.value = ''
    const saved = Number(sessionStorage.getItem(storageKey()) || 0)
    if (!student.value && saved) {
      student.value = meta.value.students.find(s => s.id === saved) || null
    }
  } catch (e: any) {
    loadError.value = e?.response?.data?.detail || '录入链接无效或已失效'
  } finally {
    loading.value = false
  }
}

onMounted(load)
onBeforeUnmount(revokeAll)
</script>
