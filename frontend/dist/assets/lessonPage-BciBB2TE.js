import{i as Z,I as B,a as P,w as R}from"./coursewareFrame-BcOnFOM2.js";import{t as J,c as j,g as _}from"./coursewareTheme-5VUv4MBp.js";import{r as Q}from"./markdown-7Vi8ptUE.js";const U=["He","Li","Be","Ne","Na","Mg","Al","Si","Cl","Ar","Ca","Sc","Ti","Cr","Mn","Fe","Ni","Cu","Zn","Ga","Ge","As","Se","Br","Kr","Rb","Sr","Zr","Nb","Mo","Ag","Cd","In","Sn","Sb","Te","Xe","Cs","Ba","La","Hf","Ta","Pt","Au","Hg","Pb","Bi","Rn","Co","No","H","B","C","N","O","F","P","S","K","V","Y","I","W","U"],W=new Set(U),ee=U.filter(e=>e.length===2),S={0:"₀",1:"₁",2:"₂",3:"₃",4:"₄",5:"₅",6:"₆",7:"₇",8:"₈",9:"₉"},C={0:"⁰",1:"¹",2:"²",3:"³",4:"⁴",5:"⁵",6:"⁶",7:"⁷",8:"⁸",9:"⁹","+":"⁺","-":"⁻","−":"⁻"},b={};for(const[e,t]of Object.entries(S))b[t]=e;function y(e){return e>="0"&&e<="9"||e in b}function E(e){return b[e]||e}function te(e,t){for(const r of[2,1]){const i=e.slice(t,t+r);if(i.length<r||!/^[A-Za-z]+$/.test(i))continue;const n=i[0].toUpperCase()+i.slice(1).toLowerCase();if(W.has(n)&&!((n==="Co"||n==="No")&&t+r<e.length&&y(e[t+r])))return[n,t+r]}return null}function D(e,t){let r="",i=t,n=0,a=!1;for(;i<e.length;){const o=e[i];if(o==="("||o==="["){const d=o==="("?")":"]",m=D(e,i+1);if(!m)break;let p=m[1];if(e[p]!==d)break;p+=1;let h="";for(;p<e.length&&y(e[p]);)h+=E(e[p]),p+=1;h&&(a=!0),r+=o+m[0]+d+h.split("").map(x=>S[x]||x).join(""),n+=1,i=p;continue}const s=te(e,i);if(!s)break;let l=s[1],g="";for(;l<e.length&&y(e[l]);)g+=E(e[l]),l+=1;g&&(a=!0),r+=s[0]+g.split("").map(d=>S[d]||d).join(""),n+=1,i=l}return!r||i===t||!(a||n>=2||r.length>=2&&ee.includes(r.slice(0,2))&&n===1)?null:[r,i,a||n>=2]}function re(e,t){const r=e.slice(t).match(/^\s*[\(（]\s*(s|l|g|aq|固|液|气)\s*[\)）]/i);return r?t+r[0].length:t}function ie(e,t){return e[t]==="↑"||e[t]==="↓"?[e[t],t+1]:["",t]}function ne(e){let t="";for(;e&&e[e.length-1]in b;)t=b[e[e.length-1]]+t,e=e.slice(0,-1);return[e,t]}function M(e,t){if(e.slice(t,t+2).toLowerCase()==="ph"&&(t+2>=e.length||!y(e[t+2])))return null;const r=D(e,t);if(!r)return null;let[i,n]=r;const a=ie(e,n);if(i+=a[0],n=a[1],n<e.length&&"+-−^".includes(e[n]))if(e[n]==="^"){let c=n+1,o="",s="";for(;c<e.length&&(y(e[c])||"+-−".includes(e[c]));)"+-−".includes(e[c])?o=e[c]==="+"?"+":"-":s+=E(e[c]),c+=1;o&&(i+=(s+o).split("").map(l=>C[l]||l).join(""),n=c)}else{let c=n+1;for(;c<e.length&&e[c]===" ";)c+=1;if(!M(e,c)){const o=e[n]==="+"?"+":"-",s=ne(i);i=s[0]+(s[1]+o).split("").map(l=>C[l]||l).join(""),n+=1}}return n=re(e,n),[i,n]}function ce(e,t){const r=M(e,t);if(!r)return null;const i=[r[0]];let n=r[1];for(;n<e.length;){let a=n;for(;a<e.length&&e[a]===" ";)a+=1;const c=e[a];if(c!=="+"&&c!=="·"&&c!=="•"&&c!=="＝"&&c!=="="&&c!=="→"&&c!=="⇌"&&c!=="↔")break;const o=c==="＝"?"=":c;let s=a+1;for(;s<e.length&&e[s]===" ";)s+=1;const l=M(e,s);if(!l)break;i.push(` ${o} ${l[0]}`),n=l[1]}return[i.join(""),n]}function K(e){const t=String(e||"");if(!t)return"";let r="",i=0;for(;i<t.length;){if(t[i]==="$"){const c=t[i+1]==="$"?"$$":"$",o=t.indexOf(c,i+c.length);if(o!==-1){r+=t.slice(i,o+c.length),i=o+c.length;continue}}const n=ce(t,i);if(n&&n[1]>i){r+=n[0],i=n[1];continue}r+=t[i],i+=1}return r}const T={cover:"封面",objectives:"学习目标",knowledge:"新知讲解",example:"例题精讲",interactive:"互动探究",comparison:"对比辨析",process:"过程路径",summary:"课堂小结",exercise:"随堂练习",homework:"课后作业",title:"封面",content:"新知讲解",intro:"情境导入",activity:"课堂活动",board:"板书设计",quiz:"随堂测验"},ae={title:"cover",content:"knowledge",intro:"process",activity:"interactive",quiz:"exercise",board:"summary"},oe=["cover","objectives","knowledge","example","interactive","comparison","process","summary","exercise","homework"],se=oe;function z(e){const t=(e||"knowledge").trim(),r=ae[t]||t;return se.includes(r)?r:"knowledge"}function F(e){return T[e||""]||T[z(e)]||"内容"}function G(e){return z(e==null?void 0:e.type)!=="objectives"}function v(e){return(e||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}function f(e){return v(K(e))}function H(e){return v(e).replace(/"/g,"&quot;")}function le(e){const t=e||"";return/数学|算术/.test(t)?"math":/语文|作文|阅读|文学/.test(t)?"chinese":/英语|英文/.test(t)?"english":/物理/.test(t)?"physics":/化学/.test(t)?"chem":/生物/.test(t)?"bio":/历史/.test(t)?"history":/地理/.test(t)?"geo":"generic"}function de(e,t){const r=t,i={math:`<circle cx="16" cy="16" r="11" fill="none" stroke="${r}" stroke-width="1.6"/>
      <path d="M16 5v22M5 16h22" stroke="${r}" stroke-width="1.2"/>
      <path d="M8 24l16-16" stroke="${r}" stroke-width="1.2"/>`,chinese:`<path d="M8 7h16v18H8z" fill="none" stroke="${r}" stroke-width="1.6"/>
      <path d="M11 12h10M11 16h10M11 20h7" stroke="${r}" stroke-width="1.3"/>`,english:`<text x="16" y="21" text-anchor="middle" font-size="14" font-weight="700" fill="${r}" font-family="serif">Aa</text>`,physics:`<circle cx="16" cy="16" r="3" fill="${r}"/>
      <ellipse cx="16" cy="16" rx="12" ry="5" fill="none" stroke="${r}" stroke-width="1.3" transform="rotate(30 16 16)"/>
      <ellipse cx="16" cy="16" rx="12" ry="5" fill="none" stroke="${r}" stroke-width="1.3" transform="rotate(-30 16 16)"/>`,chem:`<path d="M12 6h8v6l5 12H7l5-12z" fill="none" stroke="${r}" stroke-width="1.6"/>
      <circle cx="16" cy="20" r="2.2" fill="${r}"/>`,bio:`<path d="M16 28c0-12 10-12 10-20-8 0-10 8-10 8S14 8 6 8c0 8 10 8 10 20z" fill="none" stroke="${r}" stroke-width="1.5"/>
      <path d="M16 14v14" stroke="${r}" stroke-width="1.3"/>`,history:`<path d="M8 8h16v4H8zm2 4v12m12-12v12M8 24h16" fill="none" stroke="${r}" stroke-width="1.5"/>`,geo:`<circle cx="16" cy="16" r="11" fill="none" stroke="${r}" stroke-width="1.6"/>
      <ellipse cx="16" cy="16" rx="5" ry="11" fill="none" stroke="${r}" stroke-width="1.2"/>
      <path d="M5 16h22" stroke="${r}" stroke-width="1.2"/>`,generic:`<path d="M16 5l3 8h8l-6.5 5 2.5 8L16 21l-7 5 2.5-8L5 13h8z" fill="none" stroke="${r}" stroke-width="1.4"/>`};return`<svg class="cw-subject" viewBox="0 0 32 32" width="32" height="32" aria-hidden="true">${i[e]||i.generic}</svg>`}function V(e){const t=e.primary,r=e.accent,i=e.decoStyle;let n="";return i==="circles"?n=`<circle cx="1180" cy="70" r="200" fill="${t}" opacity=".10"/>
      <circle cx="80" cy="680" r="160" fill="${r}" opacity=".12"/>
      <circle cx="1080" cy="620" r="70" fill="${t}" opacity=".14"/>
      <circle cx="200" cy="80" r="36" fill="${r}" opacity=".16"/>`:i==="leaves"?n=`<ellipse cx="1220" cy="80" rx="180" ry="90" fill="${t}" opacity=".10" transform="rotate(24 1220 80)"/>
      <ellipse cx="60" cy="640" rx="160" ry="70" fill="${r}" opacity=".12" transform="rotate(-18 60 640)"/>
      <ellipse cx="1100" cy="560" rx="80" ry="36" fill="${t}" opacity=".12" transform="rotate(40 1100 560)"/>`:i==="grid"?n=`<defs><pattern id="cwg" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M40 0H0v40" fill="none" stroke="${t}" stroke-width="1" opacity=".18"/></pattern></defs>
      <rect width="1280" height="720" fill="url(#cwg)"/>
      <circle cx="1200" cy="80" r="90" fill="${r}" opacity=".10"/>`:i==="waves"?n=`<path d="M0 560 Q160 500 320 560 T640 560 T960 560 T1280 560 V720 H0z" fill="${t}" opacity=".10"/>
      <path d="M0 600 Q160 660 320 600 T640 600 T960 600 T1280 600 V720 H0z" fill="${r}" opacity=".10"/>`:i==="dots"?n=`<defs><pattern id="cwd" width="22" height="22" patternUnits="userSpaceOnUse">
        <circle cx="3" cy="3" r="1.6" fill="${t}" opacity=".28"/></pattern></defs>
      <rect width="1280" height="720" fill="url(#cwd)"/>
      <rect x="1040" y="0" width="240" height="720" fill="${t}" opacity=".06"/>`:n=`<defs><pattern id="cwl" width="28" height="28" patternUnits="userSpaceOnUse" patternTransform="rotate(32)">
        <line x1="0" y1="0" x2="0" y2="28" stroke="${t}" stroke-width="2" opacity=".10"/></pattern></defs>
      <rect width="1280" height="720" fill="url(#cwl)"/>
      <rect x="0" y="0" width="10" height="720" fill="${t}"/>`,`<div class="cw-deco" aria-hidden="true"><svg viewBox="0 0 1280 720" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">${n}</svg></div>`}function q(e,t){const r=t==="deck";return`
:root{${J(e)}}
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
.cw-cover--diagonal{background:${j(e)};color:var(--c-on-cover);text-align:center;align-items:center;justify-content:center}
.cw-cover--diagonal .cw-kicker,.cw-cover--split .cw-cover-panel .cw-kicker,.cw-ribbon .cw-kicker{background:rgba(255,255,255,.18);color:#fff}
.cw-cover--diagonal .cw-chip,.cw-cover--split .cw-cover-panel .cw-chip{background:rgba(255,255,255,.18);color:#fff}
.cw-cover--split{background:var(--c-bg);color:var(--c-text)}
.cw-cover--split .cw-inner{display:grid;grid-template-columns:42% 1fr;padding:0;min-height:100%}
.cw-cover-panel{background:${j(e)};color:var(--c-on-cover);display:flex;flex-direction:column;justify-content:center;padding:8%}
.cw-cover-side{display:flex;flex-direction:column;justify-content:center;padding:8%;gap:12px}
.cw-cover--ribbon{background:var(--c-bg);color:var(--c-text);flex-direction:column;justify-content:center}
.cw-ribbon{background:${j(e)};color:var(--c-on-cover);padding:6% 8%;box-shadow:var(--shadow)}
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
.cw-imgs img{max-height:${r?"32vh":"320px"};border-radius:12px;background:var(--c-surface);object-fit:contain;box-shadow:var(--shadow-soft)}
.cw-iframe{width:100%;border:0;display:block;background:var(--c-card);height:${r?"52vh":"520px"}}
.cw-iframe--app{height:${r?"78vh":"760px"};min-height:620px}
.cw-notes{margin-top:12px}
.body h3,.body h4,.body h5{color:var(--c-primary);margin:.7em 0 .25em}
.body p{margin:.4em 0}
.body code{background:var(--c-surface);color:#be185d;padding:.05em .3em;border-radius:4px}
${r?`
.cw-kicker{font-size:.42em}
.cw-label{font-size:.42em;margin-bottom:.35em}
.cw-cover h1{font-size:2em}
.cw-cover .sub{font-size:.9em}
.cw-page h2{font-size:1.25em;margin:.2em 0 .15em}
.cw-inner{font-size:.78em;line-height:1.45}
`:`
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
`}function A(e){return((e==null?void 0:e.bullets)||[]).map(t=>String(t||"").trim()).filter(Boolean)}function pe(e){return Array.isArray(e==null?void 0:e.steps)&&e.steps.length?e.steps.map(t=>({title:String(t.title||t.name||"").trim(),detail:String(t.detail||t.content||"").trim()})).filter(t=>t.title||t.detail):A(e).map(t=>({title:t,detail:""}))}function ge(e){if(Array.isArray(e==null?void 0:e.columns)&&e.columns.length>=2)return e.columns.slice(0,2).map(i=>({title:String(i.title||"").trim()||"对照",items:(i.items||i.bullets||[]).map(n=>String(n||"").trim()).filter(Boolean)}));const t=A(e),r=Math.max(1,Math.ceil(t.length/2));return[{title:e.left_title||"对照 A",items:t.slice(0,r)},{title:e.right_title||"对照 B",items:t.slice(r)}]}function u(e,t){const r=t?`第 ${t} 页 · `:"";return`<span class="cw-kicker">${f(r+e)}</span>`}function w(e){const t=e.title?`<h2>${f(e.title)}</h2>`:"",r=e.subtitle?`<p class="sub" style="color:var(--c-muted);margin:.15em 0 .4em">${f(e.subtitle)}</p>`:"";return t+r}function $(e){return e.length?`<ul class="cw-points">${e.map(t=>`<li><span>${f(t)}</span></li>`).join("")}</ul>`:""}function me(e){return e?`<div class="body">${e}</div>`:""}function fe(e,t,r){const i=f(e.title||"教学课件"),n=e.subtitle?`<p class="sub">${f(e.subtitle)}</p>`:"",a=t.coverStyle,c=a==="diagonal"?t.onCover:t.primary,o=r.subject?`<div class="cw-chip">${de(le(r.subject),c)}${v(r.subject)}</div>`:"",s=r.chapter?`<span class="cw-kicker">${v(r.chapter)}</span>`:"";return a==="split"?`<div class="cw-cover-panel"><div>${s}</div><h1>${i}</h1>${n}</div>
      <div class="cw-cover-side">${o}</div>`:a==="ribbon"?`${o}<div class="cw-ribbon"><div>${s}</div><h1>${i}</h1>${n}</div>`:a==="panel"?`<div class="cw-cover-card">${s}<h1 style="margin-top:.4em">${i}</h1>${n}${o}</div>`:a==="lab"?`<div class="cw-lab-bar"></div>${s}<h1>${i}</h1>${n}${o}`:a==="minimal"?`${s}<h1 style="margin-top:.6em">${i}</h1>${n}${o}`:`${o}<div style="margin-top:12px">${s}</div><h1>${i}</h1>${n}`}function he(e,t,r,i,n){const a=F(t.type),c=me(r.mdHtml),o=r.imagesHtml,s=r.iframeHtml,l=r.notesHtml,g=A(t);if(e==="cover")return fe(t,n,i)+l;if(e==="objectives"){const d=(g.length?g:[t.content||"完成本课学习目标"]).slice(0,6);return`${u(a,i.index)}${w(t)}
      <div class="cw-goals">${d.map((m,p)=>`<div class="cw-goal"><span class="cw-goal-n">${String(p+1).padStart(2,"0")}</span><div>${f(m)}</div></div>`).join("")}</div>${c}${o}${l}`}if(e==="knowledge")return`${u(a,i.index)}${w(t)}
      <div class="cw-knowledge"><div class="cw-knowledge-bar"></div>
      <div>${$(g)}${c}${o}</div></div>${l}`;if(e==="example"){const d=t.prompt||(g.length?g.join("；"):t.title||"例题"),m=String(t.solution||"").trim(),p=m?f(m):r.mdHtml,h=p?`<details class="cw-reveal"><summary>想好后再看解析</summary><div class="body">${p}</div></details>`:"";return`${u(a,i.index)}${w(t)}
      <div class="cw-example">
        <div class="cw-example-q"><h3>题干</h3><div>${f(String(d))}</div></div>
        ${h}
      </div>${o}${l}`}if(e==="interactive")return`${u(a,i.index)}${w(t)}${$(g)}${c}${s}${o}${l}`;if(e==="comparison"){const d=ge(t);return`${u(a,i.index)}${w(t)}
      <div class="cw-compare">${d.map((m,p)=>`<div class="cw-compare-col ${p?"b":"a"}"><h3>${f(m.title)}</h3>${$(m.items)}</div>`).join("")}</div>${c}${o}${l}`}if(e==="process"){const d=pe(t);return`${u(a,i.index)}${w(t)}
      <div class="cw-steps">${d.map((m,p)=>`
        <div class="cw-step">
          <div class="cw-step-rail"><span class="cw-step-n">${p+1}</span>${p<d.length-1?'<span class="cw-step-line"></span>':""}</div>
          <div class="cw-step-body"><strong>${f(m.title)}</strong>${m.detail?`<div class="body">${f(m.detail)}</div>`:""}</div>
        </div>`).join("")}</div>${c}${o}${l}`}if(e==="summary")return`${u(a,i.index)}${w(t)}
      <div class="cw-block-accent cw-summary-hero">今天带走这几件事</div>
      <div class="cw-summary-grid">${g.map(d=>`<div class="cw-block">${f(d)}</div>`).join("")}</div>
      ${c}${o}${l}`;if(e==="exercise"){const d=g.length?g:t.content?[t.content]:["完成本页练习"];return`${u(a,i.index)}${w(t)}
      <div class="cw-exercise">${d.map((m,p)=>`<div class="cw-ex"><span class="cw-ex-n">${p+1}</span><div>${f(m)}</div></div>`).join("")}</div>${c}${o}${s}${l}`}if(e==="homework"){const d=g.length?g:["完成课后巩固练习"];return`${u(a,i.index)}${w(t)}
      <div class="cw-block-accent">分层任务：基础巩固 + 生活迁移 + 小作品</div>
      <div class="cw-hw">${d.map(m=>`<div class="cw-hw-item"><span class="cw-hw-box"></span><div>${f(m)}</div></div>`).join("")}</div>${c}${o}${l}`}return`${u(a,i.index)}${w(t)}${$(g)}${c}${o}${s}${l}`}function Y(e,t,r,i){const n=z(e==null?void 0:e.type),a=n==="cover"?`cw-cover cw-cover--${t.coverStyle}`:`cw-page--${n}`;return{kind:n,className:a,inner:`<div class="cw-inner">${he(n,e,r,i,t)}</div>`}}function X(e,t,r){const i=(e.images||[]).map(s=>t[String(s)]).filter(Boolean),n=i.length?`<div class="cw-imgs">${i.map(s=>`<img src="${H(s)}" alt="" />`).join("")}</div>`:"";let a="";if(e.html&&r.wrapHtml){const s=Z(e.html);a=`<div class="cw-fs-box">
      <div class="cw-fs-bar"><span>${s?"实验台":"互动动画"}</span><button type="button" class="cw-fs-btn" aria-pressed="false">全屏</button></div>
      <div class="cw-fs-stage">
        <iframe class="cw-iframe${s?" cw-iframe--app":""}" allow="fullscreen *" allowfullscreen sandbox="allow-scripts allow-popups allow-modals" srcdoc="${H(r.wrapHtml(e.html))}"></iframe>
      </div>
    </div>`}let c="";e.notes&&r.notesMode==="aside"?c=`<aside class="notes">${f(e.notes)}</aside>`:e.notes&&r.notesMode==="details"&&(c=`<details class="cw-notes cw-block"><summary>教师讲稿 / 备注</summary><p>${f(e.notes)}</p></details>`);const o=e.content?Q(K(e.content)):"";return{imagesHtml:n,iframeHtml:a,notesHtml:c,mdHtml:o}}const k="5.1.0",I="0.16.11",ue=e=>`
${q(e,"deck")}
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
`;function N(e,t,r,i){const n=X(e,t,{wrapHtml:c=>R(c,r),notesMode:"aside"}),a=Y(e,r,n,{index:i.index,subject:i.subject});return`<section class="cw-page ${a.className}">${V(r)}${a.inner}</section>`}function $e(e,t={},r={}){const i=(e==null?void 0:e.meta)||{},n=(e==null?void 0:e.slides)||[],a=_(r.theme),c=r.subject||i.subject||"",o=[];return n.some(l=>l.type==="title"||l.type==="cover")||o.push(N({type:"cover",title:i.title||"课堂课件",subtitle:i.duration||""},{},a,{index:0,subject:c})),n.forEach((l,g)=>{G(l)&&o.push(N(l,t,a,{index:g+1,subject:c}))}),`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${v(i.title||"课堂课件")}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@${k}/dist/reveal.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@${k}/dist/theme/white.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@${I}/dist/katex.min.css">
<style>${ue(a)}</style>
</head>
<body>
<div class="reveal"><div class="slides">
${o.join(`
`)}
</div></div>
<script src="https://cdn.jsdelivr.net/npm/reveal.js@${k}/dist/reveal.js"><\/script>
<script src="https://cdn.jsdelivr.net/npm/reveal.js@${k}/plugin/notes/notes.js"><\/script>
<script src="https://cdn.jsdelivr.net/npm/katex@${I}/dist/contrib/auto-render.min.js"><\/script>
<script>
  var PRINT_MODE = ${r.print?"true":"false"};
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
<\/script>
<script>${B}<\/script>
<script>${P}<\/script>
</body>
</html>`}const O="0.16.11",we=e=>`
${q(e,"page")}
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
footer{text-align:center;color:var(--c-muted);font-size:13px;padding:0 20px 40px}
@media (max-width:900px){
  .layout{flex-direction:column;padding:20px 14px 60px}
  .toc{position:static;width:100%;max-height:none}
  .cw-page.sec .cw-inner{padding:20px 18px}
}
@media print{
  .toc{display:none}
  .cw-page{box-shadow:none;break-inside:avoid}
}
`,ve=`
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
`+B;function L(e,t,r,i,n){const a=X(e,r,{wrapHtml:o=>R(o,i),notesMode:"none"}),c=Y(e,i,a,{index:t+1,subject:n});return`<section class="cw-page sec ${c.className}" id="sec-${t}">${V(i)}${c.inner}</section>`}function ke(e,t={},r={}){const i=(e==null?void 0:e.meta)||{},n=(e==null?void 0:e.slides)||[],a=i.title||"课堂课件",c=_(r.theme),o=r.subject||i.subject||"",s=n.find(h=>h.type==="title"||h.type==="cover"),l=n.filter(h=>h!==s&&G(h)),g={type:"cover",title:(s==null?void 0:s.title)||a,subtitle:(s==null?void 0:s.subtitle)||r.subtitle||i.duration||""},d=L({...g,type:g.type},-1,{},c,o).replace('id="sec--1"','id="sec-cover"'),m=l.map((h,x)=>L(h,x,t,c,o)).join(`
`),p=['<a href="#sec-cover">封面</a>'];return l.forEach((h,x)=>{p.push(`<a href="#sec-${x}">${v(h.title||F(h.type))}</a>`)}),`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${v(a)}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@${O}/dist/katex.min.css">
<style>${we(c)}</style>
</head>
<body>
${d}
<div class="layout">
  <nav class="toc"><h2>目录</h2>${p.join("")}</nav>
  <main>
${m}
  </main>
</div>
<footer>本网页课件由知序台生成，可离线保存与分享</footer>
<script src="https://cdn.jsdelivr.net/npm/katex@${O}/dist/contrib/auto-render.min.js"><\/script>
<script>${ve}<\/script>
<script>${P}<\/script>
</body>
</html>`}export{oe as P,$e as a,ke as b,z as c,K as n,F as p};
