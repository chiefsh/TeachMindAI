<template>
  <div class="min-h-screen bg-slate-50 flex items-center justify-center p-4">
    <div class="w-full max-w-md">
      <!-- Logo区 -->
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary-600 mb-4 shadow-sm">
          <el-icon class="text-white text-3xl"><Reading /></el-icon>
        </div>
        <h1 class="text-2xl sm:text-3xl font-bold text-slate-800">智课星</h1>
        <p class="text-slate-500 mt-2 text-sm">智能辅助，让教学更高效</p>
      </div>

      <!-- 登录卡片 -->
      <div class="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 sm:p-8">
        <h2 class="text-lg sm:text-xl font-semibold text-slate-800 mb-6">教师登录</h2>
        <el-form :model="form" :rules="rules" ref="formRef" @submit.prevent="handleLogin">
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="用户名"
              size="large"
              :prefix-icon="User"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              size="large"
              show-password
              :prefix-icon="Lock"
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            class="w-full !rounded-lg mt-2"
            :loading="loading"
            @click="handleLogin"
          >
            登 录
          </el-button>
        </el-form>

        <div v-if="enableRegist" class="mt-6 pt-5 border-t border-slate-100 text-center text-sm text-slate-500">
          还没有账号？
          <el-button link type="primary" @click="showRegister = true">立即注册</el-button>
        </div>
      </div>
    </div>

    <!-- 注册弹窗 -->
    <el-dialog v-model="showRegister" title="教师注册" width="420px" :close-on-click-modal="false">
      <el-form :model="regForm" :rules="regRules" ref="regFormRef" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="regForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="真实姓名" prop="real_name">
          <el-input v-model="regForm.real_name" placeholder="请输入真实姓名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="regForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="regForm.password" type="password" show-password placeholder="至少6位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRegister = false">取消</el-button>
        <el-button type="primary" :loading="regLoading" @click="handleRegister">注册</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useEducationStore } from '@/stores/education'
import { authApi } from '@/api/modules'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const auth = useAuthStore()
const edu = useEducationStore()

const formRef = ref()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名' }],
  password: [{ required: true, message: '请输入密码' }],
}

async function handleLogin() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    await auth.fetchMe()
    await edu.init({ forceBinding: true })
    router.push('/dashboard')
  } finally {
    loading.value = false
  }
}

const showRegister = ref(false)
const enableRegist = ref(false)
const regFormRef = ref()
const regLoading = ref(false)
const regForm = reactive({ username: '', real_name: '', email: '', password: '' })
const regRules = {
  username: [{ required: true, message: '请输入用户名' }],
  real_name: [{ required: true, message: '请输入真实姓名' }],
  email: [{ required: true, type: 'email', message: '请输入正确的邮箱' }],
  password: [{ required: true, min: 6, message: '密码至少6位' }],
}

async function handleRegister() {
  await regFormRef.value?.validate()
  regLoading.value = true
  try {
    await authApi.register(regForm)
    ElMessage.success('注册成功，请登录')
    showRegister.value = false
    form.username = regForm.username
  } finally {
    regLoading.value = false
  }
}

onMounted(async () => {
  try {
    const cfg = await authApi.getConfig()
    enableRegist.value = cfg.enable_regist !== false
  } catch {
    enableRegist.value = false
  }
})
</script>
