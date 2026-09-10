// 网页样式课件：把课件内容渲染成一份自包含、可独立打开的单页教学网页。
// 与 revealDeck.ts 对称——一个产出演示文稿（reveal.js），一个产出滚动阅读的网页；
// 互动片段同样复用 wrapInteractiveHtml，保证两种样式下的互动表现一致。
import { wrapInteractiveHtml } from './coursewareFrame'
import { getTheme, type CoursewareTheme } from './coursewareTheme'
import {
  buildSlideInner, decoSvg, esc, mediaFromSlide, pageCss, pageTypeLabel,
} from './coursewarePages'

const KATEX_VERSION = '0.16.11'

const chrome = (t: CoursewareTheme) => `
${pageCss(t, 'page')}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;background:var(--c-bg);color:var(--c-text);font-size:16px;line-height:1.75;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;
}
a{color:inherit;text-decoration:none}
.layout{max-width:1120px;margin:0 auto;padding:28px 20px 72px;display:flex;gap:28px;align-items:flex-start}
.toc{position:sticky;top:24px;width:224px;flex-shrink:0;background:var(--c-card);box-shadow:var(--shadow-soft);
  border-radius:16px;padding:16px;max-height:calc(100vh - 48px);overflow-y:auto}
.toc h2{margin:0 0 10px;font-size:12px;letter-spacing:.12em;color:var(--c-muted);text-transform:uppercase}
.toc a{display:block;padding:7px 10px;border-radius:9px;font-size:14px;color:var(--c-muted);
  border-left:2px solid transparent;transition:all .15s}
.toc a:hover,.toc a.active{background:var(--c-primary-soft);color:var(--c-primary);font-weight:600;border-left-color:var(--c-primary)}
main{flex:1;min-width:0;display:flex;flex-direction:column;gap:20px}
.cw-page.sec{scroll-margin-top:20px;border-radius:20px;box-shadow:var(--shadow);min-height:auto}
.cw-page.sec .cw-inner{padding:26px 28px}
.cw-cover.sec .cw-inner{padding:0;min-height:280px}
.cw-cover--split.sec .cw-inner{display:grid;grid-template-columns:42% 1fr;min-height:320px}
.overview{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}
.toolbar{position:fixed;right:20px;bottom:20px;display:flex;gap:8px;z-index:20}
.toolbar button{border:0;background:var(--c-card);color:var(--c-text);border-radius:999px;
  padding:9px 16px;font-size:13px;cursor:pointer;box-shadow:var(--shadow)}
.toolbar button:hover{color:var(--c-primary)}
footer{text-align:center;color:var(--c-muted);font-size:13px;padding:0 20px 40px}
body.hide-notes .cw-notes{display:none}
@media (max-width:900px){
  .layout{flex-direction:column;padding:20px 14px 60px}
  .toc{position:static;width:100%;max-height:none}
  .cw-page.sec .cw-inner{padding:20px 18px}
}
@media print{
  .toc,.toolbar{display:none}
  .cw-page{box-shadow:none;break-inside:avoid}
}
`

