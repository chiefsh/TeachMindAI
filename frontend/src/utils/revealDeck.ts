// 用 reveal.js 把课件内容渲染成专业演示文稿（转场动画 / 演讲者视图 / 键盘翻页）。
// 互动页以内嵌 iframe 形式渲染，复用 wrapInteractiveHtml 保证隔离与统一样式。
import { renderMarkdown } from './markdown'
import { wrapInteractiveHtml } from './coursewareFrame'

const REVEAL_VERSION = '5.1.0'
const KATEX_VERSION = '0.16.11'

const TYPE_LABELS: Record<string, string> = {
  title: '封面', objectives: '教学目标', intro: '情境导入', content: '新知讲解',
  example: '例题精讲', activity: '课堂活动', interactive: '互动环节', summary: '课堂小结',
  homework: '课后作业', board: '板书设计', quiz: '随堂测验', exercise: '练习',
}

function esc(s: string): string {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function escAttr(s: string): string {
  return esc(s).replace(/"/g, '&quot;')
}

const DECK_STYLE = `
:root{--c-primary:#4f46e5;--c-accent:#0ea5e9;--c-text:#1e293b;--c-muted:#64748b;}
.reveal{font-family:-apple-system,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;}
.reveal h1,.reveal h2,.reveal h3{color:var(--c-text);text-transform:none;letter-spacing:0;}
.reveal .slide-label{display:inline-block;font-size:.42em;font-weight:700;color:#fff;background:var(--c-primary);
  padding:.15em .7em;border-radius:999px;margin-bottom:.4em;}
.reveal section{text-align:left;}
.reveal section.cover{text-align:center;}
.reveal .cover h1{font-size:2.0em;color:var(--c-primary);}
.reveal .cover .sub{color:var(--c-muted);font-size:.9em;margin-top:.4em;}
.reveal ul{display:block;}
.reveal .body{font-size:.78em;line-height:1.5;}
.reveal .body h3{font-size:1.05em;margin:.4em 0 .2em;color:var(--c-primary);}
.reveal .body h4{font-size:.95em;margin:.3em 0 .15em;}
.reveal .body code{background:#f1f5f9;color:#db2777;padding:.05em .3em;border-radius:4px;font-size:.85em;}
.reveal .cw-imgs{display:flex;gap:12px;flex-wrap:wrap;margin-top:.5em;}
.reveal .cw-imgs img{max-height:38vh;border-radius:10px;border:1px solid #e2e8f0;background:#f8fafc;object-fit:contain;}
.reveal .cw-iframe{width:100%;height:62vh;border:1px solid #e2e8f0;border-radius:12px;background:#fff;}
.reveal .meta-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1em;font-size:.7em;}
.reveal .meta-grid h3{font-size:1em;}
`

interface DeckImageMap { [id: string]: string }

function slideSection(slide: any, imageMap: DeckImageMap): string {
  const type = slide.type || 'content'
  const label = TYPE_LABELS[type] || ''
  const parts: string[] = []

  if (type === 'title') {
    parts.push('<section class="cover">')
    parts.push(`<h1>${esc(slide.title || '')}</h1>`)
    if (slide.subtitle) parts.push(`<p class="sub">${esc(slide.subtitle)}</p>`)
    parts.push('</section>')
    return parts.join('')
  }

  parts.push('<section>')
  if (label) parts.push(`<span class="slide-label">${esc(label)}</span>`)
  if (slide.title) parts.push(`<h2>${esc(slide.title)}</h2>`)
  if (slide.subtitle) parts.push(`<p style="color:var(--c-muted);font-size:.7em;margin-top:-.2em">${esc(slide.subtitle)}</p>`)

  parts.push('<div class="body">')
  if (Array.isArray(slide.bullets) && slide.bullets.length) {
    parts.push('<ul>' + slide.bullets.map((b: string) => `<li>${esc(b)}</li>`).join('') + '</ul>')
  }
  if (slide.content) parts.push(renderMarkdown(slide.content))
  parts.push('</div>')

  // 课本插图
  const imgs: string[] = (slide.images || [])
    .map((id: any) => imageMap[String(id)])
    .filter(Boolean)
  if (imgs.length) {
    parts.push('<div class="cw-imgs">' + imgs.map((u) => `<img src="${escAttr(u)}" />`).join('') + '</div>')
  }

  // 互动页：内嵌 iframe
  if (slide.html) {
    const doc = wrapInteractiveHtml(slide.html)
    parts.push(`<iframe class="cw-iframe" sandbox="allow-scripts allow-popups" srcdoc="${escAttr(doc)}"></iframe>`)
  }

  // 教师讲稿（演讲者视图，按 S 查看）
  if (slide.notes) {
    parts.push(`<aside class="notes">${esc(slide.notes)}</aside>`)
  }
  parts.push('</section>')
  return parts.join('')
}

function metaSection(meta: any): string {
  const blocks: [string, string[]][] = []
  if (meta.objectives?.length) blocks.push(['教学目标', meta.objectives])
  if (meta.key_points?.length) blocks.push(['教学重点', meta.key_points])
  if (meta.difficulties?.length) blocks.push(['教学难点', meta.difficulties])
  if (!blocks.length) return ''
  const cols = blocks.map(([h, items]) =>
    `<div><h3>${esc(h)}</h3><ul>${items.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>`
  ).join('')
  return `<section><span class="slide-label">课程概览</span><div class="meta-grid">${cols}</div></section>`
}

interface DeckOptions {
  /** 打印模式：用 reveal 的 view:'print' 排版并自动唤起浏览器打印（另存为 PDF）。 */
  print?: boolean
}

/** 由课件内容构建一份完整可独立运行的 reveal.js HTML 文档。 */
export function buildRevealDeck(content: any, imageMap: DeckImageMap = {}, opts: DeckOptions = {}): string {
  const meta = content?.meta || {}
  const slides: any[] = content?.slides || []

  const sections: string[] = []
  // 封面：优先用 slides 里的 title 页，否则用 meta 生成
  const hasCover = slides.some((s) => s.type === 'title')
  if (!hasCover) {
    sections.push(`<section class="cover"><h1>${esc(meta.title || '教学课件')}</h1>` +
      (meta.duration ? `<p class="sub">${esc(meta.duration)}</p>` : '') + '</section>')
  }
  const metaSec = metaSection(meta)

  let metaInserted = false
  for (const s of slides) {
    sections.push(slideSection(s, imageMap))
    // 在封面之后插入课程概览
    if (!metaInserted && s.type === 'title' && metaSec) {
      sections.push(metaSec)
      metaInserted = true
    }
  }
  if (!metaInserted && metaSec) sections.splice(hasCover ? 1 : 1, 0, metaSec)

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(meta.title || '教学课件')}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@${REVEAL_VERSION}/dist/reveal.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@${REVEAL_VERSION}/dist/theme/white.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/katex.min.css">
<style>${DECK_STYLE}</style>
</head>
<body>
<div class="reveal"><div class="slides">
${sections.join('\n')}
</div></div>
<script src="https://cdn.jsdelivr.net/npm/reveal.js@${REVEAL_VERSION}/dist/reveal.js"></script>
<script src="https://cdn.jsdelivr.net/npm/reveal.js@${REVEAL_VERSION}/plugin/notes/notes.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/contrib/auto-render.min.js"></script>
<script>
  var PRINT_MODE = ${opts.print ? 'true' : 'false'};
  Reveal.initialize({
    hash: false, slideNumber: 'c/t', transition: 'slide',
    width: 1280, height: 720, margin: 0.06,
    showSlideNumber: 'all',
    view: PRINT_MODE ? 'print' : null,
    plugins: [ RevealNotes ]
  });
  function renderMath(){
    try {
      if (window.renderMathInElement) {
        window.renderMathInElement(document.body, {
          delimiters: [
            {left:'\\\\[', right:'\\\\]', display:true},
            {left:'\\\\(', right:'\\\\)', display:false},
            {left:'$$', right:'$$', display:true}
          ], throwOnError:false
        });
      }
    } catch(e){}
  }
  Reveal.on('ready', function(){
    renderMath();
    if (PRINT_MODE) {
      // 等公式/布局稳定后唤起打印对话框，用户可“另存为 PDF”
      setTimeout(function(){ try { window.print(); } catch(e){} }, 800);
    }
  });
</script>
</body>
</html>`
}
