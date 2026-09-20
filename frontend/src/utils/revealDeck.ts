// 用 reveal.js 把课件内容渲染成专业演示文稿（转场动画 / 演讲者视图 / 键盘翻页）。
// 互动页以内嵌 iframe 形式渲染，复用 wrapInteractiveHtml 保证隔离与统一样式。
import { wrapInteractiveHtml, IFRAME_AUTO_HEIGHT } from './coursewareFrame'
import { getTheme, type CoursewareTheme } from './coursewareTheme'
import {
  buildSlideInner, decoSvg, esc, mediaFromSlide, pageCss,
} from './coursewarePages'

const REVEAL_VERSION = '5.1.0'
const KATEX_VERSION = '0.16.11'

const deckChrome = (t: CoursewareTheme) => `
${pageCss(t, 'deck')}
.reveal{font-family:-apple-system,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;background:var(--c-bg)}
.reveal .slides{background:transparent}
.reveal h1,.reveal h2,.reveal h3{color:inherit;text-transform:none;letter-spacing:0}
.reveal .slides>section.cw-page{text-align:left;background:var(--c-bg)!important}
.reveal ul{display:block}
@media screen{
  .reveal .slides>section,
  .reveal .slides>section>section{
    height:720px;max-height:720px;
    overflow-y:auto;overflow-x:hidden;
    padding:28px 40px;box-sizing:border-box;
    scrollbar-width:thin;
  }
  .reveal .slides>section.cw-cover{padding:0;overflow:hidden}
  .reveal .slides>section.cw-cover .cw-inner{height:720px;box-sizing:border-box;padding:48px 56px;display:flex;flex-direction:column;justify-content:center}
  .reveal .slides>section.cw-cover--split .cw-inner{display:grid;grid-template-columns:42% 1fr;padding:0;height:720px}
  .reveal .slides>section.cw-cover--ribbon .cw-inner{padding:0;justify-content:center}
  .reveal .slides>section::-webkit-scrollbar{width:8px}
  .reveal .slides>section::-webkit-scrollbar-thumb{background:var(--c-muted);border-radius:4px}
}
.reveal .meta-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1em}
`

interface DeckImageMap { [id: string]: string }

function slideSection(slide: any, imageMap: DeckImageMap, theme: CoursewareTheme, ctx: { index: number; subject?: string }): string {
  const media = mediaFromSlide(slide, imageMap, {
    wrapHtml: (html) => wrapInteractiveHtml(html, theme),
    notesMode: 'aside',
  })
  const view = buildSlideInner(slide, theme, media, { index: ctx.index, subject: ctx.subject })
  return `<section class="cw-page ${view.className}">${decoSvg(theme)}${view.inner}</section>`
}

function metaSection(meta: any, theme: CoursewareTheme): string {
  const blocks: [string, string[]][] = []
  if (meta.objectives?.length) blocks.push(['教学目标', meta.objectives])
  if (meta.key_points?.length) blocks.push(['教学重点', meta.key_points])
  if (meta.difficulties?.length) blocks.push(['教学难点', meta.difficulties])
  if (!blocks.length) return ''
  const cols = blocks.map(([h, items], i) =>
    `<div class="cw-block" style="border-top:4px solid ${i === 1 ? 'var(--c-accent)' : 'var(--c-primary)'}">
      <h3 style="margin:0 0 .4em;color:var(--c-primary)">${esc(h)}</h3>
      <ul>${items.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>`
  ).join('')
  return `<section class="cw-page cw-page--objectives">${decoSvg(theme)}
    <div class="cw-inner"><span class="cw-kicker">备课备忘</span>
    <div class="meta-grid" style="margin-top:12px">${cols}</div></div></section>`
}

interface DeckOptions {
  print?: boolean
  theme?: string
  subject?: string
}

/** 由课件内容构建一份完整可独立运行的 reveal.js HTML 文档。 */
export function buildRevealDeck(content: any, imageMap: DeckImageMap = {}, opts: DeckOptions = {}): string {
  const meta = content?.meta || {}
  const slides: any[] = content?.slides || []
  const theme = getTheme(opts.theme)
  const subject = opts.subject || meta.subject || ''

  const sections: string[] = []
  const hasCover = slides.some((s) => s.type === 'title' || s.type === 'cover')
  if (!hasCover) {
    sections.push(slideSection(
      { type: 'cover', title: meta.title || '教学课件', subtitle: meta.duration || '' },
      {}, theme, { index: 0, subject },
    ))
  }
  const metaSec = metaSection(meta, theme)

  slides.forEach((s, i) => {
    sections.push(slideSection(s, imageMap, theme, { index: i + 1, subject }))
  })
  if (metaSec) sections.push(metaSec)

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(meta.title || '教学课件')}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@${REVEAL_VERSION}/dist/reveal.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@${REVEAL_VERSION}/dist/theme/white.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/katex.min.css">
<style>${deckChrome(theme)}</style>
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
    width: 1280, height: 720, margin: 0.04,
    center: false,
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
      setTimeout(function(){ try { window.print(); } catch(e){} }, 800);
    }
  });
</script>
<script>${IFRAME_AUTO_HEIGHT}</script>
</body>
</html>`
}
