import request from './index'
import type {
  Textbook, Chapter, Question, QuestionImport, Courseware, HomeworkPaper,
  Student, SchoolClass, ExamResult, ExamSummary, GradeReport, LLMConfig, EmbeddingConfig, TeacherSubject,
  SchoolLevel, Grade, Subject, SubjectPrompt,
  CoursewareSession, SessionBoard, PublicSession, CoursewareVersion,
  AnalysisSet, Paginated, KgNode, KgEdge, KgGraph, LabExperiment, InteractiveAsset,
  ShareLink, ShareMeta, SharePayload, ShareResourceType,
  GradingAssignment, GradingSubmission, WrongQuestionItem,
  CollectMeta,
  PermissionItem, RoleItem, OrgUser, ClassOption,
} from '@/types'

// ─── 工作台 ────────────────────────────────────────────────────────
export const dashboardApi = {
  getStats: () => request.get<{
    textbook_count: number
    question_count: number
    courseware_count: number
    student_count: number
    analysis_count: number
  }>('/dashboard/stats'),
}

// ─── 认证 ──────────────────────────────────────────────────────────
export const authApi = {
  login: (data: { username: string; password: string }) => request.post('/auth/login', data),
  register: (data: object) => request.post('/auth/register', data),
  logout: () => request.post('/auth/logout'),
  me: () => request.get('/auth/me'),
  updateMe: (data: { real_name?: string; email?: string }) => request.patch('/auth/me', data),
  changePassword: (data: { old_password: string; new_password: string }) =>
    request.post('/auth/change-password', data),
  getConfig: () => request.get<{ enable_regist: boolean }>('/auth/config'),
}

// ─── 学段/年级/科目 ────────────────────────────────────────────────
export const educationApi = {
  getSchoolLevels: () => request.get<SchoolLevel[]>('/education/school-levels'),
  getGrades: (school_level_id?: number) => request.get<Grade[]>('/education/grades', { params: { school_level_id } }),
  getSubjects: (school_level_id?: number) => request.get<Subject[]>('/education/subjects', { params: { school_level_id } }),
  getMySubjects: () => request.get<TeacherSubject[]>('/education/my-subjects'),
  addMySubject: (data: { grade_id: number; subject_id: number }) => request.post('/education/my-subjects', data),
  removeMySubject: (id: number) => request.delete(`/education/my-subjects/${id}`),
}

// ─── 课本 ──────────────────────────────────────────────────────────
export const textbookApi = {
  list: (params?: { subject_id?: number; grade_id?: number; page?: number; page_size?: number }) =>
    request.get<Paginated<Textbook>>('/textbooks', { params }),
  upload: (formData: FormData) => request.post<Textbook>('/textbooks', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 10 * 60 * 1000, // 大 PDF 走 Nginx 反代，给足 10 分钟
  }),
  getPreviewUrl: (id: number) => request.get<{ url: string; file_type: string }>(`/textbooks/${id}/preview-url`),
  getChapters: (id: number) => request.get<Chapter[]>(`/textbooks/${id}/chapters`),
  reparse: (id: number) => request.post<Textbook>(`/textbooks/${id}/reparse`),
  relatedCounts: (id: number) =>
    request.get<{ courseware: number; homework: number; questions: number }>(`/textbooks/${id}/related-counts`),
  listImages: (id: number) => request.get<{ id: number; page_number: number; url: string }[]>(`/textbooks/${id}/images`),
  resolveImages: (ids: number[]) => request.post<Record<string, string>>('/textbooks/images/resolve', { ids }),
  // base64 data URI，供离线 HTML 内联（presigned URL 会过期）；超大图不返回
  resolveImagesInline: (ids: number[]) =>
    request.post<Record<string, string>>('/textbooks/images/resolve-inline', { ids }),
  delete: (id: number) => request.delete(`/textbooks/${id}`),
}

