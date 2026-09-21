// 课件页面类型布局：Cover / 学习目标 / 新知 / 例题 / 互动 / 对比 / 过程 / 小结 / 练习 / 作业。
// revealDeck.ts 与 lessonPage.ts 共用这里的 CSS、装饰与 inner HTML，保证演示稿与网页课件同一套视觉语言。
import { renderMarkdown } from './markdown'
import { coverGradient, themeCssVars, type CoursewareTheme } from './coursewareTheme'
import { normalizeChemText } from './chemText'
import { isAppInteractiveHtml } from './coursewareFrame'

export type PageKind =
  | 'cover' | 'objectives' | 'knowledge' | 'example' | 'interactive'
  | 'comparison' | 'process' | 'summary' | 'exercise' | 'homework'

export const PAGE_LABELS: Record<string, string> = {
  cover: '封面', objectives: '学习目标', knowledge: '新知讲解', example: '例题精讲',
  interactive: '互动探究', comparison: '对比辨析', process: '过程路径',
  summary: '课堂小结', exercise: '随堂练习', homework: '课后作业',
  title: '封面', content: '新知讲解', intro: '情境导入', activity: '课堂活动',
  board: '板书设计', quiz: '随堂测验',
}

const PAGE_ALIASES: Record<string, PageKind> = {
  title: 'cover', content: 'knowledge', intro: 'process',
  activity: 'interactive', quiz: 'exercise', board: 'summary',
}

export const PAGE_KINDS: PageKind[] = [
  'cover', 'objectives', 'knowledge', 'example', 'interactive',
  'comparison', 'process', 'summary', 'exercise', 'homework',
]
const KINDS = PAGE_KINDS

export function normalizePageKind(type?: string): PageKind {
  const t = (type || 'knowledge').trim()
  const mapped = PAGE_ALIASES[t] || t
  return (KINDS as string[]).includes(mapped) ? (mapped as PageKind) : 'knowledge'
}

export function pageTypeLabel(type?: string): string {
  return PAGE_LABELS[type || ''] || PAGE_LABELS[normalizePageKind(type)] || '内容'
}

/** 给学生上课看的页：学习目标只写在 meta，不进投影/网页。 */
export function isStudentSlide(slide?: { type?: string } | null): boolean {
  return normalizePageKind(slide?.type) !== 'objectives'
}

