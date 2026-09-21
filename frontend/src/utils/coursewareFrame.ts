// 互动课件 iframe 统一包装器：为大模型生成的 html 片段注入统一设计系统与常用库
// （KaTeX 公式、Chart.js 图表），保证风格一致、效果可靠。class 命名需与后端
// backend/app/services/courseware_components.py 中的 DESIGN_SYSTEM_SPEC 保持一致。
import { getTheme, type CoursewareTheme } from './coursewareTheme'

function designSystem(t: CoursewareTheme) {
  return `
:root{
  --c-primary:${t.primary}; --c-accent:${t.accent}; --c-ok:#16a34a; --c-bad:#dc2626;
  --c-line:${t.surface}; --c-bg:${t.bg}; --c-text:${t.text}; --c-muted:${t.muted};
  --c-card:${t.card}; --shadow:${t.shadowSoft};
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  font-family:-apple-system,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;
  color:var(--c-text); background:var(--c-bg); line-height:1.6; font-size:15px;
}
.stage{padding:20px}
.title{font-size:20px;font-weight:700;margin:0 0 4px}
.subtitle{font-size:14px;color:var(--c-muted);margin:0 0 14px}
.muted{color:var(--c-muted)}
.card{background:var(--c-card);border:1px solid var(--c-line);border-radius:14px;padding:16px;box-shadow:var(--shadow)}
.panel{background:var(--c-line);border:1px solid var(--c-line);border-radius:12px;padding:14px}
.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.center{display:flex;align-items:center;justify-content:center}
.grid{display:grid;grid-template-columns:repeat(var(--cols,2),minmax(0,1fr));gap:12px}
.btn{appearance:none;border:1px solid var(--c-line);background:var(--c-card);color:var(--c-text);
  padding:8px 16px;border-radius:10px;font-size:14px;cursor:pointer;transition:all .15s;font-weight:500}
.btn:hover{border-color:var(--c-primary);color:var(--c-primary)}
.btn.primary{background:var(--c-primary);border-color:var(--c-primary);color:#fff}
.btn.primary:hover{filter:brightness(1.08)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;background:#eef2ff;color:var(--c-primary);font-size:12px;font-weight:600}
.chip{display:inline-flex;align-items:center;padding:8px 14px;border-radius:10px;border:1px solid var(--c-line);
  background:var(--c-card);cursor:grab;user-select:none;transition:all .15s;font-size:14px}
.chip:active{cursor:grabbing}
.chip.dragover{border-color:var(--c-primary);background:#eef2ff}
.correct{border-color:var(--c-ok)!important;background:#f0fdf4!important;color:var(--c-ok)!important}
.wrong{border-color:var(--c-bad)!important;background:#fef2f2!important;color:var(--c-bad)!important}
.hint{padding:10px 14px;border-radius:10px;background:#fffbeb;border:1px solid #fde68a;color:#92400e;font-size:14px}
canvas{max-width:100%}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes pop{0%{transform:scale(.8);opacity:0}60%{transform:scale(1.05)}100%{transform:scale(1);opacity:1}}
@keyframes floatY{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
.fade-in{animation:fadeIn .4s ease both}
.pop{animation:pop .35s ease both}
.float{animation:floatY 2.6s ease-in-out infinite}
`
}

const KATEX_VERSION = '0.16.11'
const CHARTJS_VERSION = '4.4.4'

const KATEX_LIBS = `
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/contrib/auto-render.min.js"></script>
`
const CHART_LIBS = `
<script defer src="https://cdn.jsdelivr.net/npm/chart.js@${CHARTJS_VERSION}/dist/chart.umd.min.js"></script>
`