// ─── 题库 ──────────────────────────────────────────────────────────
export const questionApi = {
  list: (params?: object) => request.get<{ total: number; items: Question[] }>('/questions', { params }),
  get: (id: number) => request.get<Question>(`/questions/${id}`),
  create: (data: object) => request.post<Question>('/questions', data),
  update: (id: number, data: object) => request.patch<Question>(`/questions/${id}`, data),
  manual: (data: { text: string; subject_id: number; grade_id: number; use_ai: boolean }) =>
    request.post<{ count: number; created?: number; skipped?: number; items: Question[] }>('/questions/manual', data),
  importFile: (formData: FormData) => request.post('/questions/import-file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  listImports: (params?: { page?: number; page_size?: number }) =>
    request.get<Paginated<QuestionImport>>('/questions/imports', { params }),
  batchDelete: (ids: number[]) => request.post<{ count: number }>('/questions/batch-delete', { ids }),
  delete: (id: number) => request.delete(`/questions/${id}`),
}

// ─── 课件 ──────────────────────────────────────────────────────────
export const coursewareApi = {
  list: (params?: { grade_id?: number; subject_id?: number; page?: number; page_size?: number }) =>
    request.get<Paginated<Courseware>>('/coursewares', { params }),
  create: (data: object) => request.post<Courseware>('/coursewares', data),
  listLabExperiments: () =>
    request.get<{ items: LabExperiment[] }>('/coursewares/lab-experiments'),
  get: (id: number) => request.get<Courseware>(`/coursewares/${id}`),
  getStatus: (id: number) => request.get(`/coursewares/${id}/status`),
  regenerate: (id: number, data: object) => request.post<Courseware>(`/coursewares/${id}/regenerate`, data),
  suggestCopyTitle: (id: number) => request.get<{ title: string }>(`/coursewares/${id}/copy-title`),
  copy: (id: number, title: string) => request.post<Courseware>(`/coursewares/${id}/copy`, { title }),
  rename: (id: number, title: string) => request.patch<Courseware>(`/coursewares/${id}`, { title }),
  getSlide: (id: number, index: number) =>
    request.get<{ index: number; edit_status: string; task_id?: string | null; slide: any }>(
      `/coursewares/${id}/slides/${index}`,
    ),
  patchSlide: (id: number, index: number, data: Record<string, unknown>) =>
    request.patch<{ index: number; slide: any }>(`/coursewares/${id}/slides/${index}`, data),
  insertSlide: (id: number, data: { index?: number; type?: string }) =>
    request.post<{ index: number; slide: any }>(`/coursewares/${id}/slides`, data),
  deleteSlide: (id: number, index: number) =>
    request.delete(`/coursewares/${id}/slides/${index}`),
  reorderSlides: (id: number, order: number[]) =>
    request.put<{ count: number }>(`/coursewares/${id}/slides/reorder`, { order }),
  optimizeSlide: (id: number, index: number, data: { instruction?: string; mode?: string }) =>
    request.post<{ index: number; task_id: string; edit_status: string }>(
      `/coursewares/${id}/slides/${index}/optimize`,
      data,
    ),
  exportFile: (
    id: number,
    format: 'pptx' | 'docx' | 'pdf',
    shots?: Record<number, string>,
  ) => {
    if (shots && Object.keys(shots).length) {
      return request.post<Blob>(
        `/coursewares/${id}/export`,
        { format, shots },
        { responseType: 'blob', timeout: 180000 },
      )
    }
    return request.get<Blob>(`/coursewares/${id}/export`, {
      params: { format },
      responseType: 'blob',
      timeout: 120000,
    })
  },
  delete: (id: number) => request.delete(`/coursewares/${id}`),
  listVersions: (id: number) =>
    request.get<CoursewareVersion[]>(`/coursewares/${id}/versions`),
  getVersion: (id: number, vid: number) =>
    request.get<CoursewareVersion>(`/coursewares/${id}/versions/${vid}`),
  deleteVersion: (id: number, vid: number) =>
    request.delete(`/coursewares/${id}/versions/${vid}`),
  applyVersion: (id: number, vid: number) =>
    request.post<Courseware>(`/coursewares/${id}/versions/${vid}/apply`),
}

// ─── 互动动画库 ────────────────────────────────────────────────────
export const animationApi = {
  list: (params?: { subject?: string }) =>
    request.get<{ items: InteractiveAsset[] }>('/animations', { params }),
  get: (id: number) => request.get<InteractiveAsset>(`/animations/${id}`),
  getHtml: (id: number) =>
    request.get<string>(`/animations/${id}/html`, { responseType: 'text', timeout: 120000 }),
  create: (data: {
    template_key: string; title: string; keywords?: string[]; knowledge_tags?: string[]
    scene?: Record<string, unknown>
  }) =>
    request.post<InteractiveAsset>('/animations', data),
  update: (id: number, data: {
    title?: string; keywords?: string[]; knowledge_tags?: string[]; scene?: Record<string, unknown>
  }) =>
    request.patch<InteractiveAsset>(`/animations/${id}`, data),
  rerender: (id: number) => request.post<InteractiveAsset>(`/animations/${id}/render`),
  delete: (id: number) => request.delete(`/animations/${id}`),
}

// ─── 课堂互动会话 ──────────────────────────────────────────────────
export const interactionApi = {
  listSessions: (cwId: number) =>
    request.get<CoursewareSession[]>(`/coursewares/${cwId}/sessions`),
  createSession: (cwId: number, title?: string) =>
    request.post<CoursewareSession>(`/coursewares/${cwId}/sessions`, { title }),
  toggleSession: (sessionId: number, isOpen: boolean) =>
    request.patch<CoursewareSession>(`/sessions/${sessionId}`, null, { params: { is_open: isOpen } }),
  deleteSession: (sessionId: number) => request.delete(`/sessions/${sessionId}`),
  board: (sessionId: number) => request.get<SessionBoard>(`/sessions/${sessionId}/board`),
}

// ─── 学生公开作答（免登录） ────────────────────────────────────────
export const publicApi = {
  getSession: (token: string) => request.get<PublicSession>(`/public/sessions/${token}`),
  submitRecord: (token: string, data: {
    student_name: string; slide_index: number; component?: string | null
    question?: string | null; answer?: string | null
    is_correct?: boolean | null; duration_ms?: number | null
  }) => request.post(`/public/sessions/${token}/records`, data),
  shareMeta: (token: string) => request.get<ShareMeta>(`/public/shares/${token}`),
  shareAccess: (token: string, password?: string) =>
    request.post<SharePayload>(`/public/shares/${token}/access`, { password: password || null }),
  collectMeta: (token: string) => request.get<CollectMeta>(`/public/grading/${token}`),
  collectPages: (token: string, studentId: number, formData: FormData) => {
    formData.append('student_id', String(studentId))
    return request.post<{ student_id: number; student_name: string; page_count: number }>(
      `/public/grading/${token}/pages`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 10 * 60 * 1000 },
    )
  },
}