const PAGE_SCRIPT = `
(function(){
  var links = Array.prototype.slice.call(document.querySelectorAll('.toc a'));
  var sections = links
    .map(function(a){ return document.getElementById((a.getAttribute('href') || '').replace(/^#/, '')); })
    .filter(Boolean);
  function activate(id){
    links.forEach(function(a){ a.classList.toggle('active', a.getAttribute('href') === '#' + id); });
  }
  // 预览在 sandbox iframe 里，href="#id" 会被当成导航拦掉，必须脚本滚动。
  links.forEach(function(a){
    a.addEventListener('click', function(e){
      var id = (a.getAttribute('href') || '').replace(/^#/, '');
      var el = id && document.getElementById(id);
      if (!el) return;
      e.preventDefault();
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      activate(id);
    });
  });
  if (window.IntersectionObserver && sections.length) {
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(e){ if (e.isIntersecting) activate(e.target.id); });
    }, { rootMargin: '-15% 0px -70% 0px', threshold: 0 });
    sections.forEach(function(s){ io.observe(s); });
  }
  var notesBtn = document.getElementById('toggle-notes');
  if (notesBtn) {
    notesBtn.addEventListener('click', function(){
      var hidden = document.body.classList.toggle('hide-notes');
      notesBtn.textContent = hidden ? '显示教师讲稿' : '隐藏教师讲稿';
    });
  }
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

function sectionHtml(
  slide: any, index: number, imageMap: PageImageMap, theme: CoursewareTheme, subject?: string,
): string {
  const media = mediaFromSlide(slide, imageMap, {
    wrapHtml: (html) => wrapInteractiveHtml(html, theme),
    notesMode: 'details',
  })
  const view = buildSlideInner(slide, theme, media, { index: index + 1, subject })
  return `<section class="cw-page sec ${view.className}" id="sec-${index}">${decoSvg(theme)}${view.inner}</section>`
}

function overviewHtml(meta: any, theme: CoursewareTheme): string {
  const blocks: [string, string, string[]][] = []
  if (meta.objectives?.length) blocks.push(['教学目标', 'var(--c-primary)', meta.objectives])
  if (meta.key_points?.length) blocks.push(['教学重点', 'var(--c-accent)', meta.key_points])
  if (meta.difficulties?.length) blocks.push(['教学难点', 'var(--c-primary)', meta.difficulties])
  if (!blocks.length) return ''
  const cols = blocks.map(([title, color, items]) =>
    `<div class="cw-block" style="border-top:4px solid ${color}"><h3 style="margin:0 0 8px;color:${color}">${esc(title)}</h3><ul>` +
    items.map((x) => `<li>${esc(x)}</li>`).join('') +
    '</ul></div>'
  ).join('')
  return `<section class="cw-page sec" id="sec-overview">${decoSvg(theme)}
    <div class="cw-inner"><span class="cw-kicker">课程概览</span>
    <div class="overview" style="margin-top:12px">${cols}</div></div></section>`
}

interface PageOptions {
  subtitle?: string
  theme?: string
  subject?: string
}

/** 由课件内容构建一份自包含的网页课件 HTML 文档（可直接下载或在 iframe 中预览）。 */
export function buildLessonPage(content: any, imageMap: PageImageMap = {}, opts: PageOptions = {}): string {
  const meta = content?.meta || {}
  const slides: any[] = content?.slides || []
  const title = meta.title || '教学课件'
  const theme = getTheme(opts.theme)
  const subject = opts.subject || meta.subject || ''

  const cover = slides.find((s) => s.type === 'title' || s.type === 'cover')
  const bodySlides = slides.filter((s) => s !== cover)
  const coverSlide = {
    type: 'cover',
    title: cover?.title || title,
    subtitle: cover?.subtitle || opts.subtitle || meta.duration || '',
  }

  const coverHtml = sectionHtml({ ...coverSlide, type: coverSlide.type || 'cover' }, -1, {}, theme, subject)
    .replace('id="sec--1"', 'id="sec-cover"')
  const overview = overviewHtml(meta, theme)
  const sections = bodySlides.map((s, i) => sectionHtml(s, i, imageMap, theme, subject)).join('\n')

  const tocItems: string[] = ['<a href="#sec-cover">封面</a>']
  if (overview) tocItems.push('<a href="#sec-overview">课程概览</a>')
  bodySlides.forEach((s, i) => {
    tocItems.push(`<a href="#sec-${i}">${esc(s.title || pageTypeLabel(s.type) || `第 ${i + 1} 节`)}</a>`)
  })

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/katex.min.css">
<style>${chrome(theme)}</style>
</head>
<body class="hide-notes">
${coverHtml}
<div class="layout">
  <nav class="toc"><h2>目录</h2>${tocItems.join('')}</nav>
  <main>
${overview}
${sections}
  </main>
</div>
<footer>本网页课件由知序台生成，可离线保存与分享</footer>
<div class="toolbar">
  <button id="toggle-notes" type="button">显示教师讲稿</button>
</div>
<script src="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/contrib/auto-render.min.js"></script>
<script>${PAGE_SCRIPT}</script>
</body>
</html>`
}

export { pageTypeLabel }