export function esc(s: string): string {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function vis(s: string): string {
  return esc(normalizeChemText(s))
}

export function escAttr(s: string): string {
  return esc(s).replace(/"/g, '&quot;')
}

export function subjectKind(name?: string): string {
  const n = name || ''
  if (/数学|算术/.test(n)) return 'math'
  if (/语文|作文|阅读|文学/.test(n)) return 'chinese'
  if (/英语|英文/.test(n)) return 'english'
  if (/物理/.test(n)) return 'physics'
  if (/化学/.test(n)) return 'chem'
  if (/生物/.test(n)) return 'bio'
  if (/历史/.test(n)) return 'history'
  if (/地理/.test(n)) return 'geo'
  return 'generic'
}

function subjectSvg(kind: string, color: string): string {
  const c = color
  const icons: Record<string, string> = {
    math: `<circle cx="16" cy="16" r="11" fill="none" stroke="${c}" stroke-width="1.6"/>
      <path d="M16 5v22M5 16h22" stroke="${c}" stroke-width="1.2"/>
      <path d="M8 24l16-16" stroke="${c}" stroke-width="1.2"/>`,
    chinese: `<path d="M8 7h16v18H8z" fill="none" stroke="${c}" stroke-width="1.6"/>
      <path d="M11 12h10M11 16h10M11 20h7" stroke="${c}" stroke-width="1.3"/>`,
    english: `<text x="16" y="21" text-anchor="middle" font-size="14" font-weight="700" fill="${c}" font-family="serif">Aa</text>`,
    physics: `<circle cx="16" cy="16" r="3" fill="${c}"/>
      <ellipse cx="16" cy="16" rx="12" ry="5" fill="none" stroke="${c}" stroke-width="1.3" transform="rotate(30 16 16)"/>
      <ellipse cx="16" cy="16" rx="12" ry="5" fill="none" stroke="${c}" stroke-width="1.3" transform="rotate(-30 16 16)"/>`,
    chem: `<path d="M12 6h8v6l5 12H7l5-12z" fill="none" stroke="${c}" stroke-width="1.6"/>
      <circle cx="16" cy="20" r="2.2" fill="${c}"/>`,
    bio: `<path d="M16 28c0-12 10-12 10-20-8 0-10 8-10 8S14 8 6 8c0 8 10 8 10 20z" fill="none" stroke="${c}" stroke-width="1.5"/>
      <path d="M16 14v14" stroke="${c}" stroke-width="1.3"/>`,
    history: `<path d="M8 8h16v4H8zm2 4v12m12-12v12M8 24h16" fill="none" stroke="${c}" stroke-width="1.5"/>`,
    geo: `<circle cx="16" cy="16" r="11" fill="none" stroke="${c}" stroke-width="1.6"/>
      <ellipse cx="16" cy="16" rx="5" ry="11" fill="none" stroke="${c}" stroke-width="1.2"/>
      <path d="M5 16h22" stroke="${c}" stroke-width="1.2"/>`,
    generic: `<path d="M16 5l3 8h8l-6.5 5 2.5 8L16 21l-7 5 2.5-8L5 13h8z" fill="none" stroke="${c}" stroke-width="1.4"/>`,
  }
  return `<svg class="cw-subject" viewBox="0 0 32 32" width="32" height="32" aria-hidden="true">${icons[kind] || icons.generic}</svg>`
}

export function decoSvg(theme: CoursewareTheme): string {
  const p = theme.primary
  const a = theme.accent
  const style = theme.decoStyle
  let body = ''
  if (style === 'circles') {
    body = `<circle cx="1180" cy="70" r="200" fill="${p}" opacity=".10"/>
      <circle cx="80" cy="680" r="160" fill="${a}" opacity=".12"/>
      <circle cx="1080" cy="620" r="70" fill="${p}" opacity=".14"/>
      <circle cx="200" cy="80" r="36" fill="${a}" opacity=".16"/>`
  } else if (style === 'leaves') {
    body = `<ellipse cx="1220" cy="80" rx="180" ry="90" fill="${p}" opacity=".10" transform="rotate(24 1220 80)"/>
      <ellipse cx="60" cy="640" rx="160" ry="70" fill="${a}" opacity=".12" transform="rotate(-18 60 640)"/>
      <ellipse cx="1100" cy="560" rx="80" ry="36" fill="${p}" opacity=".12" transform="rotate(40 1100 560)"/>`
  } else if (style === 'grid') {
    body = `<defs><pattern id="cwg" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M40 0H0v40" fill="none" stroke="${p}" stroke-width="1" opacity=".18"/></pattern></defs>
      <rect width="1280" height="720" fill="url(#cwg)"/>
      <circle cx="1200" cy="80" r="90" fill="${a}" opacity=".10"/>`
  } else if (style === 'waves') {
    body = `<path d="M0 560 Q160 500 320 560 T640 560 T960 560 T1280 560 V720 H0z" fill="${p}" opacity=".10"/>
      <path d="M0 600 Q160 660 320 600 T640 600 T960 600 T1280 600 V720 H0z" fill="${a}" opacity=".10"/>`
  } else if (style === 'dots') {
    body = `<defs><pattern id="cwd" width="22" height="22" patternUnits="userSpaceOnUse">
        <circle cx="3" cy="3" r="1.6" fill="${p}" opacity=".28"/></pattern></defs>
      <rect width="1280" height="720" fill="url(#cwd)"/>
      <rect x="1040" y="0" width="240" height="720" fill="${p}" opacity=".06"/>`
  } else {
    body = `<defs><pattern id="cwl" width="28" height="28" patternUnits="userSpaceOnUse" patternTransform="rotate(32)">
        <line x1="0" y1="0" x2="0" y2="28" stroke="${p}" stroke-width="2" opacity=".10"/></pattern></defs>
      <rect width="1280" height="720" fill="url(#cwl)"/>
      <rect x="0" y="0" width="10" height="720" fill="${p}"/>`
  }
  return `<div class="cw-deco" aria-hidden="true"><svg viewBox="0 0 1280 720" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">${body}</svg></div>`
}

export function pageCss(theme: CoursewareTheme, mode: 'deck' | 'page'): string {
  const compact = mode === 'deck'
  return `
:root{${themeCssVars(theme)}}
.cw-page{position:relative;overflow:hidden;color:var(--c-text);background:var(--c-bg);box-sizing:border-box}
.cw-deco{position:absolute;inset:0;pointer-events:none;z-index:0}
.cw-deco svg{width:100%;height:100%;display:block}
.cw-inner{position:relative;z-index:1}
.cw-kicker{display:inline-flex;align-items:center;gap:.45em;font-weight:700;letter-spacing:.06em;
  color:var(--c-primary);background:var(--c-primary-soft);border-radius:999px;padding:.18em .75em}
.cw-label{display:inline-block;font-weight:700;color:#fff;background:var(--c-primary);
  padding:.15em .7em;border-radius:999px}
.cw-chip{display:inline-flex;align-items:center;gap:.35em;background:var(--c-surface);color:var(--c-text);
  border-radius:999px;padding:.2em .7em;font-weight:600}
.cw-block{background:var(--c-card);box-shadow:var(--shadow-soft);border-radius:16px;padding:14px 16px}
.cw-block-accent{background:linear-gradient(135deg,var(--c-primary),var(--c-accent));color:var(--c-on-cover);
  box-shadow:var(--shadow);border-radius:16px;padding:16px 18px}
.cw-subject{flex-shrink:0}

/* Cover */
.cw-cover{min-height:100%;display:flex}
.cw-cover .cw-inner{width:100%}
.cw-cover h1{margin:0;font-weight:800;letter-spacing:.01em;line-height:1.25}
.cw-cover .sub{opacity:.9;margin-top:.5em}
.cw-cover--diagonal{background:${coverGradient(theme)};color:var(--c-on-cover);text-align:center;align-items:center;justify-content:center}
.cw-cover--diagonal .cw-kicker,.cw-cover--split .cw-cover-panel .cw-kicker,.cw-ribbon .cw-kicker{background:rgba(255,255,255,.18);color:#fff}
.cw-cover--diagonal .cw-chip,.cw-cover--split .cw-cover-panel .cw-chip{background:rgba(255,255,255,.18);color:#fff}
.cw-cover--split{background:var(--c-bg);color:var(--c-text)}
.cw-cover--split .cw-inner{display:grid;grid-template-columns:42% 1fr;padding:0;min-height:100%}
.cw-cover-panel{background:${coverGradient(theme)};color:var(--c-on-cover);display:flex;flex-direction:column;justify-content:center;padding:8%}
.cw-cover-side{display:flex;flex-direction:column;justify-content:center;padding:8%;gap:12px}
.cw-cover--ribbon{background:var(--c-bg);color:var(--c-text);flex-direction:column;justify-content:center}
.cw-ribbon{background:${coverGradient(theme)};color:var(--c-on-cover);padding:6% 8%;box-shadow:var(--shadow)}
.cw-cover--panel{background:var(--c-bg);align-items:center;justify-content:center}
.cw-cover-card{background:var(--c-card);box-shadow:var(--shadow);border-radius:24px;padding:48px 56px;max-width:78%;
  border-top:6px solid var(--c-primary)}
.cw-cover--lab{background:var(--c-bg);color:var(--c-text);flex-direction:column;justify-content:flex-end;padding:6% 8% 8%}
.cw-cover--lab .cw-lab-bar{height:10px;width:180px;background:var(--c-accent);border-radius:8px;margin-bottom:18px}
.cw-cover--minimal{background:var(--c-bg);color:var(--c-text);flex-direction:column;justify-content:center;padding:8%}
.cw-cover--minimal h1{border-left:6px solid var(--c-primary);padding-left:18px}

/* Typed layouts */
.cw-goals{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:12px}
.cw-goal{background:var(--c-card);box-shadow:var(--shadow-soft);border-radius:14px;padding:14px 16px;display:flex;gap:12px;align-items:flex-start}
.cw-goal-n{flex-shrink:0;width:2em;height:2em;border-radius:10px;background:var(--c-primary);color:#fff;
  display:flex;align-items:center;justify-content:center;font-weight:800}
.cw-knowledge{display:grid;grid-template-columns:8px 1fr;gap:16px;margin-top:8px}
.cw-knowledge-bar{background:linear-gradient(180deg,var(--c-primary),var(--c-accent));border-radius:8px}
.cw-points{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:8px}
.cw-points li{background:var(--c-card);box-shadow:var(--shadow-soft);border-radius:12px;padding:10px 14px;display:flex;gap:8px}
.cw-points li::before{content:"▸";color:var(--c-primary);font-weight:700}
.cw-example{display:flex;flex-direction:column;gap:14px;margin-top:10px}
.cw-example-q{background:var(--c-surface);border-radius:16px;padding:16px;box-shadow:var(--shadow-soft)}
.cw-example-a{background:var(--c-card);border-radius:16px;padding:16px;box-shadow:var(--shadow);border-left:5px solid var(--c-accent)}
.cw-example h3{margin:0 0 8px;font-size:1em;color:var(--c-primary)}
.cw-reveal{background:var(--c-card);border-radius:16px;padding:12px 16px;box-shadow:var(--shadow-soft);border-left:5px solid var(--c-accent)}
.cw-reveal summary{cursor:pointer;font-weight:700;color:var(--c-primary)}
.cw-reveal[open] summary{margin-bottom:8px}
.cw-interact{margin-top:8px;background:var(--c-card);border-radius:16px;box-shadow:var(--shadow);overflow:hidden}
.cw-interact-bar{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;
  background:linear-gradient(90deg,var(--c-primary),var(--c-accent));color:var(--c-on-cover);font-weight:700}
.cw-fs-box{margin-top:8px;background:var(--c-card);border-radius:16px;box-shadow:var(--shadow);overflow:hidden;display:flex;flex-direction:column}
.cw-fs-bar{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 14px;
  background:linear-gradient(90deg,var(--c-primary),var(--c-accent));color:var(--c-on-cover);font-weight:700;font-size:14px;flex-shrink:0}
.cw-fs-stage{width:100%}
.cw-fs-btn{appearance:none;border:0;background:rgba(255,255,255,.2);color:inherit;border-radius:999px;
  padding:6px 14px;font-size:12px;font-weight:700;cursor:pointer;letter-spacing:.04em}
.cw-fs-btn:hover{background:rgba(255,255,255,.32)}
html.cw-fs-lock,html.cw-fs-lock body{overflow:hidden!important;height:100%!important}
#cw-present-layer{display:none;position:fixed;inset:0;z-index:99999;background:#000;flex-direction:column}
#cw-present-layer.is-on{display:flex}
#cw-present-layer .cw-present-bar{height:44px;flex-shrink:0;display:flex;align-items:center;gap:12px;
  padding:0 16px;background:rgba(0,0,0,.8);color:#fff;font-size:14px}
#cw-present-layer .cw-present-title{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#cw-present-layer .cw-present-hint{font-size:12px;color:rgba(255,255,255,.5)}
#cw-present-layer .cw-present-exit{appearance:none;border:0;border-radius:6px;padding:6px 12px;cursor:pointer;font-size:12px}
#cw-present-layer .cw-present-frame{flex:1;width:100%;min-height:0;border:0;background:#000}
.cw-compare{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:10px}
.cw-compare-col{background:var(--c-card);border-radius:16px;padding:16px;box-shadow:var(--shadow-soft)}
.cw-compare-col.a{border-top:5px solid var(--c-primary)}
.cw-compare-col.b{border-top:5px solid var(--c-accent)}
.cw-compare-col h3{margin:0 0 8px}
.cw-steps{display:flex;flex-direction:column;gap:0;margin-top:8px}
.cw-step{display:grid;grid-template-columns:36px 1fr;gap:12px}
.cw-step-rail{display:flex;flex-direction:column;align-items:center}
.cw-step-n{width:32px;height:32px;border-radius:50%;background:var(--c-primary);color:#fff;
  display:flex;align-items:center;justify-content:center;font-weight:800;flex-shrink:0}
.cw-step-line{width:3px;flex:1;min-height:16px;background:var(--c-primary);opacity:.25}
.cw-step-body{background:var(--c-card);box-shadow:var(--shadow-soft);border-radius:14px;padding:12px 14px;margin-bottom:10px}
.cw-summary-hero{margin-top:8px}
.cw-summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-top:12px}
.cw-summary-grid .cw-block{font-weight:600}
.cw-exercise{display:flex;flex-direction:column;gap:10px;margin-top:10px}
.cw-ex{display:flex;gap:12px;background:var(--c-card);box-shadow:var(--shadow-soft);border-radius:14px;padding:12px 14px}
.cw-ex-n{flex-shrink:0;width:1.8em;height:1.8em;border-radius:8px;border:2px solid var(--c-primary);color:var(--c-primary);
  display:flex;align-items:center;justify-content:center;font-weight:800}
.cw-hw{display:flex;flex-direction:column;gap:10px;margin-top:10px}
.cw-hw-item{display:flex;gap:12px;background:var(--c-card);box-shadow:var(--shadow-soft);border-radius:14px;padding:12px 14px;align-items:flex-start}
.cw-hw-box{width:1.15em;height:1.15em;border:2px solid var(--c-primary);border-radius:4px;margin-top:.2em;flex-shrink:0}
.cw-imgs{display:flex;gap:12px;flex-wrap:wrap;margin-top:.6em}
.cw-imgs img{max-height:${compact ? '32vh' : '320px'};border-radius:12px;background:var(--c-surface);object-fit:contain;box-shadow:var(--shadow-soft)}
.cw-iframe{width:100%;border:0;display:block;background:var(--c-card);height:${compact ? '52vh' : '520px'}}
.cw-iframe--app{height:${compact ? '78vh' : '760px'};min-height:620px}
.cw-notes{margin-top:12px}
.body h3,.body h4,.body h5{color:var(--c-primary);margin:.7em 0 .25em}
.body p{margin:.4em 0}
.body code{background:var(--c-surface);color:#be185d;padding:.05em .3em;border-radius:4px}
${compact ? `
.cw-kicker{font-size:.42em}
.cw-label{font-size:.42em;margin-bottom:.35em}
.cw-cover h1{font-size:2em}
.cw-cover .sub{font-size:.9em}
.cw-page h2{font-size:1.25em;margin:.2em 0 .15em}
.cw-inner{font-size:.78em;line-height:1.45}
` : `
.cw-kicker{font-size:12px}
.cw-label{font-size:12px}
.cw-cover h1{font-size:36px}
.cw-page h2{font-size:22px;margin:8px 0 4px}
`}
@media (max-width:900px){
  .cw-goals,.cw-example,.cw-compare,.cw-cover--split{grid-template-columns:1fr}
  .cw-cover-card{padding:28px 22px}
}
@media print{
  .cw-fs-btn{display:none}
}
`
}

function bulletsOf(slide: any): string[] {
  return (slide?.bullets || []).map((b: any) => String(b || '').trim()).filter(Boolean)
}

function stepsOf(slide: any): { title: string; detail: string }[] {
  if (Array.isArray(slide?.steps) && slide.steps.length) {
    return slide.steps.map((s: any) => ({
      title: String(s.title || s.name || '').trim(),
      detail: String(s.detail || s.content || '').trim(),
    })).filter((s: any) => s.title || s.detail)
  }
  return bulletsOf(slide).map((b) => ({ title: b, detail: '' }))
}

function columnsOf(slide: any): { title: string; items: string[] }[] {
  if (Array.isArray(slide?.columns) && slide.columns.length >= 2) {
    return slide.columns.slice(0, 2).map((c: any) => ({
      title: String(c.title || '').trim() || '对照',
      items: (c.items || c.bullets || []).map((x: any) => String(x || '').trim()).filter(Boolean),
    }))
  }
  const bs = bulletsOf(slide)
  const mid = Math.max(1, Math.ceil(bs.length / 2))
  return [
    { title: slide.left_title || '对照 A', items: bs.slice(0, mid) },
    { title: slide.right_title || '对照 B', items: bs.slice(mid) },
  ]
}

function kicker(label: string, index?: number): string {
  const chap = index ? `第 ${index} 页 · ` : ''
  return `<span class="cw-kicker">${vis(chap + label)}</span>`
}

function heading(slide: any): string {
  const h = slide.title ? `<h2>${vis(slide.title)}</h2>` : ''
  const s = slide.subtitle ? `<p class="sub" style="color:var(--c-muted);margin:.15em 0 .4em">${vis(slide.subtitle)}</p>` : ''
  return h + s
}

function pointsList(items: string[]): string {
  if (!items.length) return ''
  return `<ul class="cw-points">${items.map((b) => `<li><span>${vis(b)}</span></li>`).join('')}</ul>`
}

function mdBlock(html: string): string {
  return html ? `<div class="body">${html}</div>` : ''
}

export interface SlideMedia {
  imagesHtml: string
  iframeHtml: string
  notesHtml: string
  mdHtml: string
}

export interface SlideCtx {
  index: number
  subject?: string
  chapter?: string
}

function coverInner(slide: any, theme: CoursewareTheme, ctx: SlideCtx): string {
  const title = vis(slide.title || '教学课件')
  const sub = slide.subtitle ? `<p class="sub">${vis(slide.subtitle)}</p>` : ''
  const style = theme.coverStyle
  const iconColor = style === 'diagonal' ? theme.onCover : theme.primary
  const badge = ctx.subject
    ? `<div class="cw-chip">${subjectSvg(subjectKind(ctx.subject), iconColor)}${esc(ctx.subject)}</div>`
    : ''
  const chap = ctx.chapter ? `<span class="cw-kicker">${esc(ctx.chapter)}</span>` : ''
  if (style === 'split') {
    return `<div class="cw-cover-panel"><div>${chap}</div><h1>${title}</h1>${sub}</div>
      <div class="cw-cover-side">${badge}</div>`
  }
  if (style === 'ribbon') {
    return `${badge}<div class="cw-ribbon"><div>${chap}</div><h1>${title}</h1>${sub}</div>`
  }
  if (style === 'panel') {
    return `<div class="cw-cover-card">${chap}<h1 style="margin-top:.4em">${title}</h1>${sub}${badge}</div>`
  }
  if (style === 'lab') {
    return `<div class="cw-lab-bar"></div>${chap}<h1>${title}</h1>${sub}${badge}`
  }
  if (style === 'minimal') {
    return `${chap}<h1 style="margin-top:.6em">${title}</h1>${sub}${badge}`
  }
  return `${badge}<div style="margin-top:12px">${chap}</div><h1>${title}</h1>${sub}`
}

function innerByKind(kind: PageKind, slide: any, media: SlideMedia, ctx: SlideCtx, theme: CoursewareTheme): string {
  const label = pageTypeLabel(slide.type)
  const md = mdBlock(media.mdHtml)
  const imgs = media.imagesHtml
  const frame = media.iframeHtml
  const notes = media.notesHtml
  const bs = bulletsOf(slide)

  if (kind === 'cover') {
    return coverInner(slide, theme, ctx) + notes
  }
  if (kind === 'objectives') {
    const goals = (bs.length ? bs : [slide.content || '完成本课学习目标']).slice(0, 6)
    return `${kicker(label, ctx.index)}${heading(slide)}
      <div class="cw-goals">${goals.map((g, i) =>
        `<div class="cw-goal"><span class="cw-goal-n">${String(i + 1).padStart(2, '0')}</span><div>${vis(g)}</div></div>`
      ).join('')}</div>${md}${imgs}${notes}`
  }
  if (kind === 'knowledge') {
    return `${kicker(label, ctx.index)}${heading(slide)}
      <div class="cw-knowledge"><div class="cw-knowledge-bar"></div>
      <div>${pointsList(bs)}${md}${imgs}</div></div>${notes}`
  }
  if (kind === 'example') {
    const prompt = slide.prompt || (bs.length ? bs.join('；') : (slide.title || '例题'))
    const solText = String(slide.solution || '').trim()
    const solutionBody = solText ? vis(solText) : media.mdHtml
    const reveal = solutionBody
      ? `<details class="cw-reveal"><summary>想好后再看解析</summary><div class="body">${solutionBody}</div></details>`
      : ''
    return `${kicker(label, ctx.index)}${heading(slide)}
      <div class="cw-example">
        <div class="cw-example-q"><h3>题干</h3><div>${vis(String(prompt))}</div></div>
        ${reveal}
      </div>${imgs}${notes}`
  }
  if (kind === 'interactive') {
    return `${kicker(label, ctx.index)}${heading(slide)}${pointsList(bs)}${md}${frame}${imgs}${notes}`
  }
  if (kind === 'comparison') {
    const cols = columnsOf(slide)
    return `${kicker(label, ctx.index)}${heading(slide)}
      <div class="cw-compare">${cols.map((c, i) =>
        `<div class="cw-compare-col ${i ? 'b' : 'a'}"><h3>${vis(c.title)}</h3>${pointsList(c.items)}</div>`
      ).join('')}</div>${md}${imgs}${notes}`
  }
  if (kind === 'process') {
    const steps = stepsOf(slide)
    return `${kicker(label, ctx.index)}${heading(slide)}
      <div class="cw-steps">${steps.map((st, i) => `
        <div class="cw-step">
          <div class="cw-step-rail"><span class="cw-step-n">${i + 1}</span>${i < steps.length - 1 ? '<span class="cw-step-line"></span>' : ''}</div>
          <div class="cw-step-body"><strong>${vis(st.title)}</strong>${st.detail ? `<div class="body">${vis(st.detail)}</div>` : ''}</div>
        </div>`).join('')}</div>${md}${imgs}${notes}`
  }
  if (kind === 'summary') {
    return `${kicker(label, ctx.index)}${heading(slide)}
      <div class="cw-block-accent cw-summary-hero">今天带走这几件事</div>
      <div class="cw-summary-grid">${bs.map((b) => `<div class="cw-block">${vis(b)}</div>`).join('')}</div>
      ${md}${imgs}${notes}`
  }
  if (kind === 'exercise') {
    const qs = bs.length ? bs : (slide.content ? [slide.content] : ['完成本页练习'])
    return `${kicker(label, ctx.index)}${heading(slide)}
      <div class="cw-exercise">${qs.map((q, i) =>
        `<div class="cw-ex"><span class="cw-ex-n">${i + 1}</span><div>${vis(q)}</div></div>`
      ).join('')}</div>${md}${imgs}${frame}${notes}`
  }
  if (kind === 'homework') {
    const tasks = bs.length ? bs : ['完成课后巩固练习']
    return `${kicker(label, ctx.index)}${heading(slide)}
      <div class="cw-block-accent">分层任务：基础巩固 + 生活迁移 + 小作品</div>
      <div class="cw-hw">${tasks.map((t) =>
        `<div class="cw-hw-item"><span class="cw-hw-box"></span><div>${vis(t)}</div></div>`
      ).join('')}</div>${md}${imgs}${notes}`
  }
  return `${kicker(label, ctx.index)}${heading(slide)}${pointsList(bs)}${md}${imgs}${frame}${notes}`
}

export function buildSlideInner(
  slide: any,
  theme: CoursewareTheme,
  media: SlideMedia,
  ctx: SlideCtx,
): { kind: PageKind; className: string; inner: string } {
  const kind = normalizePageKind(slide?.type)
  const className = kind === 'cover'
    ? `cw-cover cw-cover--${theme.coverStyle}`
    : `cw-page--${kind}`
  return {
    kind,
    className,
    inner: `<div class="cw-inner">${innerByKind(kind, slide, media, ctx, theme)}</div>`,
  }
}

export function mediaFromSlide(
  slide: any,
  imageMap: Record<string, string>,
  opts: { wrapHtml?: (html: string) => string; notesMode?: 'aside' | 'details' | 'none' },
): SlideMedia {
  const imgs = (slide.images || [])
    .map((id: any) => imageMap[String(id)])
    .filter(Boolean) as string[]
  const imagesHtml = imgs.length
    ? `<div class="cw-imgs">${imgs.map((u) => `<img src="${escAttr(u)}" alt="" />`).join('')}</div>`
    : ''
  let iframeHtml = ''
  if (slide.html && opts.wrapHtml) {
    const app = isAppInteractiveHtml(slide.html)
    const label = app ? '实验台' : '互动动画'
    iframeHtml = `<div class="cw-fs-box">
      <div class="cw-fs-bar"><span>${label}</span><button type="button" class="cw-fs-btn" aria-pressed="false">全屏</button></div>
      <div class="cw-fs-stage">
        <iframe class="cw-iframe${app ? ' cw-iframe--app' : ''}" allow="fullscreen *" allowfullscreen sandbox="allow-scripts allow-popups allow-modals" srcdoc="${escAttr(opts.wrapHtml(slide.html))}"></iframe>
      </div>
    </div>`
  }
  let notesHtml = ''
  if (slide.notes && opts.notesMode === 'aside') {
    notesHtml = `<aside class="notes">${vis(slide.notes)}</aside>`
  } else if (slide.notes && opts.notesMode === 'details') {
    notesHtml = `<details class="cw-notes cw-block"><summary>教师讲稿 / 备注</summary><p>${vis(slide.notes)}</p></details>`
  }
  const mdHtml = slide.content ? renderMarkdown(normalizeChemText(slide.content)) : ''
  return { imagesHtml, iframeHtml, notesHtml, mdHtml }
}
