<template>
  <div class="page">
    <div class="flex items-start justify-between mb-6 gap-3">
      <div>
        <h1 class="page-title">用户</h1>
        <p class="page-subtitle">增删改用户，绑定角色与年级/班级/科目。</p>
      </div>
      <el-button v-if="auth.can('user.manage')" type="primary" @click="openCreate">新建用户</el-button>
    </div>
    <div class="flex gap-2 mb-4">
      <el-input v-model="keyword" placeholder="搜索用户名/姓名/邮箱" class="max-w-xs" clearable @clear="load" @keyup.enter="load" />
      <el-button @click="load">查询</el-button>
    </div>
    <el-table :data="users" v-loading="loading">
      <el-table-column prop="real_name" label="姓名" width="120" />
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="email" label="邮箱" min-width="160" />
      <el-table-column label="角色" min-width="140">
        <template #default="{ row }">{{ (row.roles || []).map((r: any) => r.name).join('、') || '—' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button v-if="auth.can('user.manage')" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button
            v-if="auth.can('user.manage') && !row.is_super"
            link
            type="danger"
            @click="remove(row)"
          >停用</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="mt-4 flex justify-end">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>

    <el-dialog v-model="show" :title="editing ? '编辑用户' : '新建用户'" width="640px" destroy-on-close>
      <el-form label-width="96px">
        <el-form-item v-if="!editing" label="用户名">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item :label="editing ? '重置密码' : '密码'">
          <el-input v-model="form.password" type="password" show-password :placeholder="editing ? '留空则不改' : '至少 6 位'" />
        </el-form-item>
        <el-form-item v-if="!form.is_super" label="角色">
          <el-select v-model="form.role_ids" multiple style="width:100%" placeholder="绑定角色">
            <el-option v-for="r in assignableRoles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editing && !form.is_super" label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item v-if="!form.is_super" label="教学范围">
          <div class="w-full space-y-2">
            <div v-for="(row, idx) in form.assignments" :key="idx" class="flex gap-2">
              <el-select v-model="row.grade_id" placeholder="年级" class="flex-1" @change="row.subject_id = null; row.class_id = null">
                <el-option v-for="g in edu.grades" :key="g.id" :label="g.name" :value="g.id" />
              </el-select>
              <el-select v-model="row.class_id" placeholder="班级" class="flex-1" clearable>
                <el-option v-for="c in classesOf(row.grade_id)" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
              <el-select v-model="row.subject_id" placeholder="科目" class="flex-1">
                <el-option v-for="s in edu.subjectsOfGrade(row.grade_id)" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
              <el-button link type="danger" @click="form.assignments.splice(idx, 1)">移除</el-button>
            </div>
            <el-button size="small" @click="form.assignments.push({ grade_id: null, class_id: null, subject_id: null })">添加绑定</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="show = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, computed } from 'vue'
import { rbacApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import { useEducationStore } from '@/stores/education'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { OrgUser, RoleItem, ClassOption } from '@/types'

const auth = useAuthStore()
const edu = useEducationStore()
const users = ref<OrgUser[]>([])
const roles = ref<RoleItem[]>([])
const classes = ref<ClassOption[]>([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const show = ref(false)
const saving = ref(false)
const editing = ref<OrgUser | null>(null)

const form = reactive({
  username: '',
  real_name: '',
  email: '',
  password: '',
  role_ids: [] as number[],
  is_active: true,
  is_super: false,
  assignments: [] as { grade_id: number | null; class_id: number | null; subject_id: number | null }[],
})

const assignableRoles = computed(() => roles.value.filter(r => !r.is_super && r.code !== 'super_admin'))

function classesOf(gradeId: number | null) {
  if (!gradeId) return []
  return classes.value.filter(c => c.grade_id === gradeId)
}

async function load() {
  loading.value = true
  try {
    const res = await rbacApi.listUsers({
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    users.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function loadMeta() {
  roles.value = await rbacApi.listRoles()
  classes.value = await rbacApi.classOptions()
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    username: '', real_name: '', email: '', password: '',
    role_ids: [], is_active: true, is_super: false, assignments: [],
  })
  show.value = true
}

async function openEdit(row: OrgUser) {
  const full = await rbacApi.getUser(row.id)
  editing.value = full
  Object.assign(form, {
    username: full.username,
    real_name: full.real_name,
    email: full.email,
    password: '',
    role_ids: (full.roles || []).map(r => r.id),
    is_active: full.is_active,
    is_super: full.is_super,
    assignments: (full.assignments || []).map(a => ({
      grade_id: a.grade_id, class_id: a.class_id, subject_id: a.subject_id,
    })),
  })
  show.value = true
}

async function save() {
  if (!form.real_name.trim() || !form.email.trim()) { ElMessage.warning('请填写姓名和邮箱'); return }
  if (!editing.value && (!form.username.trim() || form.password.length < 6)) {
    ElMessage.warning('请填写用户名和至少 6 位密码')
    return
  }
  saving.value = true
  try {
    const assignments = form.assignments
      .filter(a => a.grade_id && a.subject_id)
      .map(a => ({ grade_id: a.grade_id, subject_id: a.subject_id, class_id: a.class_id || null }))
    if (editing.value) {
      const data: Record<string, unknown> = {
        real_name: form.real_name.trim(),
        email: form.email.trim(),
        is_active: form.is_active,
        role_ids: form.role_ids,
        assignments,
      }
      if (form.password) data.password = form.password
      await rbacApi.updateUser(editing.value.id, data)
    } else {
      await rbacApi.createUser({
        username: form.username.trim(),
        real_name: form.real_name.trim(),
        email: form.email.trim(),
        password: form.password,
        role_ids: form.role_ids,
        assignments,
      })
    }
    ElMessage.success('已保存')
    show.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(row: OrgUser) {
  await ElMessageBox.confirm(`确定停用用户「${row.real_name}」？`, '提示', { type: 'warning' })
  await rbacApi.deleteUser(row.id)
  ElMessage.success('已停用')
  await load()
}

onMounted(async () => {
  await edu.init()
  await loadMeta()
  await load()
})
</script>
