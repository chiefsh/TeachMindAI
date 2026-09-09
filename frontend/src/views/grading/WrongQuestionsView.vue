<template>
  <div class="page">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4 sm:mb-6">
      <div>
        <h1 class="page-title">错题本</h1>
        <p class="page-subtitle">按学生、单次作业/考试、题库三层汇总错题次数</p>
      </div>
      <el-button @click="$router.push('/grading')">返回批改</el-button>
    </div>

    <el-tabs v-model="scope" class="card !pb-0" @tab-change="load">
      <el-tab-pane label="按学生" name="student" />
      <el-tab-pane label="单次作业/考试" name="assignment" />
      <el-tab-pane label="题库汇总" name="bank" />
    </el-tabs>

    <div class="card mt-4">
      <div class="flex flex-wrap gap-3 mb-4">
        <el-select
          v-if="scope !== 'bank'"
          v-model="assignmentId"
          clearable
          placeholder="筛选布置"
          style="width:240px"
          @change="load"
        >
          <el-option v-for="a in assignments" :key="a.id" :label="a.title" :value="a.id" />
        </el-select>
        <el-select
          v-if="scope === 'student'"
          v-model="studentId"
          clearable
          filterable
          placeholder="筛选学生"
          style="width:200px"
          @change="load"
        >
          <el-option
            v-for="s in students"
            :key="s.id"
            :label="`${s.name} ${s.student_no}`"
            :value="s.id"
          />
        </el-select>
      </div>

      <div class="table-scroll">
        <el-table :data="items" v-loading="loading">
          <el-table-column v-if="scope === 'student'" label="学生" width="140">
            <template #default="{ row }">
              <p class="text-sm">{{ row.student_name }}</p>
              <p class="text-xs text-slate-400">{{ row.student_no }}</p>
            </template>
          </el-table-column>
          <el-table-column v-if="scope === 'student'" label="来源" min-width="140">
            <template #default="{ row }">
              <span class="text-xs text-slate-600">{{ row.assignment_title }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="scope !== 'bank'" label="#" width="50" align="center">
            <template #default="{ row }">{{ row.sort_order ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="题目" min-width="240">
            <template #default="{ row }">
              <p class="text-sm line-clamp-2">{{ row.content }}</p>
            </template>
          </el-table-column>
          <el-table-column label="错次" width="80" align="center">
            <template #default="{ row }">
              <span class="text-sm font-semibold text-red-500">{{ row.error_count }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="scope !== 'bank'" label="未做" width="70" align="center">
            <template #default="{ row }">{{ row.blank_count || 0 }}</template>
          </el-table-column>
          <el-table-column v-if="scope === 'bank'" label="组卷使用" width="90" align="center">
            <template #default="{ row }">{{ row.use_count ?? 0 }}</template>
          </el-table-column>
        </el-table>
      </div>
      <p v-if="!loading && !items.length" class="text-center text-sm text-slate-400 py-8">暂无错题记录</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import { gradingApi, studentApi } from '@/api/modules'
import { useEducationStore } from '@/stores/education'
import type { GradingAssignment, Student, WrongQuestionItem } from '@/types'

const edu = useEducationStore()
const route = useRoute()
const scope = ref<'student' | 'assignment' | 'bank'>((route.query.scope as any) || 'student')
const assignmentId = ref<number | undefined>(route.query.assignment_id ? Number(route.query.assignment_id) : undefined)
const studentId = ref<number | undefined>(undefined)
const items = ref<WrongQuestionItem[]>([])
const assignments = ref<GradingAssignment[]>([])
const students = ref<Student[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    items.value = await gradingApi.wrongQuestions({
      scope: scope.value,
      assignment_id: assignmentId.value,
      student_id: studentId.value,
      grade_id: edu.selectedGradeId || undefined,
      subject_id: edu.selectedSubjectId || undefined,
    })
  } finally {
    loading.value = false
  }
}

async function loadFilters() {
  assignments.value = await gradingApi.listAssignments({
    grade_id: edu.selectedGradeId || undefined,
    subject_id: edu.selectedSubjectId || undefined,
  })
  students.value = await studentApi.list({
    grade_id: edu.selectedGradeId || undefined,
  }) as Student[]
}

watchDebounced(
  () => [edu.selectedGradeId, edu.selectedSubjectId],
  () => { loadFilters(); load() },
  { debounce: 250 },
)

onMounted(async () => {
  await loadFilters()
  await load()
})
</script>