export const shareApi = {
  create: (data: {
    resource_type: ShareResourceType
    resource_id: number
    expire_days?: number
    password?: string | null
  }) => request.post<ShareLink>('/shares', data),
  list: (resource_type: ShareResourceType, resource_id: number) =>
    request.get<ShareLink[]>('/shares', { params: { resource_type, resource_id } }),
  revoke: (id: number) => request.delete(`/shares/${id}`),
}

// ─── 作业/考试 ─────────────────────────────────────────────────────
export const homeworkApi = {
  list: (params?: { grade_id?: number; subject_id?: number }) => request.get<HomeworkPaper[]>('/homework', { params }),
  create: (data: object) => request.post<HomeworkPaper>('/homework', data),
  regenerate: (id: number, data: object) => request.post<HomeworkPaper>(`/homework/${id}/regenerate`, data),
  get: (id: number) => request.get<HomeworkPaper>(`/homework/${id}`),
  review: (id: number, verified = true) =>
    request.post<HomeworkPaper>(`/homework/${id}/review`, { verified }),
  exportFile: (id: number, format: 'docx' | 'pdf', includeAnswers = false) =>
    request.get<Blob>(`/homework/${id}/export`, {
      params: { format, include_answers: includeAnswers },
      responseType: 'blob',
    }),
  delete: (id: number) => request.delete(`/homework/${id}`),
}

