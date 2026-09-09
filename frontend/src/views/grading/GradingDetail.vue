<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4 sm:mb-6">
      <div>
        <div class="flex items-center gap-2">
          <el-button link type="primary" @click="$router.push('/grading')">← 布置列表</el-button>
        </div>
        <h1 class="page-title mt-1">{{ detail?.title || '批改' }}</h1>
        <p class="page-subtitle">
          {{ detail?.paper_type === 'exam' ? '考试' : '作业' }}
          · {{ detail?.class_name || '全年级' }}
          · {{ detail?.assigned_at }}
          <template v-if="detail?.full_score"> · 满分 {{ detail.full_score }}</template>
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <el-button type="primary" @click="openCollect">手机录入</el-button>
        <el-button @click="$router.push({ path: '/wrong-questions', query: { assignment_id: id, scope: 'assignment' } })">
          本次错题
        </el-button>
      </div>
    </div>

    <div class="card mb-4" v-if="detail">
      <p class="text-sm text-slate-600">
        花名册 {{ detail.student_count }} 人 · 已上传原卷 {{ detail.submitted_count }} · 已批完 {{ detail.graded_count }}
      </p>
    </div>

    <div class="grid lg:grid-cols-5 gap-4">
      <div class="lg:col-span-3 card !p-0 overflow-hidden">
        <div class="px-4 py-3 border-b border-slate-100 text-sm font-medium text-slate-700">学生</div>
        <p v-if="!loading && !(detail?.students || []).length" class="text-center text-sm text-slate-400 py-8">
          该班还没有学生。请先到
          <router-link to="/students" class="text-primary-600">班级/学生</router-link>
          录入花名册。
        </p>
        <div v-else class="table-scroll">
          <el-table :data="detail?.students || []" v-loading="loading" max-height="560">
            <el-table-column label="学号" width="90">
              <template #default="{ row }"><span class="text-xs">{{ row.student_no }}</span></template>
            </el-table-column>
            <el-table-column label="姓名" min-width="90">
              <template #default="{ row }"><span class="text-sm">{{ row.name }}</span></template>
            </el-table-column>
            <el-table-column label="原卷" width="70" align="center">
              <template #default="{ row }">
                <span class="text-xs" :class="row.page_count ? 'text-green-600' : 'text-slate-400'">
                  {{ row.page_count ? `${row.page_count} 页` : '未传' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="批改" width="80" align="center">
              <template #default="{ row }">
                <span class="text-xs">{{ row.graded_count }}/{{ row.question_count }}</span>
              </template>
            </el-table-column>
            <el-table-column v-if="detail?.paper_type === 'exam'" label="得分" width="80" align="center">
              <template #default="{ row }">
                <span class="text-sm font-medium">{{ row.total_score ?? '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="" width="80" align="center">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="goStudent(row.student_id)">批改</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <div class="lg:col-span-2 card !p-0 overflow-hidden">
        <div class="px-4 py-3 border-b border-slate-100 text-sm font-medium text-slate-700">各题错次</div>
        <div class="table-scroll">
          <el-table :data="detail?.question_stats || []" max-height="560">
            <el-table-column label="#" width="50" align="center">
              <template #default="{ row }">{{ row.sort_order }}</template>
            </el-table-column>
            <el-table-column label="题干" min-width="140">
              <template #default="{ row }">
                <p class="text-xs line-clamp-2 text-slate-700">{{ row.content }}</p>
              </template>
            </el-table-column>
            <el-table-column label="错次" width="64" align="center">
              <template #default="{ row }">
                <span class="text-sm font-semibold" :class="row.error_count ? 'text-red-500' : 'text-slate-400'">
                  {{ row.error_count }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="错误率" width="72" align="center">
              <template #default="{ row }">
                <span class="text-xs">{{ row.graded_count ? Math.round(row.error_rate * 100) + '%' : '—' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>

    <el-dialog v-model="showCollect" title="手机录入原卷" width="420px">
      <div v-loading="collectLoading" class="min-h-[8rem]">
        <p class="text-sm text-slate-600 mb-3">扫码后先选学生，再拍照或从相册上传多张原卷。</p>
        <div v-if="collectUrl" class="flex gap-4 items-center">
          <img v-if="collectQr" :src="collectQr" alt="二维码" class="w-36 h-36 rounded-lg border border-slate-200 bg-white" />
          <div class="flex-1 min-w-0">
            <p class="text-xs text-slate-400 mb-1">也可复制链接发给手机</p>
            <el-input :model-value="collectUrl" readonly size="small" />
            <el-button class="mt-2" size="small" type="primary" @click="copyCollect">复制链接</el-button>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import QRCode from 'qrcode'
import { gradingApi } from '@/api/modules'
import type { GradingAssignment } from '@/types'

const route = useRoute()
const router = useRouter()
const detail = ref<GradingAssignment | null>(null)
const loading = ref(false)
const id = ref(Number(route.params.id))

async function load() {
  loading.value = true
  try {
    detail.value = await gradingApi.getAssignment(id.value)
  } finally {
    loading.value = false
  }
}

function goStudent(studentId: number) {
  router.push(`/grading/${id.value}/student/${studentId}`)
}

const showCollect = ref(false)
const collectLoading = ref(false)
const collectUrl = ref('')
const collectQr = ref('')

function collectLink(token: string) {
  return `${window.location.origin}/c/${token}`
}

async function openCollect() {
  showCollect.value = true
  collectLoading.value = true
  try {
    const { token } = await gradingApi.collectToken(id.value)
    if (detail.value) detail.value.collect_token = token
    collectUrl.value = collectLink(token)
    collectQr.value = await QRCode.toDataURL(collectUrl.value, { width: 256, margin: 1 })
  } catch {
    collectUrl.value = ''
    collectQr.value = ''
  } finally {
    collectLoading.value = false
  }
}

async function copyCollect() {
  if (!collectUrl.value) return
  try {
    await navigator.clipboard.writeText(collectUrl.value)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('请手动复制链接')
  }
}

watch(() => route.params.id, (v) => {
  id.value = Number(v)
  load()
})

onMounted(load)
</script>
