import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { educationApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import type { SchoolLevel, Grade, Subject, TeacherSubject, WorkAssignment } from '@/types'

export const useEducationStore = defineStore('education', () => {
  const schoolLevels = ref<SchoolLevel[]>([])
  const grades = ref<Grade[]>([])
  const subjects = ref<Subject[]>([])
  const mySubjects = ref<TeacherSubject[]>([])

  const selectedSchoolLevelId = ref<number | null>(null)
  const selectedGradeId = ref<number | null>(null)
  const selectedSubjectId = ref<number | null>(null)

  const selectedSchoolLevel = computed(() =>
    schoolLevels.value.find(s => s.id === selectedSchoolLevelId.value)
  )
  const selectedGrade = computed(() =>
    grades.value.find(g => g.id === selectedGradeId.value)
  )
  const selectedSubject = computed(() =>
    subjects.value.find(s => s.id === selectedSubjectId.value)
  )

  const assignments = computed((): WorkAssignment[] => {
    return useAuthStore().teacher?.assignments || []
  })
  const boundGradeIds = computed(() => new Set(assignments.value.map(a => a.grade_id)))
  const boundSubjectIds = computed(() => new Set(assignments.value.map(a => a.subject_id)))
  const restrictToBindings = computed(() => {
    const auth = useAuthStore()
    if (auth.teacher?.is_super || auth.can('resource.view_all')) return false
    return boundGradeIds.value.size > 0
  })
  function boundSubjectIdsForGrade(gradeId: number | null) {
    if (!restrictToBindings.value || !gradeId) return null
    const ids = new Set(
      assignments.value.filter(a => a.grade_id === gradeId).map(a => a.subject_id),
    )
    return ids.size ? ids : boundSubjectIds.value
  }

  const sortedGrades = computed(() =>
    [...grades.value].sort(
      (a, b) => a.school_level_id - b.school_level_id || a.sort_order - b.sort_order
    )
  )

  const filteredGrades = computed(() =>
    sortedGrades.value.filter((g) => {
      if (selectedSchoolLevelId.value && g.school_level_id !== selectedSchoolLevelId.value) return false
      if (restrictToBindings.value && !boundGradeIds.value.has(g.id)) return false
      return true
    })
  )
  const filteredSubjects = computed(() =>
    [...subjects.value]
      .filter((s) => {
        if (selectedSchoolLevelId.value && s.school_level_id !== selectedSchoolLevelId.value) return false
        const bound = boundSubjectIdsForGrade(selectedGradeId.value)
        if (bound && !bound.has(s.id)) return false
        if (!bound && restrictToBindings.value && !boundSubjectIds.value.has(s.id)) return false
        return true
      })
      .sort((a, b) => a.sort_order - b.sort_order)
  )
  const visibleSchoolLevels = computed(() => {
    if (!restrictToBindings.value) return schoolLevels.value
    const ids = new Set(filteredGrades.value.map(g => g.school_level_id).concat(
      sortedGrades.value.filter(g => boundGradeIds.value.has(g.id)).map(g => g.school_level_id),
    ))
    return schoolLevels.value.filter(l => ids.has(l.id))
  })

  function gradeName(id?: number | null) {
    return grades.value.find(g => g.id === id)?.name || ''
  }
  function subjectName(id?: number | null) {
    return subjects.value.find(s => s.id === id)?.name || ''
  }

  function subjectsOfGrade(gradeId: number | null) {
    const g = grades.value.find(x => x.id === gradeId)
    if (!g) return []
    const bound = boundSubjectIdsForGrade(gradeId)
    return subjects.value
      .filter(s => {
        if (s.school_level_id !== g.school_level_id) return false
        if (bound && !bound.has(s.id)) return false
        return true
      })
      .sort((a, b) => a.sort_order - b.sort_order)
  }

  function defaultSubjectId(gradeId: number | null): number | null {
    if (!gradeId) return null
    const hit = assignments.value.find(a => a.grade_id === gradeId)
    const valid = subjectsOfGrade(gradeId)
    if (hit && valid.some(s => s.id === hit.subject_id)) return hit.subject_id
    return valid[0]?.id ?? null
  }

  function lsPrefix() {
    const id = useAuthStore().teacher?.id
    return id ? `sel_${id}_` : 'sel_'
  }
  function readStored(name: string): number | null {
    const raw = localStorage.getItem(lsPrefix() + name)
    const n = Number(raw)
    return raw && Number.isFinite(n) && n > 0 ? n : null
  }
  function persist() {
    const p = lsPrefix()
    const write = (name: string, v: number | null) => {
      if (v) localStorage.setItem(p + name, String(v))
      else localStorage.removeItem(p + name)
    }
    write('school_level', selectedSchoolLevelId.value)
    write('grade', selectedGradeId.value)
    write('subject', selectedSubjectId.value)
  }

  function applyAssignment(a: WorkAssignment) {
    const g = grades.value.find(x => x.id === a.grade_id)
    selectedGradeId.value = a.grade_id
    selectedSubjectId.value = a.subject_id
    selectedSchoolLevelId.value = g?.school_level_id ?? null
    persist()
  }

  function isSelectionValid() {
    const g = grades.value.find(x => x.id === selectedGradeId.value)
    if (!g) return false
    if (selectedSchoolLevelId.value !== g.school_level_id) return false
    if (!subjects.value.some(s => s.id === selectedSubjectId.value)) return false
    if (restrictToBindings.value) {
      if (!boundGradeIds.value.has(g.id)) return false
      const bound = boundSubjectIdsForGrade(g.id)
      if (bound && selectedSubjectId.value && !bound.has(selectedSubjectId.value)) return false
    }
    return true
  }

  function applyContext(forceBinding = false) {
    const first = assignments.value.find(a =>
      grades.value.some(g => g.id === a.grade_id) && subjects.value.some(s => s.id === a.subject_id),
    )
    if (first && (forceBinding || !isSelectionValid())) {
      applyAssignment(first)
      return
    }
    if (isSelectionValid()) {
      persist()
      return
    }
    selectedSchoolLevelId.value = null
    selectedGradeId.value = null
    selectedSubjectId.value = null
    persist()
  }

  function selectSchoolLevel(id: number | null) {
    selectedSchoolLevelId.value = id || null
    if (!selectedSchoolLevelId.value) {
      selectedGradeId.value = null
      selectedSubjectId.value = null
      persist()
      return
    }
    const hit = assignments.value.find((a) => {
      const g = grades.value.find(x => x.id === a.grade_id)
      return g?.school_level_id === selectedSchoolLevelId.value
    })
    if (hit) {
      applyAssignment(hit)
      return
    }
    const g = filteredGrades.value[0]
    selectedGradeId.value = g?.id ?? null
    selectedSubjectId.value = defaultSubjectId(selectedGradeId.value)
    persist()
  }

  function selectGrade(id: number | null) {
    selectedGradeId.value = id || null
    const g = grades.value.find(x => x.id === selectedGradeId.value)
    if (g) selectedSchoolLevelId.value = g.school_level_id
    selectedSubjectId.value = defaultSubjectId(selectedGradeId.value)
    persist()
  }

  function selectSubject(id: number | null) {
    selectedSubjectId.value = id || null
    persist()
  }

  async function init(opts?: { forceBinding?: boolean }) {
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
    if (!opts?.forceBinding) {
      selectedSchoolLevelId.value = readStored('school_level')
      selectedGradeId.value = readStored('grade')
      selectedSubjectId.value = readStored('subject')
    }
    applyContext(Boolean(opts?.forceBinding))
  }

  return {
    schoolLevels, grades, subjects, mySubjects, visibleSchoolLevels,
    selectedSchoolLevelId, selectedGradeId, selectedSubjectId,
    selectedSchoolLevel, selectedGrade, selectedSubject,
    sortedGrades, filteredGrades, filteredSubjects, subjectsOfGrade,
    defaultSubjectId, gradeName, subjectName,
    selectSchoolLevel, selectGrade, selectSubject, init,
  }
})