export const classApi = {
  list: (params?: { grade_id?: number }) => request.get<SchoolClass[]>('/classes', { params }),
  create: (data: { grade_id: number; name: string }) => request.post<SchoolClass>('/classes', data),
  update: (id: number, data: { name: string }) => request.patch<SchoolClass>(`/classes/${id}`, data),
  delete: (id: number) => request.delete(`/classes/${id}`),
  students: (id: number) => request.get<Student[]>(`/classes/${id}/students`),
  addStudent: (id: number, data: { student_no: string; name: string; grade_id: number }) =>
    request.post<Student>(`/classes/${id}/students`, data),
  batchStudents: (id: number, rows: { student_no: string; name: string }[]) =>
    request.post<{ created: number; skipped: number }>(`/classes/${id}/students/batch`, { rows }),
}

// ─── 批改作业/试卷 ─────────────────────────────────────────────────
export const gradingApi = {
  listAssignments: (params?: { grade_id?: number; subject_id?: number; class_name?: string }) =>
    request.get<GradingAssignment[]>('/grading/assignments', { params }),
  createAssignment: (data: {
    paper_id: number; grade_id: number; subject_id: number
    class_id?: number | null; class_name?: string | null; title?: string | null; assigned_at?: string | null
  }) => request.post<GradingAssignment>('/grading/assignments', data),
  getAssignment: (id: number) => request.get<GradingAssignment>(`/grading/assignments/${id}`),
  deleteAssignment: (id: number) => request.delete(`/grading/assignments/${id}`),
  getSubmission: (assignmentId: number, studentId: number) =>
    request.get<GradingSubmission>(`/grading/assignments/${assignmentId}/students/${studentId}`),
  uploadPages: (submissionId: number, formData: FormData) =>
    request.post<GradingSubmission>(`/grading/submissions/${submissionId}/pages`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 10 * 60 * 1000,
    }),
  deletePage: (submissionId: number, pageId: number) =>
    request.delete<GradingSubmission>(`/grading/submissions/${submissionId}/pages/${pageId}`),
  gradeAnswers: (submissionId: number, items: object[]) =>
    request.put<GradingSubmission>(`/grading/submissions/${submissionId}/answers`, { items }),
  collectToken: (id: number) => request.post<{ token: string }>(`/grading/assignments/${id}/collect-token`),
  wrongQuestions: (params?: {
    scope?: 'student' | 'assignment' | 'bank'
    assignment_id?: number; student_id?: number
    grade_id?: number; subject_id?: number
  }) => request.get<WrongQuestionItem[]>('/grading/wrong-questions', { params }),
}

