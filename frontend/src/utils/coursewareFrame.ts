// 互动课件 iframe 统一包装器：为大模型生成的 html 片段注入统一设计系统与常用库
// （KaTeX 公式、Chart.js 图表），保证风格一致、效果可靠。class 命名需与后端
// backend/app/services/courseware_components.py 中的 DESIGN_SYSTEM_SPEC 保持一致。

const DESIGN_SYSTEM = `
:root{
  --c-primary:#4f46e5; --c-accent:#0ea5e9; --c-ok:#16a34a; --c-bad:#dc2626;
  --c-line:#e2e8f0; --c-bg:#ffffff; --c-text:#1e293b; --c-muted:#64748b;
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
.card{background:#fff;border:1px solid var(--c-line);border-radius:14px;padding:16px;box-shadow:0 1px 3px rgba(15,23,42,.04)}
.panel{background:#f8fafc;border:1px solid var(--c-line);border-radius:12px;padding:14px}
.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.center{display:flex;align-items:center;justify-content:center}
.grid{display:grid;grid-template-columns:repeat(var(--cols,2),minmax(0,1fr));gap:12px}
.btn{appearance:none;border:1px solid var(--c-line);background:#fff;color:var(--c-text);
  padding:8px 16px;border-radius:10px;font-size:14px;cursor:pointer;transition:all .15s;font-weight:500}
.btn:hover{border-color:var(--c-primary);color:var(--c-primary)}
.btn.primary{background:var(--c-primary);border-color:var(--c-primary);color:#fff}
.btn.primary:hover{filter:brightness(1.08)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;background:#eef2ff;color:var(--c-primary);font-size:12px;font-weight:600}
.chip{display:inline-flex;align-items:center;padding:8px 14px;border-radius:10px;border:1px solid var(--c-line);
  background:#fff;cursor:grab;user-select:none;transition:all .15s;font-size:14px}
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

const KATEX_VERSION = '0.16.11'
const CHARTJS_VERSION = '4.4.4'

const HEAD_LIBS = `
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/contrib/auto-render.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/chart.js@${CHARTJS_VERSION}/dist/chart.umd.min.js"></script>
`

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

/** 把模型生成的 html 片段包装成可在 iframe 中渲染的完整文档字符串。
 *
 *  注意：调用方应通过 createIframeBlob() 生成 Blob URL 后赋给 iframe.src，
 *  以避免 srcdoc 模式下 </script> 被 HTML 解析器提前截断的问题。
 *  若调用方坚持使用 srcdoc，也可直接使用返回字符串，但 Chrome 以外的浏览器
 *  可能出现 SyntaxError。
 */
export function wrapInteractiveHtml(fragment: string): string {
  const body = (fragment || '').trim()
  if (/<html[\s>]/i.test(body)) return body
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
${CW_BRIDGE}
${HEAD_LIBS}
<style>${DESIGN_SYSTEM}</style>
</head>
<body>
${body}
${BOOT}
</body>
</html>`
}

/** 生成 Blob URL（调用方负责在组件卸载时 revokeObjectURL）。 */
export function createIframeBlob(fragment: string): string {
  const html = wrapInteractiveHtml(fragment)
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  return URL.createObjectURL(blob)
}
