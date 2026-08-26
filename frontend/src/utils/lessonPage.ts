// 网页样式课件：把课件内容渲染成一份自包含、可独立打开的单页教学网页。
// 与 revealDeck.ts 对称——一个产出演示文稿（reveal.js），一个产出滚动阅读的网页；
// 互动片段同样复用 wrapInteractiveHtml，保证两种样式下的互动表现一致。
import { renderMarkdown } from './markdown'
import { wrapInteractiveHtml } from './coursewareFrame'
import { getTheme, type CoursewareTheme } from './coursewareTheme'

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

const pageStyle = (t: CoursewareTheme) => `
:root{
  --c-primary:${t.primary};--c-primary-soft:${t.primary}1a;--c-accent:${t.accent};
  --c-text:${t.text};--c-muted:${t.muted};--c-line:#e2e8f0;--c-bg:${t.bg};
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;background:var(--c-bg);color:var(--c-text);font-size:16px;line-height:1.75;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;
}
a{color:inherit;text-decoration:none}

.hero{background:linear-gradient(135deg,var(--c-primary),var(--c-accent));color:#fff;padding:56px 24px 48px;text-align:center}
.hero h1{margin:0;font-size:32px;line-height:1.35;font-weight:800}
.hero p{margin:10px 0 0;opacity:.9;font-size:15px}
.hero .tags{margin-top:18px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap}
.hero .tags span{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);
  padding:4px 12px;border-radius:999px;font-size:13px}

.layout{max-width:1120px;margin:0 auto;padding:28px 20px 72px;display:flex;gap:28px;align-items:flex-start}
.toc{position:sticky;top:24px;width:224px;flex-shrink:0;background:#fff;border:1px solid var(--c-line);
  border-radius:16px;padding:16px;max-height:calc(100vh - 48px);overflow-y:auto}
.toc h2{margin:0 0 10px;font-size:12px;letter-spacing:.12em;color:var(--c-muted);text-transform:uppercase}
.toc a{display:block;padding:7px 10px;border-radius:9px;font-size:14px;color:var(--c-muted);
  border-left:2px solid transparent;transition:all .15s}
.toc a:hover{background:var(--c-primary-soft);color:var(--c-primary)}
.toc a.active{background:var(--c-primary-soft);color:var(--c-primary);font-weight:600;border-left-color:var(--c-primary)}
main{flex:1;min-width:0;display:flex;flex-direction:column;gap:20px}

.card{background:#fff;border:1px solid var(--c-line);border-radius:18px;padding:26px 28px;
  box-shadow:0 1px 3px rgba(15,23,42,.04)}
.overview{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px}
.overview h3{margin:0 0 8px;font-size:13px;font-weight:700}
.overview ul{margin:0;padding-left:18px;font-size:14px;color:#475569}
.overview li{margin:3px 0}
.o-goal h3{color:var(--c-primary)}
.o-key h3{color:#059669}
.o-hard h3{color:#e11d48}

.sec{scroll-margin-top:20px}
.label{display:inline-block;padding:3px 12px;border-radius:999px;background:var(--c-primary-soft);
  color:var(--c-primary);font-size:12px;font-weight:700}
.sec h2{margin:12px 0 2px;font-size:22px;font-weight:700}
.sec .sub{margin:0 0 16px;color:var(--c-muted);font-size:14px}
.points{margin:0 0 18px;padding:0;list-style:none;display:flex;flex-direction:column;gap:8px}
.points li{background:#f8fafc;border:1px solid var(--c-line);border-radius:11px;padding:11px 15px;
  font-size:15px;display:flex;gap:9px}
.points li::before{content:"▸";color:var(--c-primary);font-weight:700}
/* renderMarkdown 会把 ### 渲染成 h5，这里统一覆盖各级小标题 */
.body h3,.body h4,.body h5,.body h6{margin:22px 0 8px;font-size:17px;font-weight:700;color:var(--c-primary)}
.body h3{font-size:19px}
.body h4{font-size:18px}
.body>:first-child{margin-top:0}
.body p{margin:9px 0}
.body ul{margin:9px 0;padding-left:22px}
.body li{margin:4px 0}
.body code{background:#f1f5f9;color:#db2777;padding:.1em .35em;border-radius:4px;font-size:.9em}
.imgs{display:flex;flex-wrap:wrap;gap:12px;margin-top:16px}
.imgs img{max-height:320px;max-width:100%;border:1px solid var(--c-line);border-radius:12px;
  background:#f8fafc;object-fit:contain}
.interactive{margin-top:20px}
.interactive .bar{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.interactive .bar span{font-size:13px;font-weight:700;color:#7c3aed}
.interactive iframe{width:100%;height:520px;border:1px solid var(--c-line);border-radius:14px;background:#fff}

.notes{margin-top:18px;border:1px solid #fde68a;background:#fffbeb;border-radius:12px;padding:12px 16px}
.notes summary{cursor:pointer;font-size:13px;font-weight:700;color:#b45309}
.notes p{margin:8px 0 0;font-size:14px;color:#92400e;white-space:pre-wrap}
body.hide-notes .notes{display:none}

.toolbar{position:fixed;right:20px;bottom:20px;display:flex;gap:8px;z-index:20}
.toolbar button{border:1px solid var(--c-line);background:#fff;color:var(--c-text);border-radius:999px;
  padding:9px 16px;font-size:13px;cursor:pointer;box-shadow:0 4px 12px rgba(15,23,42,.1)}
.toolbar button:hover{border-color:var(--c-primary);color:var(--c-primary)}

footer{text-align:center;color:var(--c-muted);font-size:13px;padding:0 20px 40px}

@media (max-width:900px){
  .layout{flex-direction:column;padding:20px 14px 60px}
  .toc{position:static;width:100%;max-height:none}
  .card{padding:20px 18px}
  .hero{padding:40px 18px 34px}
  .hero h1{font-size:25px}
}
@media print{
  body{background:#fff}
  .toc,.toolbar{display:none}
  .card{break-inside:avoid;box-shadow:none}
}
`

