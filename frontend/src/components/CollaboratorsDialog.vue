<template>
  <el-dialog
    :model-value="modelValue"
    title="批量设置协作者"
    width="560px"
    @close="emit('update:modelValue', false)"
  >
    <p class="text-xs text-slate-500 mb-3">{{ hint }}</p>
    <el-form label-width="72px">
      <el-form-item label="资源">
        <el-select
          v-model="pickedResourceIds"
          multiple
          filterable
          collapse-tags
          collapse-tags-tooltip
          placeholder="选择要授权的资源（可多选）"
          style="width:100%"
        >
          <el-option v-for="o in options" :key="o.id" :label="o.title" :value="o.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="人员">
        <el-select
          v-model="pickedIds"
          multiple
          filterable
          collapse-tags
          collapse-tags-tooltip
          placeholder="选择人员（可多选）"
          style="width:100%"
          @change="onPicked"
        >
          <el-option
            v-for="c in colleagues"
            :key="c.id"
            :label="`${c.real_name}（${c.username}）`"
            :value="c.id"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <el-table :data="rows" size="small" empty-text="尚未选择人员">
      <el-table-column label="姓名" min-width="140">
        <template #default="{ row }">{{ row.real_name }}（{{ row.username }}）</template>
      </el-table-column>
      <el-table-column label="权限" width="140">
        <template #default="{ row }">
          <el-select v-model="row.can_edit" size="small">
            <el-option :value="false" label="仅查看" />
            <el-option :value="true" label="可编辑" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column width="70" align="center">
        <template #default="{ row }">
          <el-button size="small" link type="danger" @click="remove(row.teacher_id)">移除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-checkbox
      v-if="pickedResourceIds.length > 1"
      v-model="replaceExisting"
      class="mt-3"
    >覆盖已有协作者（否则只追加）</el-checkbox>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { rbacApi } from '@/api/modules'
import { ElMessage } from 'element-plus'

export interface CollabOption {
  id: number
  title: string
}

const props = defineProps<{
  modelValue: boolean
  resourceType: string
  options: CollabOption[]
  selectedIds?: number[]
}>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const colleagues = ref<{ id: number; username: string; real_name: string }[]>([])
const rows = ref<{ teacher_id: number; real_name: string; username: string; can_edit: boolean }[]>([])
const pickedIds = ref<number[]>([])
const pickedResourceIds = ref<number[]>([])
const saving = ref(false)
const replaceExisting = ref(false)

const hint = computed(() => {
  if (pickedResourceIds.value.length <= 1) {
    return '默认仅自己可见。先选资源，再选人员并设置查看或编辑权限。'
  }
  return '将授权到所选资源。默认追加到已有协作者；勾选覆盖则会替换为下列人员。'
})

function onPicked(next: number[]) {
  const keep = new Set(next)
  rows.value = rows.value.filter(r => keep.has(r.teacher_id))
  for (const id of next) {
    if (rows.value.some(r => r.teacher_id === id)) continue
    const c = colleagues.value.find(x => x.id === id)
    if (c) {
      rows.value.push({
        teacher_id: c.id, real_name: c.real_name, username: c.username, can_edit: false,
      })
    }
  }
}

function remove(teacherId: number) {
  pickedIds.value = pickedIds.value.filter(id => id !== teacherId)
  rows.value = rows.value.filter(r => r.teacher_id !== teacherId)
}

async function load() {
  colleagues.value = (await rbacApi.colleagues()) || []
  rows.value = []
  pickedIds.value = []
  replaceExisting.value = false
  const allowed = new Set((props.options || []).map(o => o.id))
  const preset = (props.selectedIds || []).filter(id => allowed.has(id))
  pickedResourceIds.value = preset.length ? [...preset] : []
  if (pickedResourceIds.value.length === 1) {
    const list = await rbacApi.listCollaborators(props.resourceType, pickedResourceIds.value[0])
    rows.value = (list || []).map(x => ({ ...x, can_edit: Boolean(x.can_edit) }))
    pickedIds.value = rows.value.map(r => r.teacher_id)
  }
}

async function save() {
  if (!pickedResourceIds.value.length) {
    ElMessage.warning('请选择要授权的资源')
    return
  }
  const replace = pickedResourceIds.value.length === 1 || replaceExisting.value
  if (!replace && !rows.value.length) {
    ElMessage.warning('请选择要授权的人员')
    return
  }
  saving.value = true
  try {
    const res = await rbacApi.saveCollaboratorsBatch(props.resourceType, {
      resource_ids: pickedResourceIds.value,
      items: rows.value.map(r => ({ teacher_id: r.teacher_id, can_edit: r.can_edit })),
      replace,
    })
    const skip = res.skipped || 0
    ElMessage.success(skip ? `已更新 ${res.updated} 项，跳过 ${skip} 项` : `已更新 ${res.updated} 项`)
    emit('update:modelValue', false)
  } finally {
    saving.value = false
  }
}

watch(() => props.modelValue, v => { if (v) load() })
</script>
