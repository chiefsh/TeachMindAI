export interface RoleBrief {
  id: number
  code: string
  name: string
  is_system: boolean
}

export interface WorkAssignment {
  grade_id: number
  subject_id: number
  class_id?: number | null
  grade_name?: string | null
  subject_name?: string | null
  class_name?: string | null
}

export interface Teacher {
  id: number
  username: string
  email: string
  real_name: string
  avatar?: string
  is_active: boolean
  is_super?: boolean
  roles?: RoleBrief[]
  permissions?: string[]
  assignments?: WorkAssignment[]
}

export interface Paginated<T> { total: number; page: number; page_size: number; items: T[] }

export interface SchoolLevel { id: number; name: string; sort_order: number }
export interface Grade { id: number; school_level_id: number; name: string; sort_order: number }
export interface Subject { id: number; school_level_id: number; name: string; sort_order: number }

export interface TeacherSubject {
  id: number
  grade_id: number
  subject_id: number
  grade: Grade
  subject: Subject
}

export type ParseStatus = 'pending' | 'processing' | 'done' | 'failed'
export type QuestionType = 'single_choice' | 'multi_choice' | 'fill_blank' | 'short_answer' | 'essay' | 'true_false' | 'calculation'
export type DifficultyLevel = 'easy' | 'medium' | 'hard' | 'very_hard'

export interface AnalysisStep { title?: string; detail?: string; formula?: string }

export interface AnalysisContent {
  思路?: string
  steps?: AnalysisStep[]
  知识点?: string[]
  易错点?: string
  答案?: string
}

export interface Textbook {
  id: number; title: string; file_name: string; file_type: string
  file_size: number; parse_status: ParseStatus; total_pages?: number
  subject_id: number; grade_id: number; created_at: string
  creator_name?: string | null
}

export interface Chapter {
  id: number; title: string; level: number; sort_order: number
  page_start?: number; page_end?: number; children: Chapter[]
}

export interface QuestionImages {
  stem?: string[]
  options?: Record<string, string>
}

export interface Question {
  id: number; question_type: QuestionType; difficulty: DifficultyLevel
  content: string; options?: Record<string, string>; answer?: string
  explanation?: string; subject_id: number; grade_id: number
  tags?: string[]; created_at: string
  images?: QuestionImages | null
  use_count?: number
  wrong_count?: number
  analysis_content?: AnalysisContent | null
  analysis_html?: string | null
  has_diagram?: boolean
}

export interface QuestionImport {
  id: number
  file_name: string
  file_type: string
  parse_status: ParseStatus
  parse_error?: string | null
  question_count: number
  grade_id: number
  subject_id: number
  created_at: string
  updated_at: string
}

export type RenderStyle = 'ppt' | 'html'

export interface Courseware {
  id: number; title: string; courseware_type: string; gen_status: ParseStatus
  render_style?: RenderStyle; theme?: string
  is_interactive: boolean
  want_virtual_lab?: boolean
  virtual_lab_key?: string | null
  animation_keys?: string[] | null
  textbook_id?: number; grade_id?: number; subject_id?: number
  task_id?: string; created_at: string
  content?: Record<string, unknown>; custom_prompt?: string
  chapter_range?: { chapter_ids?: number[] } | Record<string, number>
  page_range?: { start?: number; end?: number }
  creator_name?: string | null
  is_owner?: boolean
  can_edit?: boolean
  can_manage_collab?: boolean
}

export interface LabExperiment {
  key: string
  title: string
  group: string
}

export interface InteractiveAsset {
  id: number
  key: string
  title: string
  subject: string
  group: string
  kind: string
  origin: 'system' | 'teacher' | string
  teacher_id: number | null
  keywords: string[]
  knowledge_tags: string[]
  skill: string
  problem_type: string
  spec: Record<string, unknown>
  has_html: boolean
  created_at: string
}

export interface CoursewareVersion {
  id: number
  courseware_id: number
  teacher_id: number
  title: string
  render_style: RenderStyle | string
  theme: string
  created_at: string
  creator_name?: string | null
  content?: Record<string, unknown>
}

export interface HomeworkQuestion {
  id: number; sort_order: number; content: string
  options?: Record<string, string> | null; answer?: string | null; score?: number | null
  source?: 'ai' | 'bank' | null
  question_id?: number | null
  question_type?: QuestionType | string | null
}

export type HomeworkSourceType = 'courseware' | 'textbook' | 'chapters'
export type QuestionSourceMode = 'ai' | 'bank' | 'mixed'

