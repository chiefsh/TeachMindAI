// 课件 Theme System。
// 与后端 backend/app/services/courseware_theme.py 一一对应——key、色值、封面/装饰/阴影
// 必须保持一致，否则在线预览（reveal 演示 / 网页课件）与导出的 PPTX/DOCX/PDF 会长得不一样。

export type CoverStyle = 'diagonal' | 'split' | 'ribbon' | 'panel' | 'lab' | 'minimal'
export type DecoStyle = 'circles' | 'leaves' | 'grid' | 'waves' | 'dots' | 'lines'

export interface CoursewareTheme {
  key: string
  label: string
  primary: string
  accent: string
  text: string
  muted: string
  bg: string
  card: string
  surface: string
  coverFrom: string
  coverTo: string
  onCover: string
  coverStyle: CoverStyle
  decoStyle: DecoStyle
  shadow: string
  shadowSoft: string
}

export const THEMES: CoursewareTheme[] = [
  {
    key: 'vibrant', label: '活力课堂',
    primary: '#E85D04', accent: '#F48C06', text: '#3B1D08', muted: '#9A6240',
    bg: '#FFF1E4', card: '#FFF8F0', surface: '#FFE0C2',
    coverFrom: '#E85D04', coverTo: '#DC2F02', onCover: '#FFFFFF',
    coverStyle: 'diagonal', decoStyle: 'circles',
    shadow: '0 10px 28px rgba(232,93,4,0.14)', shadowSoft: '0 3px 10px rgba(232,93,4,0.08)',
  },
  {
    key: 'nature', label: '清新自然',
    primary: '#2D6A4F', accent: '#52B788', text: '#143528', muted: '#52796F',
    bg: '#EAF6EF', card: '#F6FBF8', surface: '#D4EDDA',
    coverFrom: '#1B4332', coverTo: '#40916C', onCover: '#FFFFFF',
    coverStyle: 'split', decoStyle: 'leaves',
    shadow: '0 10px 28px rgba(45,106,79,0.12)', shadowSoft: '0 3px 10px rgba(45,106,79,0.08)',
  },
  {
    key: 'explore', label: '蓝色探索',
    primary: '#1D4ED8', accent: '#0EA5E9', text: '#102A4C', muted: '#5B7A9D',
    bg: '#E7F0FA', card: '#F4F8FD', surface: '#D0E3F6',
    coverFrom: '#1E3A8A', coverTo: '#0284C7', onCover: '#FFFFFF',
    coverStyle: 'ribbon', decoStyle: 'grid',
    shadow: '0 10px 28px rgba(29,78,216,0.12)', shadowSoft: '0 3px 10px rgba(29,78,216,0.08)',
  },
  {
    key: 'humanities', label: '人文阅读',
    primary: '#9A3412', accent: '#C2410C', text: '#3F2412', muted: '#9A6B52',
    bg: '#F3E8D9', card: '#FAF4EB', surface: '#E6D3B8',
    coverFrom: '#7C2D12', coverTo: '#B45309', onCover: '#FFFFFF',
    coverStyle: 'panel', decoStyle: 'waves',
    shadow: '0 8px 22px rgba(124,45,18,0.12)', shadowSoft: '0 3px 8px rgba(124,45,18,0.08)',
  },
  {
    key: 'lab', label: '明亮实验室',
    primary: '#0F766E', accent: '#14B8A6', text: '#134E4A', muted: '#5F8A86',
    bg: '#E4F4F2', card: '#F2FAF9', surface: '#C8EDE8',
    coverFrom: '#115E59', coverTo: '#0D9488', onCover: '#FFFFFF',
    coverStyle: 'lab', decoStyle: 'dots',
    shadow: '0 10px 28px rgba(15,118,110,0.12)', shadowSoft: '0 3px 10px rgba(15,118,110,0.08)',
  },
  {
    key: 'exam', label: '简洁考试',
    primary: '#334155', accent: '#64748B', text: '#0F172A', muted: '#64748B',
    bg: '#E8EDF3', card: '#F4F6F9', surface: '#D9E0E8',
    coverFrom: '#1E293B', coverTo: '#475569', onCover: '#FFFFFF',
    coverStyle: 'minimal', decoStyle: 'lines',
    shadow: '0 6px 18px rgba(15,23,42,0.10)', shadowSoft: '0 2px 8px rgba(15,23,42,0.06)',
  },
]

/** 旧版主题 key → 现行主题，保证已生成课件仍能上色。 */
const ALIASES: Record<string, string> = {
  indigo: 'explore',
  sky: 'explore',
  emerald: 'nature',
  amber: 'vibrant',
  rose: 'humanities',
  slate: 'exam',
}

export const DEFAULT_THEME = 'explore'

export function resolveThemeKey(key?: string | null): string {
  const k = ALIASES[key || ''] || key || DEFAULT_THEME
  return THEMES.some((t) => t.key === k) ? k : DEFAULT_THEME
}

export function getTheme(key?: string | null): CoursewareTheme {
  const resolved = resolveThemeKey(key)
  return THEMES.find((t) => t.key === resolved) || THEMES[0]
}

export function themeCssVars(t: CoursewareTheme): string {
  return [
    `--c-primary:${t.primary}`,
    `--c-accent:${t.accent}`,
    `--c-text:${t.text}`,
    `--c-muted:${t.muted}`,
    `--c-bg:${t.bg}`,
    `--c-card:${t.card}`,
    `--c-surface:${t.surface}`,
    `--c-cover-from:${t.coverFrom}`,
    `--c-cover-to:${t.coverTo}`,
    `--c-on-cover:${t.onCover}`,
    `--c-primary-soft:${t.primary}22`,
    `--shadow:${t.shadow}`,
    `--shadow-soft:${t.shadowSoft}`,
  ].join(';')
}

export function coverGradient(t: CoursewareTheme): string {
  return `linear-gradient(135deg, ${t.coverFrom}, ${t.coverTo})`
}
