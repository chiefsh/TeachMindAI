import{g as d}from"./coursewareTheme-5VUv4MBp.js";function p(e){return`
:root{
  --c-primary:${e.primary}; --c-accent:${e.accent}; --c-ok:#16a34a; --c-bad:#dc2626;
  --c-line:${e.surface}; --c-bg:${e.bg}; --c-text:${e.text}; --c-muted:${e.muted};
  --c-card:${e.card}; --shadow:${e.shadowSoft};
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
`}const a="0.16.11",m="4.4.4",f=`
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@${a}/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@${a}/dist/katex.min.js"><\/script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@${a}/dist/contrib/auto-render.min.js"><\/script>
`,u=`
<script defer src="https://cdn.jsdelivr.net/npm/chart.js@${m}/dist/chart.umd.min.js"><\/script>
`;function o(e){return/\$\$|\\\(|\\\[|katex|mathjax/i.test(e)}function b(e){return/chart\.js|new\s+Chart\b|window\.Chart|canvas/i.test(e)}const i=`
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
`,x=`
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
`;function g(e){const r=e||"";return/<html[\s>]/i.test(r)||/id=["']lab-data["']/.test(r)}const k=`
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
`,E=`
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
`,c=`
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
<\/script>
`,h=`
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
`;function y(e){const t=`${/id=["']lab-data["']/.test(e)?h:""}${i}${c}`;return/<\/body>/i.test(e)?e.replace(/<\/body>/i,t+"</body>"):e+t}function w(e,r){const t=(e||"").trim();if(/<html[\s>]/i.test(t))return y(t);const n=typeof r=="string"||!r?d(r):r,s=[o(t)?f:"",b(t)?u:""].join(""),l=o(t)?x:"";return`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
${i}
${s}
<style>${p(n)}</style>
</head>
<body>
${t}
${l}
${c}
</body>
</html>`}function L(e,r){const t=w(e,r),n=new Blob([t],{type:"text/html;charset=utf-8"});return URL.createObjectURL(n)}export{k as I,E as a,L as c,g as i,w};
