<template>
  <div class="min-h-screen grid lg:grid-cols-2" style="background: var(--canvas)">
    <!-- 品牌侧：桌面端 -->
    <aside class="relative hidden lg:flex flex-col justify-between overflow-hidden px-14 py-12 text-white login-brand">
      <div class="login-orb login-orb-a" />
      <div class="login-orb login-orb-b" />
      <div class="login-grid" />

      <div class="relative z-10">
        <div class="flex items-center gap-3">
          <div class="brand-mark w-11 h-11">
            <el-icon class="text-xl"><Reading /></el-icon>
          </div>
          <div>
            <p class="text-lg font-semibold tracking-wide">智课星</p>
            <p class="text-[11px] tracking-[0.18em] uppercase text-white/50">TeachMind</p>
          </div>
        </div>
      </div>

      <div class="relative z-10 max-w-md">
        <h1 class="text-4xl font-semibold leading-tight tracking-tight">
          智能辅助，<br />让教学更高效
        </h1>
        <p class="mt-4 text-white/65 text-[15px] leading-relaxed">
          备课、出题、阅卷分析与知识图谱，集中在一个安静好用的工作台。
        </p>
        <ul class="mt-10 space-y-4">
          <li v-for="item in highlights" :key="item.title" class="flex gap-3">
            <span class="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-white/10 text-sm font-medium">
              {{ item.n }}
            </span>
            <div>
              <p class="font-medium">{{ item.title }}</p>
              <p class="text-sm text-white/55 mt-0.5">{{ item.desc }}</p>
            </div>
          </li>
        </ul>
      </div>

      <p class="relative z-10 text-xs text-white/35">面向教师的备课与学情工作台</p>
    </aside>

    <!-- 表单侧 -->
    <div class="flex items-center justify-center p-5 sm:p-8">
      <div class="w-full max-w-[400px]">
        <div class="lg:hidden text-center mb-8">
          <div class="brand-mark w-14 h-14 mx-auto mb-4">
            <el-icon class="text-white text-2xl"><Reading /></el-icon>
          </div>
          <h1 class="text-2xl font-semibold tracking-tight" style="color: var(--ink)">智课星</h1>
          <p class="mt-1.5 text-sm" style="color: var(--ink-muted)">智能辅助，让教学更高效</p>
        </div>

        <div class="hidden lg:block mb-8">
          <h2 class="text-2xl font-semibold tracking-tight" style="color: var(--ink)">教师登录</h2>
          <p class="mt-1.5 text-sm" style="color: var(--ink-muted)">使用学校账号进入工作台</p>
        </div>

        <div class="card !p-6 sm:!p-8">
          <h2 class="lg:hidden text-lg font-semibold mb-5" style="color: var(--ink)">教师登录</h2>
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
              class="w-full !h-11 !rounded-xl !text-[15px] mt-1"
              :loading="loading"
              @click="handleLogin"
            >
              进入工作台
            </el-button>
          </el-form>

          <div
            v-if="enableRegist"
            class="mt-6 pt-5 text-center text-sm"
            style="border-top: 1px solid var(--border-subtle); color: var(--ink-muted)"
          >
            还没有账号？
            <el-button link type="primary" @click="showRegister = true">立即注册</el-button>
          </div>
        </div>
      </div>
    </div>

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

const highlights = [
  { n: '01', title: '备课出课件', desc: '按课本与知识点生成可演示的课堂内容' },
  { n: '02', title: '作业与阅卷', desc: '组卷、布置、原卷批改和错题沉淀' },
  { n: '03', title: '学情看得见', desc: '成绩、试题分析与知识图谱连成一条线' },
]

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

<style scoped>
.login-brand {
  background: linear-gradient(165deg, #161821 0%, #25204a 52%, #3730a3 100%);
}
.login-orb {
  position: absolute;
  border-radius: 9999px;
  filter: blur(40px);
  pointer-events: none;
}
.login-orb-a {
  width: 280px;
  height: 280px;
  right: -60px;
  top: -40px;
  background: rgba(99, 102, 241, 0.45);
}
.login-orb-b {
  width: 360px;
  height: 360px;
  left: -80px;
  bottom: -80px;
  background: rgba(245, 158, 11, 0.12);
}
.login-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at 30% 40%, black 20%, transparent 70%);
  pointer-events: none;
}
</style>