const PAGE_SCRIPT = `
(function(){
  // 目录高亮：滚动到哪一节就点亮哪一项
  var links = Array.prototype.slice.call(document.querySelectorAll('.toc a'));
  var sections = links
    .map(function(a){ return document.getElementById(a.getAttribute('href').slice(1)); })
    .filter(Boolean);
  function activate(id){
    links.forEach(function(a){ a.classList.toggle('active', a.getAttribute('href') === '#' + id); });
  }
  if (window.IntersectionObserver && sections.length) {
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(e){ if (e.isIntersecting) activate(e.target.id); });
    }, { rootMargin: '-15% 0px -70% 0px', threshold: 0 });
    sections.forEach(function(s){ io.observe(s); });
  }

  // 讲稿默认隐藏：这份网页会直接分享给学生，教师需要时再展开
  var notesBtn = document.getElementById('toggle-notes');
  if (notesBtn) {
    notesBtn.addEventListener('click', function(){
      var hidden = document.body.classList.toggle('hide-notes');
      notesBtn.textContent = hidden ? '显示教师讲稿' : '隐藏教师讲稿';
    });
  }
  var printBtn = document.getElementById('print-page');
  if (printBtn) printBtn.addEventListener('click', function(){ window.print(); });

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
  window.addEventListener('load', renderMath);
})();
`

interface PageImageMap { [id: string]: string }

