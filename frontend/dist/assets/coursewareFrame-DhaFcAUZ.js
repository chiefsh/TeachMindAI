import{g as c}from"./coursewareTheme-5VUv4MBp.js";function d(r){return`
:root{
  --c-primary:${r.primary}; --c-accent:${r.accent}; --c-ok:#16a34a; --c-bad:#dc2626;
  --c-line:${r.surface}; --c-bg:${r.bg}; --c-text:${r.text}; --c-muted:${r.muted};
  --c-card:${r.card}; --shadow:${r.shadowSoft};
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
`}const n="0.16.11",p="4.4.4",l=`
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@${n}/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@${n}/dist/katex.min.js"><\/script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@${n}/dist/contrib/auto-render.min.js"><\/script>
`,f=`
<script defer src="https://cdn.jsdelivr.net/npm/chart.js@${p}/dist/chart.umd.min.js"><\/script>
`;function o(r){return/\$\$|\\\(|\\\[|katex|mathjax/i.test(r)}function m(r){return/chart\.js|new\s+Chart\b|window\.Chart|canvas/i.test(r)}const b=`
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
<\/script>
`,u=`
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
<\/script>
`;function g(r,e){const t=(r||"").trim();if(/<html[\s>]/i.test(t))return t;const a=typeof e=="string"||!e?c(e):e,i=[o(t)?l:"",m(t)?f:""].join(""),s=o(t)?u:"";return`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
${b}
${i}
<style>${d(a)}</style>
</head>
<body>
${t}
${s}
</body>
</html>`}function h(r,e){const t=g(r,e),a=new Blob([t],{type:"text/html;charset=utf-8"});return URL.createObjectURL(a)}export{h as c,g as w};
