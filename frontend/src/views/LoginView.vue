<template>
  <div class="min-h-[100dvh] grid lg:grid-cols-2" style="background: var(--canvas)">
    <aside class="relative hidden lg:flex flex-col justify-center overflow-hidden px-14 py-12 login-brand">
      <div class="login-orb login-orb-a" />
      <div class="login-orb login-orb-b" />
      <div class="login-grid" />

      <div class="relative z-10 max-w-md">
        <div class="login-lockup">
          <img src="@/assets/logo-mark.png" alt="知序台" class="login-mark" />
          <div>
            <p class="login-name">知序台</p>
            <p class="login-tagline">让知识与教学变得有序</p>
          </div>
        </div>
        <p class="mt-10 text-[15px] leading-relaxed" style="color: var(--ink-secondary)">
          备课、出题、阅卷分析与知识图谱，<br />
          集中在一个安静好用的工作台。
        </p>
        <ul class="mt-8 space-y-4">
          <li v-for="item in highlights" :key="item.title" class="flex items-start gap-3">
            <span class="login-mark-bar" />
            <div>
              <p class="text-sm font-medium" style="color: var(--ink)">{{ item.title }}</p>
              <p class="text-[13px] mt-0.5 leading-relaxed" style="color: var(--ink-muted)">{{ item.desc }}</p>
            </div>
          </li>
        </ul>
      </div>
    </aside>

    <div class="relative flex items-center justify-center p-5 sm:p-8">
      <div class="absolute top-3 right-3 sm:top-5 sm:right-5">
        <ThemeToggle />
      </div>
      <div class="w-full max-w-[400px]">
        <div class="lg:hidden text-center mb-8">
          <div class="login-lockup login-lockup-center">
            <img src="@/assets/logo-mark.png" alt="知序台" class="login-mark-mobile" />
            <div>
              <p class="login-name">知序台</p>
              <p class="login-tagline">让知识与教学变得有序</p>
            </div>
          </div>
        </div>

        <div class="hidden lg:block mb-8">
          <h1 class="text-2xl font-semibold tracking-tight" style="color: var(--ink); letter-spacing: -0.03em">教师登录</h1>
          <p class="mt-1.5 text-sm" style="color: var(--ink-muted)">使用学校账号进入工作台</p>
        </div>

        <div class="card !p-6 sm:!p-8">
          <h2 class="lg:hidden text-lg font-semibold mb-5" style="color: var(--ink)">教师登录</h2>
          <el-form :model="form" :rules="rules" ref="formRef" label-position="top" hide-required-asterisk @submit.prevent="handleLogin">
            <el-form-item prop="username" label="用户名">
              <el-input
                v-model="form.username"
                size="large"
                autocomplete="username"
              />
            </el-form-item>
            <el-form-item prop="password" label="密码">
              <el-input
                v-model="form.password"
                type="password"
                size="large"
                autocomplete="current-password"
                show-password
                @keyup.enter="handleLogin"
              />
            </el-form-item>
            <el-button
              type="primary"
              size="large"
              class="w-full !h-11 !rounded-[10px] !text-[15px] mt-1"
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
import ThemeToggle from '@/components/layout/ThemeToggle.vue'

const router = useRouter()
const auth = useAuthStore()
const edu = useEducationStore()

const highlights = [
  { title: '备课出课件', desc: '按课本与知识点生成可演示的课堂内容' },
  { title: '作业与阅卷', desc: '组卷、布置、原卷批改和错题沉淀' },
  { title: '学情看得见', desc: '成绩、试题分析与知识图谱连成一条线' },
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
  background: var(--canvas);
  border-right: 1px solid var(--border-subtle);
  color: var(--ink);
}
.login-lockup {
  display: flex;
  align-items: center;
  gap: 14px;
}
.login-lockup-center {
  justify-content: center;
}
.login-mark {
  width: 52px;
  height: 52px;
  object-fit: contain;
  flex-shrink: 0;
}
.login-mark-mobile {
  width: 48px;
  height: 48px;
  object-fit: contain;
  flex-shrink: 0;
}
.login-name {
  font-size: 26px;
  font-weight: 650;
  letter-spacing: -0.03em;
  line-height: 1.15;
  color: var(--ink);
}
.login-tagline {
  margin-top: 6px;
  font-size: 13px;
  letter-spacing: 0.02em;
  color: var(--ink-muted);
}
.login-mark-bar {
  width: 2px;
  height: 14px;
  margin-top: 4px;
  border-radius: 99px;
  flex-shrink: 0;
  background: var(--el-color-primary);
  opacity: 0.55;
}
.login-orb {
  position: absolute;
  border-radius: 9999px;
  filter: blur(48px);
  pointer-events: none;
}
.login-orb-a {
  width: 280px;
  height: 280px;
  right: -60px;
  top: -40px;
  background: var(--login-orb-a);
}
.login-orb-b {
  width: 360px;
  height: 360px;
  left: -80px;
  bottom: -80px;
  background: var(--login-orb-b);
}
.login-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--login-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--login-grid) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at 30% 40%, black 20%, transparent 70%);
  pointer-events: none;
}
:deep(.el-form--label-top .el-form-item__label) {
  color: var(--ink-secondary);
  font-weight: 500;
  margin-bottom: 4px !important;
  line-height: 1.4;
}
</style>
