export interface Teacher {
  id: number
  username: string
  email: string
  real_name: string
  avatar?: string
  is_active: boolean
}

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

export interface Courseware {
  id: number; title: string; courseware_type: string; gen_status: ParseStatus
  is_interactive: boolean; textbook_id?: number; grade_id?: number; subject_id?: number
  task_id?: string; created_at: string
  content?: Record<string, unknown>; custom_prompt?: string
  chapter_range?: Record<string, number>; page_range?: Record<string, number>
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

export interface GradeReport {
  id: number; grade_id?: number | null; subject_id: number; exam_name: string
  report_type: 'stats' | 'ai'; custom_prompt?: string | null
  content?: Record<string, any> | null; gen_status: ParseStatus; created_at: string
}

export interface LLMConfig {
  id: number; provider: string; model_name: string; display_name: string
  base_url?: string; temperature: number; max_tokens: number
  is_default: boolean; is_active: boolean
}

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
  token: string; title: string; is_open: boolean
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
