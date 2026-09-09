<template>
  <el-drawer v-model="open" title="个人信息" size="400px">
    <div class="space-y-5">
      <div class="flex items-center gap-3">
        <el-avatar :size="48" class="bg-primary-600 text-white">
          {{ auth.teacher?.real_name?.charAt(0) || '师' }}
        </el-avatar>
        <div>
          <p class="font-medium text-slate-800">{{ auth.teacher?.real_name }}</p>
          <p class="text-xs text-slate-400">{{ auth.teacher?.username }}</p>
        </div>
      </div>
      <div v-if="roleNames" class="text-xs text-slate-500">角色：{{ roleNames }}</div>

      <el-form :model="profileForm" label-width="88px">
        <el-form-item label="用户名">
          <el-input :model-value="auth.teacher?.username" disabled />
        </el-form-item>
        <el-form-item label="真实姓名">
          <el-input v-model="profileForm.real_name" maxlength="64" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="profileForm.email" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="profileSaving" @click="saveProfile">保存资料</el-button>
        </el-form-item>
      </el-form>

      <el-form :model="pwdForm" label-width="88px">
        <p class="text-sm font-semibold text-slate-700 mb-3">修改密码</p>
        <el-form-item label="原密码">
          <el-input v-model="pwdForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwdForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="pwdForm.confirm" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="pwdSaving" @click="savePassword">更新密码</el-button>
        </el-form-item>
      </el-form>

      <div>
        <p class="text-sm font-semibold text-slate-700 mb-2">教学范围</p>
        <div v-for="ts in mySubjects" :key="ts.id" class="text-sm text-slate-600 py-1">
          {{ ts.grade.name }} · {{ ts.subject.name }}
        </div>
        <el-empty v-if="!mySubjects.length" :image-size="48" description="由管理员在用户管理中绑定" />
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { educationApi, authApi } from '@/api/modules'
import { ElMessage } from 'element-plus'
import type { TeacherSubject } from '@/types'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const open = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const auth = useAuthStore()
const profileForm = reactive({ real_name: '', email: '' })
const profileSaving = ref(false)
const pwdForm = reactive({ old_password: '', new_password: '', confirm: '' })
const pwdSaving = ref(false)
const mySubjects = ref<TeacherSubject[]>([])

const roleNames = computed(() => (auth.teacher?.roles || []).map(r => r.name).join('、'))

watch(open, async (v) => {
  if (!v) return
  profileForm.real_name = auth.teacher?.real_name || ''
  profileForm.email = auth.teacher?.email || ''
  try {
    mySubjects.value = await educationApi.getMySubjects()
  } catch {
    mySubjects.value = []
  }
})

async function saveProfile() {
  const real_name = profileForm.real_name.trim()
  const email = profileForm.email.trim()
  if (!real_name) { ElMessage.warning('请填写真实姓名'); return }
  if (!email) { ElMessage.warning('请填写邮箱'); return }
  profileSaving.value = true
  try {
    await auth.updateProfile({ real_name, email })
    ElMessage.success('资料已保存')
  } finally {
    profileSaving.value = false
  }
}

async function savePassword() {
  if (!pwdForm.old_password) { ElMessage.warning('请输入原密码'); return }
  if (pwdForm.new_password.length < 6) { ElMessage.warning('新密码至少 6 位'); return }
  if (pwdForm.new_password !== pwdForm.confirm) { ElMessage.warning('两次输入的新密码不一致'); return }
  pwdSaving.value = true
  try {
    await authApi.changePassword({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    ElMessage.success('密码已更新')
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm = ''
  } finally {
    pwdSaving.value = false
  }
}
</script>
