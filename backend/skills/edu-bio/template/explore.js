(function () {
  var DATA = JSON.parse(document.getElementById("bio-data").textContent);
  var seen = {};
  var phaseIndex = 0;
  var toastTimer = 0;
  var playing = true;
  var elapsed = 0;
  var lastTs = 0;
  var userHoldPhase = false;
  var pathCache = {};

  function $(id) { return document.getElementById(id); }

  function report(ok, q, a) {
    try {
      if (ok) window.CW && window.CW.correct && window.CW.correct(q, a);
      else window.CW && window.CW.wrong && window.CW.wrong(q, a);
    } catch (e) {}
  }

  function toast(msg, bad) {
    var el = $("toast");
    el.textContent = msg;
    el.className = "toast " + (bad ? "bad" : "ok");
    el.style.display = "block";
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.style.display = "none"; }, 2200);
  }

  function partMeta(id) {
    var parts = DATA.parts || [];
    for (var i = 0; i < parts.length; i++) if (parts[i].id === id) return parts[i];
    return null;
  }

  function setActive(id) {
    var nodes = document.querySelectorAll("[data-part]");
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      n.classList.toggle("is-on", n.getAttribute("data-part") === id);
      n.classList.toggle("is-dim", id && n.getAttribute("data-part") !== id);
    }
    var chips = document.querySelectorAll("#legend .chip");
    for (var j = 0; j < chips.length; j++) {
      chips[j].classList.toggle("on", chips[j].getAttribute("data-part") === id);
    }
    var p = partMeta(id);
    if (!p) return;
    seen[id] = true;
    chips = document.querySelectorAll("#legend .chip");
    for (var k = 0; k < chips.length; k++) {
      if (seen[chips[k].getAttribute("data-part")]) chips[k].classList.add("seen");
    }
    var html = "<h2>" + p.name + "</h2>";
    if (p.hint) html += "<p class='hint'>" + p.hint + "</p>";
    html += "<div>" + (p.detail || "") + "</div>";
    if (p.mistake) html += "<div class='mist'>易错：" + p.mistake + "</div>";
    $("detail").innerHTML = html;
    maybeReadyQuiz();
  }

  function showIntro() {
    $("detail").innerHTML =
      "<h2>" + (DATA.title || "") + "</h2>" +
      "<p class='hint'>" + (DATA.goal || "点击图中结构或右侧名称") + "</p>" +
      "<div>" + (DATA.intro || "") + "</div>";
  }

  function bindParts() {
    var nodes = document.querySelectorAll("[data-part]");
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].addEventListener("click", function (ev) {
        ev.stopPropagation();
        setActive(this.getAttribute("data-part"));
      });
    }
  }

  function renderLegend() {
    var box = $("legend");
    box.innerHTML = "";
    (DATA.parts || []).forEach(function (p) {
      var b = document.createElement("button");
      b.className = "chip";
      b.type = "button";
      b.setAttribute("data-part", p.id);
      b.textContent = p.name;
      b.onclick = function () { setActive(p.id); };
      box.appendChild(b);
    });
  }

  function showPhase(i) {
    var phases = DATA.phases || [];
    if (!phases.length) return;
    phaseIndex = (i + phases.length) % phases.length;
    var cur = phases[phaseIndex];
    var nodes = document.querySelectorAll("[data-phase]");
    for (var n = 0; n < nodes.length; n++) {
      var id = nodes[n].getAttribute("data-phase");
      nodes[n].classList.toggle("is-off", id !== cur.id);
    }
    var btns = document.querySelectorAll("#phases .pbtn");
    for (var b = 0; b < btns.length; b++) btns[b].classList.toggle("on", Number(btns[b].dataset.i) === phaseIndex);
    $("hint").textContent = cur.hint || DATA.hint || "";
    $("detail").innerHTML = "<h2>" + cur.name + "</h2><div>" + (cur.detail || "") + "</div>";
  }

  function renderPhases() {
    var box = $("phases");
    box.innerHTML = "";
    if (!(DATA.phases || []).length) return;
    $("list-title").textContent = "过程";
    (DATA.phases || []).forEach(function (p, i) {
      var b = document.createElement("button");
      b.className = "pbtn";
      b.type = "button";
      b.dataset.i = String(i);
      b.textContent = p.name;
      b.onclick = function () {
        userHoldPhase = true;
        setPlaying(false);
        showPhase(i);
      };
      box.appendChild(b);
    });
    var actions = $("actions");
    var prev = document.createElement("button");
    prev.className = "btn ghost";
    prev.textContent = "上一阶段";
    prev.onclick = function () { userHoldPhase = true; setPlaying(false); showPhase(phaseIndex - 1); };
    var next = document.createElement("button");
    next.className = "btn";
    next.textContent = "下一阶段";
    next.onclick = function () { userHoldPhase = true; setPlaying(false); showPhase(phaseIndex + 1); };
    actions.appendChild(prev);
    actions.appendChild(next);
    showPhase(0);
  }

  function maybeReadyQuiz() {
    var quiz = DATA.quiz;
    if (!quiz) return;
    var need = (DATA.parts || []).length;
    var n = Object.keys(seen).length;
    if (need && n < Math.min(need, 4)) return;
    if ($("quiz-btn")) return;
    var b = document.createElement("button");
    b.id = "quiz-btn";
    b.className = "btn";
    b.textContent = "检测一下";
    b.onclick = showQuiz;
    $("actions").appendChild(b);
  }

  function showQuiz() {
    var quiz = DATA.quiz;
    if (!quiz) return;
    var html = "<h2>" + quiz.q + "</h2>";
    $("detail").innerHTML = html;
    (quiz.options || []).forEach(function (opt) {
      var btn = document.createElement("button");
      btn.className = "choice";
      btn.type = "button";
      btn.textContent = opt.t;
      btn.onclick = function () {
        report(!!opt.ok, quiz.q, opt.t);
        toast(opt.ok ? (quiz.ok || "正确") : (opt.why || quiz.bad || "再看一看图"), !opt.ok);
        if (opt.ok) $("detail").innerHTML += "<p class='hint'>" + (quiz.explain || "") + "</p>";
      };
      $("detail").appendChild(btn);
    });
  }

  function setPlaying(on) {
    playing = on;
    if (on) userHoldPhase = false;
    var view = $("view");
    if (view) view.classList.toggle("paused", !playing);
    var btn = $("btn-play");
    if (btn) btn.textContent = playing ? "暂停仿真" : "播放仿真";
    var note = $("sim-note");
    if (note) note.textContent = playing ? "仿真播放中" : "已暂停";
  }

  function lerp(a, b, t) { return a + (b - a) * t; }

  function sampleKeys(keys, u) {
    if (!keys || !keys.length) return {};
    if (u <= keys[0].t) return keys[0];
    for (var i = 0; i < keys.length - 1; i++) {
      if (u <= keys[i + 1].t) {
        var a = keys[i], b = keys[i + 1];
        var p = (u - a.t) / ((b.t - a.t) || 1);
        var out = {};
        ["x", "y", "r", "s", "o"].forEach(function (k) {
          if (a[k] != null || b[k] != null) out[k] = lerp(a[k] || 0, b[k] || 0, p);
        });
        return out;
      }
    }
    return keys[keys.length - 1];
  }

  function applySim(u) {
    var tracks = DATA.tracks || [];
    for (var i = 0; i < tracks.length; i++) {
      var tr = tracks[i];
      var el = document.querySelector('[data-sim="' + tr.id + '"]');
      if (!el) continue;
      var uu = u;
      if (tr.pingpong) {
        var c = uu * 2;
        uu = c < 1 ? c : 2 - c;
      }
      if (tr.path) {
        var path = pathCache[tr.id];
        if (!path) {
          path = document.createElementNS("http://www.w3.org/2000/svg", "path");
          path.setAttribute("d", tr.path);
          pathCache[tr.id] = path;
        }
        var len = path.getTotalLength();
        var pt = path.getPointAtLength(uu * Math.max(len, 1));
        el.setAttribute("transform", "translate(" + (pt.x - (tr.ox || 0)) + "," + (pt.y - (tr.oy || 0)) + ")");
        continue;
      }
      var k = sampleKeys(tr.keys, uu);
      var x = k.x || 0, y = k.y || 0, r = k.r || 0, s = k.s == null ? 1 : k.s;
      var cx = tr.cx, cy = tr.cy;
      var tf = (cx != null)
        ? ("rotate(" + r + "," + cx + "," + cy + ") translate(" + x + "," + y + ") scale(" + s + ")")
        : ("translate(" + x + "," + y + ") rotate(" + r + ") scale(" + s + ")");
      el.setAttribute("transform", tf);
      if (k.o != null) el.setAttribute("opacity", k.o);
    }
  }

  function tick(ts) {
    if (!lastTs) lastTs = ts;
    var dt = ts - lastTs;
    lastTs = ts;
    if (playing) elapsed += dt;
    var period = DATA.period || 8000;
    var u = (elapsed % period) / period;
    applySim(u);
    var phases = DATA.phases || [];
    if (playing && phases.length && !userHoldPhase) {
      var i = Math.floor(u * phases.length) % phases.length;
      if (i !== phaseIndex) showPhase(i);
    }
    requestAnimationFrame(tick);
  }

  function bindSimBar() {
    var btn = $("btn-play");
    if (!btn) return;
    btn.onclick = function () { setPlaying(!playing); };
    setPlaying(true);
  }

  function init() {
    $("badge").textContent = DATA.badge || "生物探究";
    $("title").textContent = DATA.title || "生物探究";
    $("subtitle").textContent = DATA.subtitle || "";
    $("equation").textContent = DATA.equation || "";
    $("equation").style.display = DATA.equation ? "" : "none";
    $("hint").textContent = DATA.hint || "点击图中结构，右侧会说明它的功能。";
    $("view").innerHTML = DATA.svg || "";
    bindParts();
    bindSimBar();
    if (DATA.mode === "phases") {
      $("legend").style.display = "none";
      renderPhases();
      maybeReadyQuiz();
    } else {
      renderLegend();
      showIntro();
    }
    requestAnimationFrame(tick);
  }

  init();
})();