function sectionHtml(slide: any, index: number, imageMap: PageImageMap): string {
  const type = slide.type || 'content'
  const label = TYPE_LABELS[type] || ''
  const parts: string[] = [`<section class="card sec" id="sec-${index}">`]

  if (label) parts.push(`<span class="label">${esc(label)}</span>`)
  if (slide.title) parts.push(`<h2>${esc(slide.title)}</h2>`)
  if (slide.subtitle) parts.push(`<p class="sub">${esc(slide.subtitle)}</p>`)

  if (Array.isArray(slide.bullets) && slide.bullets.length) {
    parts.push(
      '<ul class="points">' +
      slide.bullets.filter(Boolean).map((b: string) => `<li><span>${esc(b)}</span></li>`).join('') +
      '</ul>'
    )
  }
  if (slide.content) parts.push(`<div class="body">${renderMarkdown(slide.content)}</div>`)

  const imgs: string[] = (slide.images || []).map((id: any) => imageMap[String(id)]).filter(Boolean)
  if (imgs.length) {
    parts.push('<div class="imgs">' + imgs.map((u) => `<img src="${escAttr(u)}" alt="" />`).join('') + '</div>')
  }

  if (slide.html) {
    const doc = wrapInteractiveHtml(slide.html)
    parts.push(
      '<div class="interactive"><div class="bar"><span>互动练习</span></div>' +
      `<iframe sandbox="allow-scripts allow-popups" srcdoc="${escAttr(doc)}"></iframe></div>`
    )
  }

  if (slide.notes) {
    parts.push(
      `<details class="notes"><summary>教师讲稿 / 备注</summary><p>${esc(slide.notes)}</p></details>`
    )
  }

  parts.push('</section>')
  return parts.join('')
}

function overviewHtml(meta: any): string {
  const blocks: [string, string, string[]][] = []
  if (meta.objectives?.length) blocks.push(['o-goal', '教学目标', meta.objectives])
  if (meta.key_points?.length) blocks.push(['o-key', '教学重点', meta.key_points])
  if (meta.difficulties?.length) blocks.push(['o-hard', '教学难点', meta.difficulties])
  if (!blocks.length) return ''
  const cols = blocks.map(([cls, title, items]) =>
    `<div class="${cls}"><h3>${esc(title)}</h3><ul>` +
    items.map((x) => `<li>${esc(x)}</li>`).join('') +
    '</ul></div>'
  ).join('')
  return `<section class="card overview" id="sec-overview">${cols}</section>`
}

interface PageOptions {
  /** 副标题，通常为「年级 · 科目」等上下文信息 */
  subtitle?: string
  /** 视觉主题 key，见 coursewareTheme.ts */
  theme?: string
}

/** 由课件内容构建一份自包含的网页课件 HTML 文档（可直接下载或在 iframe 中预览）。 */
export function buildLessonPage(content: any, imageMap: PageImageMap = {}, opts: PageOptions = {}): string {
  const meta = content?.meta || {}
  const slides: any[] = content?.slides || []
  const title = meta.title || '教学课件'
  const theme = getTheme(opts.theme)

  // 封面页信息并入 hero，正文只渲染其余小节
  const cover = slides.find((s) => s.type === 'title')
  const bodySlides = slides.filter((s) => s !== cover)

  const overview = overviewHtml(meta)
  const sections = bodySlides.map((s, i) => sectionHtml(s, i, imageMap)).join('\n')

  const tocItems: string[] = []
  if (overview) tocItems.push('<a href="#sec-overview">课程概览</a>')
  bodySlides.forEach((s, i) => {
    tocItems.push(`<a href="#sec-${i}">${esc(s.title || TYPE_LABELS[s.type] || `第 ${i + 1} 节`)}</a>`)
  })

  const heroTags = [opts.subtitle, meta.duration, cover?.subtitle]
    .filter(Boolean)
    .map((t: string) => `<span>${esc(t)}</span>`)
    .join('')

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/katex.min.css">
<style>${pageStyle(theme)}</style>
</head>
<body class="hide-notes">
<header class="hero">
  <h1>${esc(title)}</h1>
  ${meta.topic ? `<p>${esc(meta.topic)}</p>` : ''}
  ${heroTags ? `<div class="tags">${heroTags}</div>` : ''}
</header>
<div class="layout">
  <nav class="toc"><h2>目录</h2>${tocItems.join('')}</nav>
  <main>
${overview}
${sections}
  </main>
</div>
<footer>本网页课件由智课星生成，可离线保存与分享</footer>
<div class="toolbar">
  <button id="toggle-notes" type="button">显示教师讲稿</button>
  <button id="print-page" type="button">打印 / 存为 PDF</button>
</div>
<script src="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/contrib/auto-render.min.js"></script>
<script>${PAGE_SCRIPT}</script>
</body>
</html>`
}
