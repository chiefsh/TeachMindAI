<template>
  <el-dialog
    :model-value="modelValue"
    title="分享链接"
    width="520px"
    @update:model-value="$emit('update:modelValue', $event)"
    @open="onOpen"
  >
    <p class="text-sm text-slate-500 mb-3">
      生成免登录链接，发给学生或同事即可打开「{{ resourceTitle || '这份内容' }}」。
    </p>
    <div class="space-y-3">
      <div>
        <p class="text-xs text-slate-500 mb-1">有效期</p>
        <el-input-number v-model="expireDays" :min="1" :max="90" :step="1" />
        <span class="text-xs text-slate-400 ml-2">天（默认 5 天）</span>
      </div>
      <div>
        <p class="text-xs text-slate-500 mb-1">访问密码（可选）</p>
        <el-input
          v-model="password"
          type="password"
          show-password
          maxlength="64"
          placeholder="留空则打开链接即可查看"
        />
      </div>
      <div class="flex justify-end">
        <el-button type="primary" :icon="Share" :loading="creating" @click="create">生成链接</el-button>
      </div>
    </div>

    <div v-if="latestUrl" class="mt-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
      <p class="text-xs text-slate-500 mb-2">刚生成的链接</p>
      <div class="flex gap-3 items-start">
        <img v-if="qr" :src="qr" alt="二维码" class="w-28 h-28 rounded border border-slate-200 bg-white" />
        <div class="flex-1 min-w-0 space-y-2">
          <el-input :model-value="latestUrl" readonly size="small" />
          <p v-if="latestPassword" class="text-xs text-amber-700">
            访问密码：<span class="font-mono font-semibold">{{ latestPassword }}</span>
            （请单独告知对方，关闭后不再显示）
          </p>
          <el-button size="small" type="primary" @click="copy(latestUrl)">复制链接</el-button>
        </div>
      </div>
    </div>

    <div class="mt-5">
      <p class="text-xs font-semibold text-slate-600 mb-2">已生成的链接</p>
      <el-table :data="links" size="small" empty-text="还没有分享链接">
        <el-table-column label="状态" width="88">
          <template #default="{ row }">
            <el-tag v-if="isExpired(row)" size="small" type="info">已过期</el-tag>
            <el-tag v-else size="small" type="success">有效</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="密码" width="64">
          <template #default="{ row }">{{ row.has_password ? '有' : '无' }}</template>
        </el-table-column>
        <el-table-column label="到期" min-width="140">
          <template #default="{ row }">{{ formatTime(row.expires_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" link :disabled="isExpired(row)" @click="copy(shareUrl(row.token))">复制</el-button>
            <el-button size="small" link type="danger" @click="revoke(row)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Share } from '@element-plus/icons-vue'
import QRCode from 'qrcode'
import dayjs from 'dayjs'
import { shareApi } from '@/api/modules'
import type { ShareLink, ShareResourceType } from '@/types'

const props = defineProps<{
  modelValue: boolean
  resourceType: ShareResourceType
  resourceId: number
  resourceTitle?: string
}>()
defineEmits<{ 'update:modelValue': [boolean] }>()

const expireDays = ref(5)
const password = ref('')
const creating = ref(false)
const links = ref<ShareLink[]>([])
const latestUrl = ref('')
const latestPassword = ref('')
const qr = ref('')

function shareUrl(token: string) {
  return `${window.location.origin}/share/${token}`
}

function isExpired(row: ShareLink) {
  return dayjs(row.expires_at).isBefore(dayjs())
}

function formatTime(v: string) {
  return dayjs(v).format('YYYY-MM-DD HH:mm')
}

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

async function loadLinks() {
  if (!props.resourceId) return
  try {
    links.value = await shareApi.list(props.resourceType, props.resourceId)
  } catch { /* handled */ }
}

async function onOpen() {
  expireDays.value = 5
  password.value = ''
  latestUrl.value = ''
  latestPassword.value = ''
  qr.value = ''
  await loadLinks()
}

async function create() {
  creating.value = true
  try {
    const pwd = password.value.trim()
    const row = await shareApi.create({
      resource_type: props.resourceType,
      resource_id: props.resourceId,
      expire_days: expireDays.value,
      password: pwd || null,
    })
    latestUrl.value = shareUrl(row.token)
    latestPassword.value = pwd
    try {
      qr.value = await QRCode.toDataURL(latestUrl.value, { width: 224, margin: 1 })
    } catch { qr.value = '' }
    password.value = ''
    ElMessage.success('分享链接已生成')
    await loadLinks()
  } finally {
    creating.value = false
  }
}

async function revoke(row: ShareLink) {
  try {
    await ElMessageBox.confirm('取消后该链接将立即失效，确定吗？', '取消分享', { type: 'warning' })
    await shareApi.revoke(row.id)
    if (latestUrl.value === shareUrl(row.token)) {
      latestUrl.value = ''
      latestPassword.value = ''
      qr.value = ''
    }
    await loadLinks()
  } catch { /* cancel */ }
}
</script>
