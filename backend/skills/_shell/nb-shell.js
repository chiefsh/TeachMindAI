/* NB 外壳：统一顶栏（简介 / 画笔 / 重置 / 全屏）+ 场景协议。
 * 宿主页 iframe 通过 postMessage 调用：
 *   → {nb:"call", id, method, args}
 *   ← {nb:"reply", id, result} | {nb:"reply", id, error}
 *   ← {nb:"event", type:"onload"|"onChange", data}
 * method: config / getData / setData / reset / info
 * 页面引擎用 NB.register({getData, setData, reset, info}) 接入；没接入的页面只有外壳。 */
(function () {
  if (window.NB && window.NB.__shell) return;
  var CFG = window.__NB_CFG__ || {};
  var adapter = null;
  var loaded = false;
  var pendingScene = CFG.scene || null;
  var ui = {};
  var penOn = false, penColor = "#e11d48", strokes = [], cur = null;

  function emit(type, data) {
    try { window.parent && window.parent !== window && window.parent.postMessage({ nb: "event", type: type, data: data || {} }, "*"); } catch (e) {}
  }

  function applyScene() {
    if (!adapter || !pendingScene || !adapter.setData) return;
    var s = pendingScene;
    pendingScene = null;
    try { adapter.setData(s); } catch (e) { console.warn("NB setData", e); }
  }

  var NB = {
    __shell: true,
    register: function (a) {
      adapter = a || null;
      applyScene();
      if (ui.reset) ui.reset.style.display = adapter && adapter.reset ? "" : "none";
      if (loaded) emit("onload", status());
    },
    emit: emit,
    changed: function () { emit("onChange", {}); },
    config: config,
  };
  window.NB = NB;

  function status() {
    return { sceneEditable: !!(adapter && adapter.getData && adapter.setData), title: CFG.title || "" };
  }

  function config(opts) {
    opts = opts || {};
    if (opts.titleVisible === false || opts.toolbarVisible === false) document.documentElement.classList.remove("nb-chrome");
    if (opts.titleVisible === true || opts.toolbarVisible === true) document.documentElement.classList.add("nb-chrome");
    if (adapter && adapter.config) adapter.config(opts);
    return status();
  }

  var METHODS = {
    config: config,
    getData: function () { return adapter && adapter.getData ? adapter.getData() : null; },
    setData: function (d) {
      if (typeof d === "string") { try { d = JSON.parse(d); } catch (e) { throw new Error("场景数据不是合法 JSON"); } }
      if (!adapter || !adapter.setData) { pendingScene = d; return false; }
      adapter.setData(d);
      return true;
    },
    reset: function () { if (adapter && adapter.reset) adapter.reset(); return true; },
    info: function () { return mergedInfo(); },
    status: status,
  };

  window.addEventListener("message", function (ev) {
    var m = ev.data;
    if (!m || m.nb !== "call" || !METHODS[m.method]) return;
    var reply = { nb: "reply", id: m.id };
    try { reply.result = METHODS[m.method](m.args); } catch (e) { reply.error = String(e && e.message || e); }
    try { ev.source && ev.source.postMessage(reply, "*"); } catch (e) {}
  });

  /* ── 简介 ─────────────────────────────── */
  function mergedInfo() {
    var a = adapter && adapter.info ? (adapter.info() || {}) : {};
    var c = CFG.info || {};
    var out = {};
    ["purpose", "apparatus", "steps", "discussion", "tags"].forEach(function (k) {
      out[k] = a[k] != null && (a[k].length || typeof a[k] === "string") ? a[k] : c[k];
    });
    return out;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch];
    });
  }
  function list(items, ordered) {
    if (!items || !items.length) return "";
    if (typeof items === "string") return "<p>" + esc(items) + "</p>";
    var tag = ordered ? "ol" : "ul";
    return "<" + tag + ">" + items.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</" + tag + ">";
  }
  function renderInfo() {
    var i = mergedInfo();
    var h = '<button class="nb-btn nb-close" type="button" aria-label="关闭">✕</button><h3>' + esc(CFG.title || document.title) + "</h3>";
    if (i.purpose) h += "<h4>实验目的</h4>" + list(i.purpose);
    if (i.apparatus && i.apparatus.length) h += "<h4>实验器材</h4>" + list(i.apparatus);
    if (i.steps && i.steps.length) h += "<h4>实验步骤</h4>" + list(i.steps, true);
    if (i.discussion && i.discussion.length) h += "<h4>讨论</h4>" + list(i.discussion);
    if (i.tags && i.tags.length) {
      h += '<h4>关联知识点</h4><div class="nb-tags">' + i.tags.map(function (t) { return "<span>" + esc(t) + "</span>"; }).join("") + "</div>";
    }
    ui.drawer.innerHTML = h;
    ui.drawer.querySelector(".nb-close").onclick = function () { toggleInfo(false); };
  }
  function toggleInfo(on) {
    var show = on == null ? !ui.drawer.classList.contains("show") : on;
    if (show) renderInfo();
    ui.drawer.classList.toggle("show", show);
    ui.info.classList.toggle("on", show);
  }

  /* ── 画笔批注 ──────────────────────────── */
  function sizeInk() {
    var c = ui.ink, r = c.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    c.width = Math.max(1, Math.round(r.width * dpr));
    c.height = Math.max(1, Math.round(r.height * dpr));
    drawInk();
  }
  function drawInk() {
    var c = ui.ink, g = c.getContext("2d"), dpr = window.devicePixelRatio || 1;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, c.width, c.height);
    g.lineCap = "round"; g.lineJoin = "round";
    strokes.forEach(function (s) {
      g.strokeStyle = s.c; g.lineWidth = 3.2;
      g.beginPath();
      s.p.forEach(function (p, k) { k ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]); });
      g.stroke();
    });
  }
  function inkPt(ev) {
    var r = ui.ink.getBoundingClientRect();
    return [ev.clientX - r.left, ev.clientY - r.top];
  }
  function setPen(on) {
    penOn = on;
    ui.ink.classList.toggle("active", on);
    ui.pen.classList.toggle("on", on);
    ui.pens.classList.toggle("show", on);
  }

  /* ── 构建 ─────────────────────────────── */
  var ICON = {
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/></svg>',
    pen: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20l4-1 11-11-3-3L5 16l-1 4z"/></svg>',
    clear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/></svg>',
    reset: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12a8 8 0 1 0 3-6.2M4 4v5h5"/></svg>',
    full: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>',
  };
  function btn(id, icon, label) {
    return '<button class="nb-btn" type="button" id="nb-' + id + '">' + ICON[icon] + '<span class="nb-lbl">' + label + "</span></button>";
  }

  function build() {
    var root = document.documentElement;
    if (CFG.chrome !== false) root.classList.add("nb-chrome");
    var bar = document.createElement("div");
    bar.className = "nb-bar";
    var colors = ["#e11d48", "#2563eb", "#16a34a", "#111827"];
    bar.innerHTML =
      (CFG.subject ? '<span class="nb-subj">' + esc(CFG.subject) + (CFG.group ? " · " + esc(CFG.group) : "") + "</span>" : "") +
      '<span class="nb-title">' + esc(CFG.title || document.title || "") + "</span>" +
      '<div class="nb-tools">' +
      btn("info", "info", "简介") + '<span class="nb-sep"></span>' +
      btn("pen", "pen", "画笔") +
      '<span class="nb-pens" id="nb-pens">' +
      colors.map(function (c, k) { return '<button type="button" class="nb-swatch' + (k ? "" : " on") + '" data-c="' + c + '" style="background:' + c + '"></button>'; }).join("") +
      btn("clear", "clear", "清除") + "</span>" +
      btn("reset", "reset", "重置") + btn("full", "full", "全屏") + "</div>";
    root.appendChild(bar);

    var ink = document.createElement("canvas");
    ink.className = "nb-ink";
    root.appendChild(ink);
    var drawer = document.createElement("div");
    drawer.className = "nb-drawer";
    root.appendChild(drawer);

    ui = {
      bar: bar, ink: ink, drawer: drawer,
      info: bar.querySelector("#nb-info"), pen: bar.querySelector("#nb-pen"),
      pens: bar.querySelector("#nb-pens"), reset: bar.querySelector("#nb-reset"),
    };
    ui.reset.style.display = adapter && adapter.reset ? "" : "none";
    ui.info.onclick = function () { toggleInfo(); };
    ui.pen.onclick = function () { setPen(!penOn); };
    bar.querySelector("#nb-clear").onclick = function () { strokes = []; drawInk(); };
    Array.prototype.forEach.call(bar.querySelectorAll(".nb-swatch"), function (s) {
      s.onclick = function () {
        penColor = s.getAttribute("data-c");
        Array.prototype.forEach.call(bar.querySelectorAll(".nb-swatch"), function (o) { o.classList.toggle("on", o === s); });
      };
    });
    ui.reset.onclick = function () { METHODS.reset(); };
    bar.querySelector("#nb-full").onclick = function () {
      var d = document;
      if (d.fullscreenElement || d.webkitFullscreenElement) (d.exitFullscreen || d.webkitExitFullscreen).call(d);
      else {
        var req = root.requestFullscreen || root.webkitRequestFullscreen;
        if (req) try { req.call(root); } catch (e) {}
      }
    };

    ink.addEventListener("pointerdown", function (ev) {
      if (!penOn) return;
      cur = { c: penColor, p: [inkPt(ev)] };
      strokes.push(cur);
      try { ink.setPointerCapture(ev.pointerId); } catch (e) {}
      ev.preventDefault();
    });
    ink.addEventListener("pointermove", function (ev) {
      if (!cur) return;
      cur.p.push(inkPt(ev));
      drawInk();
    });
    ink.addEventListener("pointerup", function () { cur = null; });
    ink.addEventListener("pointercancel", function () { cur = null; });
    window.addEventListener("resize", sizeInk);
    sizeInk();
    window.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && penOn) setPen(false);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
  window.addEventListener("load", function () {
    loaded = true;
    applyScene();
    emit("onload", status());
    window.dispatchEvent(new Event("resize"));
  });
})();
