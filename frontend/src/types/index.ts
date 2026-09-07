export interface Teacher {
  id: number
  username: string
  email: string
  real_name: string
  avatar?: string
  is_active: boolean
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

export interface Textbook {
  id: number; title: string; file_name: string; file_type: string
  file_size: number; parse_status: ParseStatus; total_pages?: number
  subject_id: number; grade_id: number; created_at: string
}

export interface Chapter {
  id: number; title: string; level: number; sort_order: number
  page_start?: number; page_end?: number; children: Chapter[]
}

export interface Question {
  id: number; question_type: QuestionType; difficulty: DifficultyLevel
  content: string; options?: Record<string, string>; answer?: string
  explanation?: string; subject_id: number; grade_id: number
  tags?: string[]; created_at: string
}

export type RenderStyle = 'ppt' | 'html'

export interface Courseware {
  id: number; title: string; courseware_type: string; gen_status: ParseStatus
  render_style?: RenderStyle; theme?: string
  is_interactive: boolean; textbook_id?: number; grade_id?: number; subject_id?: number
  task_id?: string; created_at: string
  content?: Record<string, unknown>; custom_prompt?: string
  chapter_range?: { chapter_ids?: number[] } | Record<string, number>
  page_range?: { start?: number; end?: number }
}

export interface HomeworkQuestion {
  id: number; sort_order: number; content: string
  options?: Record<string, string> | null; answer?: string | null; score?: number | null
}

export interface HomeworkPaper {
  id: number; title: string; paper_type: string; difficulty: DifficultyLevel
  gen_status: ParseStatus; courseware_id?: number; created_at: string
  content?: string; question_config?: Record<string, number>
  questions?: HomeworkQuestion[]
}

export interface Student {
  id: number; student_no: string; name: string; grade_id: number; class_name?: string
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

export interface AnalysisStep { title?: string; detail?: string; formula?: string }

export interface AnalysisContent {
  思路?: string
  steps?: AnalysisStep[]
  知识点?: string[]
  易错点?: string
  答案?: string
}

export interface AnalysisQuestion {
  id: number; seq: number; content: string
  options?: Record<string, string> | null; answer?: string | null
  question_type: QuestionType; difficulty: DifficultyLevel
  selected: boolean; analysis_status: ParseStatus
  analysis_content?: AnalysisContent | null; analysis_html?: string | null
}

export interface AnalysisSet {
  id: number; name: string; grade_id: number; subject_id: number
  source_type: string; parse_status: ParseStatus; parse_error?: string | null
  task_id?: string | null; question_count: number; created_at: string
  questions?: AnalysisQuestion[]
}

export interface LLMConfig {
  id: number; provider: string; model_name: string; display_name: string
  base_url?: string; temperature: number; max_tokens: number
  is_default: boolean; is_active: boolean
}

// ── 知识图谱 ──
export interface KgNeighbor {
  type: string; direction: 'in' | 'out'
  other: { id: string; name: string; subject_name?: string }
  weight: number; cross_subject: boolean; status: string
}
export interface KgNode {
  id: string; name: string; teacher_id?: number
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
