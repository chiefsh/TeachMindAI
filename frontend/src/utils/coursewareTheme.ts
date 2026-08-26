// 课件视觉主题调色板。
// 与后端 backend/app/services/courseware_theme.py 一一对应——key 与色值必须保持一致，
// 否则在线预览（reveal 演示 / 网页课件）与导出的 PPTX/DOCX/PDF 会长得不一样。

export interface CoursewareTheme {
  key: string
  label: string
  primary: string
  accent: string
  text: string
  muted: string
  bg: string
}

export const THEMES: CoursewareTheme[] = [
  { key: 'indigo',  label: '靛蓝学院', primary: '#4F46E5', accent: '#0EA5E9', text: '#1E293B', muted: '#64748B', bg: '#F8FAFC' },
  { key: 'emerald', label: '清新绿意', primary: '#059669', accent: '#10B981', text: '#1E293B', muted: '#64748B', bg: '#F5FBF8' },
  { key: 'amber',   label: '活力暖橙', primary: '#D97706', accent: '#F59E0B', text: '#1E293B', muted: '#6B7280', bg: '#FFFBF3' },
  { key: 'rose',    label: '温暖珊瑚', primary: '#E11D48', accent: '#FB7185', text: '#1E293B', muted: '#64748B', bg: '#FFF5F7' },
  { key: 'sky',     label: '晴空蓝',   primary: '#0284C7', accent: '#38BDF8', text: '#1E293B', muted: '#64748B', bg: '#F3FAFF' },
  { key: 'slate',   label: '极简墨黑', primary: '#334155', accent: '#64748B', text: '#0F172A', muted: '#6B7280', bg: '#F6F7F9' },
]

export const DEFAULT_THEME = 'indigo'

export function getTheme(key?: string | null): CoursewareTheme {
  return THEMES.find((t) => t.key === key) || THEMES[0]
}