export interface HomeworkPaper {
  id: number; title: string; paper_type: string; difficulty: DifficultyLevel
  gen_status: ParseStatus; courseware_id?: number; created_at: string
  content?: string
  question_config?: Record<string, any>
  questions?: HomeworkQuestion[]
  source_type?: HomeworkSourceType
  question_source?: QuestionSourceMode
  textbook_id?: number | null
  chapter_ids?: number[] | null
  courseware_ids?: number[] | null
  grade_id?: number | null
  subject_id?: number | null
  creator_name?: string | null
  is_owner?: boolean
  can_edit?: boolean
  can_manage_collab?: boolean
}

export interface Student {
  id: number; student_no: string; name: string; grade_id: number
  class_id?: number | null; class_name?: string
}

export interface SchoolClass {
  id: number; grade_id: number; name: string; student_count: number; created_at: string
}

export interface ExamResult {
  id: number; student_id: number; subject_id: number; exam_name: string
  score: number; full_score: number; entry_method: string; created_at: string
  student_name?: string; student_no?: string; grade_id?: number
}

export interface ExamSummary {
  subject_id: number
  exam_name: string
  grade_id?: number | null
  count: number
  max_score: number
  min_score: number
  avg_score: number
  full_score: number
  high_count: number
  low_count: number
  high_line: number
  low_line: number
  latest_at?: string | null
}

export interface GradeReport {
  id: number; grade_id?: number | null; subject_id: number; exam_name: string
  report_type: 'stats' | 'ai'; custom_prompt?: string | null
  content?: Record<string, any> | null; gen_status: ParseStatus; created_at: string
}

export interface AnalysisQuestion {
  id: number; seq: number; content: string
  options?: Record<string, string> | null; answer?: string | null
  question_type: QuestionType; difficulty: DifficultyLevel
  selected: boolean; analysis_status: ParseStatus
  analysis_content?: AnalysisContent | null; analysis_html?: string | null
  analysis_source?: 'bank' | 'ai' | null
}

export interface AnalysisSet {
  id: number; name: string; grade_id: number; subject_id: number
  source_type: string; parse_status: ParseStatus; parse_error?: string | null
  task_id?: string | null; question_count: number; created_at: string
  questions?: AnalysisQuestion[]
  creator_name?: string | null
  is_owner?: boolean
  can_edit?: boolean
  can_manage_collab?: boolean
}

export interface LLMConfig {
  id: number; provider: string; model_name: string; display_name: string
  base_url?: string; temperature: number; max_tokens: number
  is_default: boolean; is_active: boolean
}

export interface EmbeddingConfig {
  enabled: boolean
  model: string
  base_url?: string | null
  dim: number
  use_llm_gateway: boolean
  has_api_key: boolean
  source: 'teacher' | 'env' | 'none'
}

// ── 知识图谱 ──
export interface KgNeighbor {
  type: string; direction: 'in' | 'out'
  other: { id: string; name: string; subject_name?: string }
  weight: number; cross_subject: boolean; status: string
}
export interface KgNode {
  id: string; name: string
  subject_id?: number | null; subject_name?: string
  school_level_id?: number | null; grade_id?: number | null
  description?: string; difficulty?: number; tags?: string[]; source?: string
  courseware_ids?: number[]; question_ids?: number[]
  neighbors?: KgNeighbor[]
  prerequisite_path?: { id: string; name: string; subject_name?: string }[]
}
export interface KgEdge {
  source: string; target: string; type: string
  weight: number; cross_subject: boolean; status: string
}
export interface KgGraph { nodes: KgNode[]; edges: KgEdge[] }

export interface GradeStats {
  exam_name: string; subject_id: number; avg_score: number
  max_score: number; min_score: number; pass_rate: number
  excellent_rate: number; score_distribution: Record<string, number>
}

export interface SubjectPrompt {
  subject_name: string; prompt: string
  interactive_guidance?: string | null; is_custom: boolean
}

export interface CoursewareSession {
  id: number; courseware_id: number; token: string; title: string
  is_open: boolean; record_count: number; student_count: number
}

export interface PublicSession {
  token: string; title: string; is_open: boolean; theme?: string | null
  content?: { meta?: Record<string, any>; slides?: any[] } | null
}

export interface SessionBoardQuestion {
  slide_index: number; question: string; component?: string | null
  attempts: number; correct: number; correct_rate: number
}

export interface SessionBoardStudent {
  name: string; attempts: number; correct: number; correct_rate: number
}