// ─── 学生成绩 ──────────────────────────────────────────────────────
export const studentApi = {
  list: (params?: object) => request.get<Student[]>('/students', { params }),
  create: (data: object) => request.post<Student>('/students', data),
  update: (id: number, data: object) => request.patch<Student>(`/students/${id}`, data),
  delete: (id: number) => request.delete(`/students/${id}`),
  batchImport: (formData: FormData) => request.post('/students/batch-import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  imageImport: (formData: FormData) => request.post('/students/image-import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  addResults: (data: object[]) => request.post<ExamResult[]>('/students/results', data),
  manualGrades: (data: {
    grade_id: number; subject_id: number; exam_name: string; full_score: number
    rows: { name: string; student_no: string; score: number | null }[]
  }) => request.post<{ count: number }>('/students/manual-grades', data),
  getResults: (params?: object) => request.get<ExamResult[]>('/students/results', { params }),
  getResultsSummary: (params?: {
    grade_id?: number; subject_id?: number; high_line?: number; low_line?: number
  }) => request.get<ExamSummary[]>('/students/results/summary', { params }),
  getExamNames: (params?: { grade_id?: number; subject_id?: number }) =>
    request.get<string[]>('/students/exam-names', { params }),
  getGradeLineConfig: () =>
    request.get<{ high_line: number; low_line: number }>('/students/grade-line-config'),
  saveGradeLineConfig: (data: { high_line: number; low_line: number }) =>
    request.put<{ high_line: number; low_line: number }>('/students/grade-line-config', data),
  // 成绩分析报告（统计/AI）历史
  createAnalysis: (data: {
    grade_id?: number | null; subject_id: number; exam_name: string
    report_type: 'stats' | 'ai'; custom_prompt?: string | null
  }) => request.post<GradeReport>('/students/analysis', data),
  listAnalysis: (params: { report_type: 'stats' | 'ai'; grade_id?: number; subject_id?: number }) =>
    request.get<GradeReport[]>('/students/analysis', { params }),
  getAnalysis: (id: number) => request.get<GradeReport>(`/students/analysis/${id}`),
  deleteAnalysis: (id: number) => request.delete(`/students/analysis/${id}`),
  regenerateAnalysis: (id: number, custom_prompt?: string | null) =>
    request.post<GradeReport>(`/students/analysis/${id}/regenerate`, { custom_prompt }),
}

// ─── 试题分析 ──────────────────────────────────────────────────────
export const analysisApi = {
  list: (params?: { grade_id?: number; subject_id?: number; page?: number; page_size?: number }) =>
    request.get<Paginated<AnalysisSet>>('/question-analysis', { params }),
  importManual: (data: { text: string; grade_id: number; subject_id: number; name?: string }) =>
    request.post<AnalysisSet>('/question-analysis/import-manual', data),
  importFile: (formData: FormData) =>
    request.post<AnalysisSet>('/question-analysis/import-file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  get: (id: number) => request.get<AnalysisSet>(`/question-analysis/${id}`),
  getStatus: (id: number) => request.get<{
    parse_status: string; question_count: number
    analysis: { pending: number; processing: number; done: number; failed: number }
  }>(`/question-analysis/${id}/status`),
  reparse: (id: number) => request.post<AnalysisSet>(`/question-analysis/${id}/reparse`),
  analyze: (id: number, question_ids: number[], force = false) =>
    request.post<{ task_id: string | null; count: number; reused?: number }>(
      `/question-analysis/${id}/analyze`,
      { question_ids, force },
    ),
  saveToBank: (id: number, question_ids: number[]) =>
    request.post<{ count: number; created?: number; skipped?: number }>(`/question-analysis/${id}/save-to-bank`, { question_ids }),
  exportFile: (id: number, format: 'docx' | 'pdf') =>
    request.get<Blob>(`/question-analysis/${id}/export`, { params: { format }, responseType: 'blob' }),
  delete: (id: number) => request.delete(`/question-analysis/${id}`),
}

// ─── 知识图谱 ──────────────────────────────────────────────────────
export const knowledgeApi = {
  getGraph: (params?: { subject_id?: number; grade_id?: number; limit?: number }) =>
    request.get<KgGraph>('/knowledge/graph', { params }),
  getStats: () => request.get<{ point_count: number; relation_count: number }>('/knowledge/stats'),
  searchPoints: (params?: { keyword?: string; subject_id?: number; limit?: number }) =>
    request.get<KgNode[]>('/knowledge/points', { params }),
  getPoint: (id: string) => request.get<KgNode>(`/knowledge/points/${id}`),
  createPoint: (body: {
    name: string; subject_id?: number | null; grade_id?: number | null
    description?: string; difficulty?: number; tags?: string[]
  }) => request.post<{ id: string; name: string; merged: boolean }>('/knowledge/points', body),
  deletePoint: (id: string) => request.delete(`/knowledge/points/${id}`),
  createRelation: (body: {
    from_id: string; to_id: string; rel_type: string
    weight?: number; cross_subject?: boolean; evidence?: string
  }) => request.post('/knowledge/relations', body),
  deleteRelation: (body: { from_id: string; to_id: string; rel_type: string }) =>
    request.post('/knowledge/relations/delete', body),
  updateRelationStatus: (body: { from_id: string; to_id: string; rel_type: string; status: string }) =>
    request.put('/knowledge/relations/status', body),
  extractChapter: (chapterId: number) => request.post<{ task_id: string }>(`/knowledge/extract/chapter/${chapterId}`),
  extractTextbook: (textbookId: number) => request.post<{ task_id: string }>(`/knowledge/extract/textbook/${textbookId}`),
  suggestCrossSubject: () => request.post<{ task_id: string }>('/knowledge/suggest-cross-subject'),
}

// ─── 设置 ──────────────────────────────────────────────────────────
export const settingsApi = {
  getProviders: () => request.get('/settings/providers'),
  fetchModels: (data: { provider: string; api_key?: string; base_url?: string }) =>
    request.post<{ models: string[]; source: string; error?: string }>('/settings/fetch-models', data),
  listConfigs: () => request.get<LLMConfig[]>('/settings/llm-configs'),
  createConfig: (data: object) => request.post<LLMConfig>('/settings/llm-configs', data),
  updateConfig: (id: number, data: object) => request.patch<LLMConfig>(`/settings/llm-configs/${id}`, data),
  deleteConfig: (id: number) => request.delete(`/settings/llm-configs/${id}`),
  testConfig: (id: number) => request.post(`/settings/llm-configs/${id}/test`),
  getEmbedding: () => request.get<EmbeddingConfig>('/settings/embedding'),
  saveEmbedding: (data: {
    enabled: boolean; model: string; base_url?: string | null
    api_key?: string | null; dim: number; use_llm_gateway: boolean
  }) => request.put<EmbeddingConfig>('/settings/embedding', data),
  testEmbedding: () => request.post<{ success: boolean; dim?: number; model?: string; error?: string }>(
    '/settings/embedding/test',
  ),
  // 科目课件提示词
  listSubjectPrompts: () => request.get<SubjectPrompt[]>('/settings/subject-prompts'),
  updateSubjectPrompt: (subjectName: string, data: { prompt: string; interactive_guidance?: string | null }) =>
    request.put<SubjectPrompt>(`/settings/subject-prompts/${encodeURIComponent(subjectName)}`, data),
  resetSubjectPrompt: (subjectName: string) =>
    request.delete<SubjectPrompt>(`/settings/subject-prompts/${encodeURIComponent(subjectName)}`),
}

// ─── 用户 / 角色 ──────────────────────────────────────────────────
export const rbacApi = {
  listPermissions: () => request.get<PermissionItem[]>('/permissions'),
  listRoles: () => request.get<RoleItem[]>('/roles'),
  createRole: (data: { name: string; permission_codes: string[] }) =>
    request.post<RoleItem>('/roles', data),
  updateRole: (id: number, data: { name?: string; permission_codes?: string[] }) =>
    request.patch<RoleItem>(`/roles/${id}`, data),
  deleteRole: (id: number) => request.delete(`/roles/${id}`),
  listUsers: (params?: { keyword?: string; page?: number; page_size?: number }) =>
    request.get<Paginated<OrgUser>>('/users', { params }),
  getUser: (id: number) => request.get<OrgUser>(`/users/${id}`),
  createUser: (data: object) => request.post<OrgUser>('/users', data),
  updateUser: (id: number, data: object) => request.patch<OrgUser>(`/users/${id}`, data),
  deleteUser: (id: number) => request.delete(`/users/${id}`),
  classOptions: () => request.get<ClassOption[]>('/users/class-options'),
  colleagues: () => request.get<{ id: number; username: string; real_name: string }[]>('/colleagues'),
  listCollaborators: (type: string, id: number) =>
    request.get<{ teacher_id: number; real_name: string; username: string; can_edit: boolean }[]>(
      `/resources/${type}/${id}/collaborators`,
    ),
  saveCollaborators: (type: string, id: number, items: { teacher_id: number; can_edit: boolean }[]) =>
    request.put(`/resources/${type}/${id}/collaborators`, items),
  saveCollaboratorsBatch: (
    type: string,
    data: { resource_ids: number[]; items: { teacher_id: number; can_edit: boolean }[]; replace?: boolean },
  ) => request.put<{ updated: number; skipped: number }>(`/resources/${type}/collaborators/batch`, data),
}
