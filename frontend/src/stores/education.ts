import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { educationApi } from '@/api/modules'
import type { SchoolLevel, Grade, Subject, TeacherSubject } from '@/types'

export const useEducationStore = defineStore('education', () => {
  const schoolLevels = ref<SchoolLevel[]>([])
  const grades = ref<Grade[]>([])
  const subjects = ref<Subject[]>([])
  const mySubjects = ref<TeacherSubject[]>([])

  // 当前选中的上下文
  const selectedSchoolLevelId = ref<number | null>(
    Number(localStorage.getItem('sel_school_level')) || null
  )
  const selectedGradeId = ref<number | null>(
    Number(localStorage.getItem('sel_grade')) || null
  )
  const selectedSubjectId = ref<number | null>(
    Number(localStorage.getItem('sel_subject')) || null
  )

  const selectedSchoolLevel = computed(() =>
    schoolLevels.value.find(s => s.id === selectedSchoolLevelId.value)
  )
  const selectedGrade = computed(() =>
    grades.value.find(g => g.id === selectedGradeId.value)
  )
  const selectedSubject = computed(() =>
    subjects.value.find(s => s.id === selectedSubjectId.value)
  )

  // 全部年级按「学段 -> 学段内序号」排序（低年级到高年级）
  const sortedGrades = computed(() =>
    [...grades.value].sort(
      (a, b) => a.school_level_id - b.school_level_id || a.sort_order - b.sort_order
    )
  )

  // 根据选中学段过滤年级和科目（同样保证有序）
  const filteredGrades = computed(() =>
    sortedGrades.value.filter(
      g => !selectedSchoolLevelId.value || g.school_level_id === selectedSchoolLevelId.value
    )
  )
  const filteredSubjects = computed(() =>
    [...subjects.value]
      .filter(s => !selectedSchoolLevelId.value || s.school_level_id === selectedSchoolLevelId.value)
      .sort((a, b) => a.sort_order - b.sort_order)
  )

  // 按 id 取名称
  function gradeName(id?: number | null) {
    return grades.value.find(g => g.id === id)?.name || ''
  }
  function subjectName(id?: number | null) {
    return subjects.value.find(s => s.id === id)?.name || ''
  }

  // 按年级 id 联动取该年级所属学段的科目
  function subjectsOfGrade(gradeId: number | null) {
    const g = grades.value.find(x => x.id === gradeId)
    if (!g) return []
    return subjects.value
      .filter(s => s.school_level_id === g.school_level_id)
      .sort((a, b) => a.sort_order - b.sort_order)
  }

  function selectSchoolLevel(id: number) {
    selectedSchoolLevelId.value = id
    selectedGradeId.value = null
    selectedSubjectId.value = null
    localStorage.setItem('sel_school_level', String(id))
    localStorage.removeItem('sel_grade')
    localStorage.removeItem('sel_subject')
  }

  function selectGrade(id: number) {
    selectedGradeId.value = id
    localStorage.setItem('sel_grade', String(id))
  }

  function selectSubject(id: number) {
    selectedSubjectId.value = id
    localStorage.setItem('sel_subject', String(id))
  }

  async function init() {
    const [lvRes, grRes, subRes, myRes] = await Promise.all([
      educationApi.getSchoolLevels() as Promise<any>,
      educationApi.getGrades() as Promise<any>,
      educationApi.getSubjects() as Promise<any>,
      educationApi.getMySubjects() as Promise<any>,
    ])
    schoolLevels.value = lvRes
    grades.value = grRes
    subjects.value = subRes
    mySubjects.value = myRes
  }

  return {
    schoolLevels, grades, subjects, mySubjects,
    selectedSchoolLevelId, selectedGradeId, selectedSubjectId,
    selectedSchoolLevel, selectedGrade, selectedSubject,
    sortedGrades, filteredGrades, filteredSubjects, subjectsOfGrade,
    gradeName, subjectName,
    selectSchoolLevel, selectGrade, selectSubject, init,
  }
})