export interface SessionBoardRecord {
  id: number; student_name: string; slide_index: number
  component?: string | null; question?: string | null; answer?: string | null
  is_correct?: boolean | null; duration_ms?: number | null; created_at?: string | null
}

export interface SessionBoard {
  session: CoursewareSession
  summary: { total_records: number; student_count: number; question_count: number }
  questions: SessionBoardQuestion[]
  students: SessionBoardStudent[]
  records: SessionBoardRecord[]
}

export type ShareResourceType = 'courseware' | 'courseware_version' | 'question_analysis' | 'animation'

export interface ShareLink {
  id: number
  token: string
  resource_type: ShareResourceType | string
  resource_id: number
  title: string
  has_password: boolean
  expires_at: string
  revoked: boolean
  created_at: string
}

export interface ShareMeta {
  status: 'ok' | 'need_password' | 'expired' | 'revoked' | 'not_found'
  title: string
  resource_type?: ShareResourceType | string | null
  has_password: boolean
  expires_at?: string | null
}

export interface SharePayload {
  resource_type: ShareResourceType | string
  title: string
  expires_at: string
  payload: Record<string, any>
}

export type GradeVerdict = 'correct' | 'partial' | 'wrong' | 'blank'

export interface GradingAssignment {
  id: number
  paper_id: number
  paper_title: string
  paper_type: string
  title: string
  grade_id: number
  subject_id: number
  class_id?: number | null
  class_name?: string | null
  assigned_at: string
  status: string
  full_score?: number | null
  student_count: number
  submitted_count: number
  graded_count: number
  collect_token?: string | null
  created_at: string
  creator_name?: string | null
  is_owner?: boolean
  can_edit?: boolean
  can_manage_collab?: boolean
  questions?: HomeworkQuestion[]
  question_stats?: GradingQuestionStat[]
  students?: GradingStudentRow[]
}

export interface CollectStudent {
  id: number
  name: string
  student_no: string
  page_count: number
}

export interface CollectMeta {
  title: string
  class_name?: string | null
  paper_type: string
  assigned_at?: string | null
  students: CollectStudent[]
}

export interface GradingQuestionStat {
  paper_question_id: number
  sort_order: number
  content: string
  question_id?: number | null
  error_count: number
  blank_count: number
  graded_count: number
  error_rate: number
}

export interface GradingStudentRow {
  student_id: number
  name: string
  student_no: string
  class_name?: string | null
  submission_id?: number | null
  status: string
  page_count: number
  graded_count: number
  question_count: number
  total_score?: number | null
  full_score?: number | null
}

export interface GradingPage {
  id: number
  page_index: number
  url: string
  file_name?: string | null
}

export interface GradingAnswer {
  id: number
  paper_question_id: number
  question_id?: number | null
  student_answer?: string | null
  verdict?: GradeVerdict | string | null
  is_correct?: boolean | null
  score?: number | null
  max_score?: number | null
  comment?: string | null
  grade_method?: string
  page_index?: number | null
}

export interface GradingSubmission {
  id: number
  assignment_id: number
  student_id: number
  student_name: string
  student_no: string
  status: string
  total_score?: number | null
  full_score?: number | null
  paper_type: string
  assignment_title: string
  pages: GradingPage[]
  answers: GradingAnswer[]
  questions: HomeworkQuestion[]
  roster: GradingStudentRow[]
  can_edit?: boolean
}

export interface WrongQuestionItem {
  student_id?: number | null
  student_name?: string | null
  student_no?: string | null
  assignment_id?: number | null
  assignment_title?: string | null
  paper_question_id?: number | null
  question_id?: number | null
  sort_order?: number | null
  content: string
  question_type?: string | null
  error_count: number
  blank_count?: number
  last_at?: string | null
  use_count?: number | null
}

export interface PermissionItem {
  code: string
  module: string
  name: string
  sort_order: number
}

export interface RoleItem {
  id: number
  code: string
  name: string
  is_system: boolean
  is_super: boolean
  permission_codes: string[]
}

export interface UserAssignment {
  id: number
  grade_id: number
  subject_id: number
  class_id: number | null
  grade_name?: string | null
  subject_name?: string | null
  class_name?: string | null
}

export interface OrgUser {
  id: number
  username: string
  email: string
  real_name: string
  is_active: boolean
  is_super: boolean
  roles: RoleBrief[]
  assignments: UserAssignment[]
}

export interface ClassOption {
  id: number
  grade_id: number
  name: string
}