function needsKatex(html: string): boolean {
  return /\$\$|\\\(|\\\[|katex|mathjax/i.test(html)
}
function needsChart(html: string): boolean {
  return /chart\.js|new\s+Chart\b|window\.Chart|canvas/i.test(html)
}

// 作答数据回收桥接：互动页通过 window.CW.report/correct/wrong 把结果回传给上层页面
const CW_BRIDGE = `
<script>
(function(){
  function send(payload){
    try { parent.postMessage({ __cw: true, type: 'interaction', payload: payload || {} }, '*'); } catch(e){}
  }
  window.CW = {
    report: function(data){ send(data || {}); },
    correct: function(question, answer){ send({ question: question, answer: answer, correct: true }); },
    wrong: function(question, answer){ send({ question: question, answer: answer, correct: false }); }
  };
})();
</script>
`

// 公式自动渲染：等库加载完成后执行
const BOOT = `
<script>
window.addEventListener('load', function(){
  try {
    if (window.renderMathInElement) {
      window.renderMathInElement(document.body, {
        delimiters: [
          {left:'\\\\[', right:'\\\\]', display:true},
          {left:'\\\\(', right:'\\\\)', display:false},
          {left:'$$', right:'$$', display:true}
        ],
        throwOnError:false
      });
    }
  } catch(e){}
});
</script>
`

/** skill 产出的整页应用（如宏观实验台），需要比普通互动片段更高的 iframe。 */
export function isAppInteractiveHtml(html?: string | null): boolean {
  const s = html || ''
  return /<html[\s>]/i.test(s) || /id=["']lab-data["']/.test(s)
}

/** 父页监听后按内容撑开 `.cw-iframe`。全屏时不改高度，避免把实验台压回去。 */
export const IFRAME_AUTO_HEIGHT = `
(function(){
  function fsNow(){ return document.fullscreenElement || document.webkitFullscreenElement || null; }
  window.addEventListener('message', function(e){
    var d = e.data;
    if (!d || d.__cw !== true || d.type !== 'resize') return;
    var h = Number(d.height);
    if (!h || h < 200) return;
    var frames = document.querySelectorAll('iframe.cw-iframe');
    for (var i = 0; i < frames.length; i++) {
      if (frames[i].contentWindow === e.source) {
        var box = frames[i].closest('.cw-fs-box');
        var cur = fsNow();
        if (cur && (cur === box || cur === frames[i] || (box && box.contains(cur)))) return;
        var cap = frames[i].classList.contains('cw-iframe--app') ? 1100 : 720;
        frames[i].style.height = Math.min(Math.max(Math.ceil(h), 360), cap) + 'px';
        break;
      }
    }
  });
})();
`

/** 网页课件 / 演示稿里的动画、实验台：点「全屏」走铺满视口遮罩（与互动动画「全屏演示」一致）。 */
export const IFRAME_FULLSCREEN = `
(function(){
  var layer = null;
  var presentFrame = null;
  var presentUrl = '';
  function embedded(){ return !!(window.parent && window.parent !== window); }
  function srcOf(box){
    var frame = box.querySelector('iframe.cw-iframe');
    return frame ? (frame.getAttribute('srcdoc') || '') : '';
  }
  function titleOf(box){
    var el = box.querySelector('.cw-fs-bar span');
    return (el && el.textContent) ? String(el.textContent).trim() : '实验台';
  }
  function askParent(action, extra){
    extra = extra || {};
    try {
      parent.postMessage({
        __cw: true,
        type: 'fullscreen',
        action: action,
        title: extra.title || '',
        srcdoc: extra.srcdoc || ''
      }, '*');
      return true;
    } catch (e) { return false; }
  }
  function revoke(){
    if (presentUrl) { try { URL.revokeObjectURL(presentUrl); } catch (e) {} presentUrl = ''; }
  }
  function ensureLayer(){
    if (layer) return;
    layer = document.createElement('div');
    layer.id = 'cw-present-layer';
    layer.innerHTML = '<div class="cw-present-bar"><span class="cw-present-title"></span><span class="cw-present-hint">Esc 退出全屏</span><button type="button" class="cw-present-exit">退出</button></div><iframe class="cw-present-frame" sandbox="allow-scripts allow-same-origin allow-popups allow-modals" allow="fullscreen"></iframe>';
    document.body.appendChild(layer);
    presentFrame = layer.querySelector('iframe');
    layer.querySelector('.cw-present-exit').addEventListener('click', function(ev){
      ev.preventDefault();
      exitLocal();
    });
  }
  function isOn(){ return !!(layer && layer.classList.contains('is-on')); }
  function enterLocal(box){
    var html = srcOf(box);
    if (!html) return;
    ensureLayer();
    layer.querySelector('.cw-present-title').textContent = titleOf(box);
    revoke();
    presentUrl = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }));
    presentFrame.src = presentUrl;
    layer.classList.add('is-on');
    document.documentElement.classList.add('cw-fs-lock');
    if (document.body) document.body.classList.add('cw-fs-lock');
    var req = layer.requestFullscreen || layer.webkitRequestFullscreen;
    if (req) {
      try {
        var p = req.call(layer);
        if (p && typeof p.catch === 'function') p.catch(function(){});
      } catch (e) {}
    }
  }
  function exitLocal(){
    if (!isOn()) return;
    layer.classList.remove('is-on');
    if (presentFrame) presentFrame.removeAttribute('src');
    revoke();
    document.documentElement.classList.remove('cw-fs-lock');
    if (document.body) document.body.classList.remove('cw-fs-lock');
    var cur = document.fullscreenElement || document.webkitFullscreenElement;
    if (cur) {
      var x = document.exitFullscreen || document.webkitExitFullscreen;
      if (x) try { x.call(document); } catch (e) {}
    }
  }
  document.addEventListener('click', function(e){
    var t = e.target;
    if (t && t.nodeType === 3) t = t.parentElement;
    var btn = t && t.closest && t.closest('.cw-fs-btn');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    var box = btn.closest('.cw-fs-box');
    if (!box) return;
    if (embedded()) {
      askParent('enter', { title: titleOf(box), srcdoc: srcOf(box) });
      return;
    }
    if (isOn()) exitLocal();
    else enterLocal(box);
  });
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape' && isOn()) exitLocal();
  });
})();
`

const IFRAME_REPORT_HEIGHT = `
<script>
(function(){
  function sendH(){
    var el = document.documentElement;
    var h = Math.max(el ? el.scrollHeight : 0, document.body ? document.body.scrollHeight : 0);
    try { parent.postMessage({ __cw: true, type: 'resize', height: h }, '*'); } catch(e){}
  }
  window.addEventListener('load', sendH);
  window.addEventListener('resize', sendH);
  setTimeout(sendH, 80);
  setTimeout(sendH, 400);
})();
</script>
`

const APP_EMBED_CSS = `
<style id="cw-embed-fix">
html,body{height:100%!important;overflow:hidden!important;min-height:640px!important}
.wrap{grid-template-columns:196px minmax(0,1fr) 200px!important;flex:1;min-height:0!important;overflow:hidden}
.stage{min-height:0!important;overflow:hidden}
#view,#bench{min-height:0!important;width:100%!important;height:100%}
.palette{position:relative!important;left:auto!important;top:auto!important;max-width:none!important;z-index:1;overflow:auto}
.log-col{min-height:0!important;overflow:hidden!important;display:flex;flex-direction:column}
#log{flex:1;min-height:0;overflow-y:auto}
.hint-bar,.stage-hint{position:static!important;max-width:none!important}
@media (max-width:720px){
  html,body{height:auto!important;overflow:auto!important}
  .wrap{grid-template-columns:1fr!important;min-height:0!important}
}
</style>
`

function injectHostScripts(html: string): string {
  const labFix = /id=["']lab-data["']/.test(html) ? APP_EMBED_CSS : ''
  const extra = `${labFix}${CW_BRIDGE}${IFRAME_REPORT_HEIGHT}`
  if (/<\/body>/i.test(html)) return html.replace(/<\/body>/i, extra + '</body>')
  return html + extra
}

/** 把模型生成的 html 片段包装成可在 iframe 中渲染的完整文档字符串。
 *
 *  注意：调用方应通过 createIframeBlob() 生成 Blob URL 后赋给 iframe.src，
 *  以避免 srcdoc 模式下 </script> 被 HTML 解析器提前截断的问题。
 *  若调用方坚持使用 srcdoc，也可直接使用返回字符串，但 Chrome 以外的浏览器
 *  可能出现 SyntaxError。
 */
export function wrapInteractiveHtml(fragment: string, theme?: CoursewareTheme | string): string {
  const body = (fragment || '').trim()
  if (/<html[\s>]/i.test(body)) return injectHostScripts(body)
  const t = typeof theme === 'string' || !theme ? getTheme(theme as string) : theme
  // 按内容按需注入 CDN，避免每个 iframe 都拉 KaTeX + Chart.js
  const libs = [
    needsKatex(body) ? KATEX_LIBS : '',
    needsChart(body) ? CHART_LIBS : '',
  ].join('')
  const boot = needsKatex(body) ? BOOT : ''
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
${CW_BRIDGE}
${libs}
<style>${designSystem(t)}</style>
</head>
<body>
${body}
${boot}
${IFRAME_REPORT_HEIGHT}
</body>
</html>`
}

/** 生成 Blob URL（调用方负责在组件卸载时 revokeObjectURL）。 */
export function createIframeBlob(fragment: string, theme?: CoursewareTheme | string): string {
  const html = wrapInteractiveHtml(fragment, theme)
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  return URL.createObjectURL(blob)
}
