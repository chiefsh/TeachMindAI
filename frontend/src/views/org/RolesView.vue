<template>
  <div class="page">
    <div class="flex items-start justify-between mb-6">
      <div>
        <h1 class="page-title">角色</h1>
        <p class="page-subtitle">系统角色权限固定。可新建自定义角色并勾选模块功能。</p>
      </div>
      <el-button v-if="auth.can('role.manage')" type="primary" @click="openCreate">新建角色</el-button>
    </div>
    <el-table :data="roles" v-loading="loading">
      <el-table-column prop="name" label="名称" width="160" />
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.is_system" size="small">系统</el-tag>
          <el-tag v-else size="small" type="info">自定义</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="权限数">
        <template #default="{ row }">{{ row.permission_codes?.length || 0 }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button v-if="!row.is_system && auth.can('role.manage')" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="!row.is_system && auth.can('role.manage')" link type="danger" @click="remove(row)">删除</el-button>
          <span v-if="row.is_system" class="text-xs text-slate-400">不可改</span>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="show" :title="editing ? '编辑角色' : '新建角色'" width="640px">
      <el-form label-width="88px">
        <el-form-item label="名称">
          <el-input v-model="form.name" maxlength="64" />
        </el-form-item>
        <el-form-item label="权限">
          <div class="w-full max-h-80 overflow-y-auto border border-slate-100 rounded-lg p-3 space-y-3">
            <div v-for="g in grouped" :key="g.module">
              <p class="text-xs font-semibold text-slate-500 mb-1">{{ g.module }}</p>
              <el-checkbox-group v-model="form.permission_codes">
                <el-checkbox v-for="p in g.items" :key="p.code" :label="p.code">{{ p.name }}</el-checkbox>
              </el-checkbox-group>
            </div>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { rbacApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { PermissionItem, RoleItem } from '@/types'

const auth = useAuthStore()
const roles = ref<RoleItem[]>([])
const perms = ref<PermissionItem[]>([])
const loading = ref(false)
const show = ref(false)
const saving = ref(false)
const editing = ref<RoleItem | null>(null)
const form = reactive({ name: '', permission_codes: [] as string[] })

const grouped = computed(() => {
  const map = new Map<string, PermissionItem[]>()
  for (const p of perms.value) {
    const arr = map.get(p.module) || []
    arr.push(p)
    map.set(p.module, arr)
  }
  return [...map.entries()].map(([module, items]) => ({ module, items }))
})

async function load() {
  loading.value = true
  try {
    roles.value = await rbacApi.listRoles()
    perms.value = await rbacApi.listPermissions()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.name = ''
  form.permission_codes = []
  show.value = true
}

function openEdit(row: RoleItem) {
  editing.value = row
  form.name = row.name
  form.permission_codes = [...(row.permission_codes || [])]
  show.value = true
}

async function save() {
  if (!form.name.trim()) { ElMessage.warning('请填写名称'); return }
  saving.value = true
  try {
    if (editing.value) {
      await rbacApi.updateRole(editing.value.id, {
        name: form.name.trim(),
        permission_codes: form.permission_codes,
      })
    } else {
      await rbacApi.createRole({ name: form.name.trim(), permission_codes: form.permission_codes })
    }
    ElMessage.success('已保存')
    show.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(row: RoleItem) {
  await ElMessageBox.confirm(`确定删除角色「${row.name}」？`, '提示', { type: 'warning' })
  await rbacApi.deleteRole(row.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>
