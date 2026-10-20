window.addEventListener("load", function () {
  setTimeout(function () {
    var L = window.OpticsLab, out = [];
    function log(s) { out.push(s); }
    function set(parts) { var d = L.getData(); d.parts = parts; L.setData(d); }
    function P(id, type, x, y, rot, props) { return { id: id, type: type, x: x, y: y, rot: rot || 0, props: props || {} }; }
    function ev() { return L.state().events.map(function (e) { return e.type + ":" + e.part.type + ":i=" + (e.i == null ? "-" : e.i.toFixed(1)) + ",o=" + (e.o == null ? "-" : e.o.toFixed(1)); }).join(" | "); }
    try {
      var mode = document.title;
      log("title=" + mode);
      log("init events: " + ev());
      if (/反射定律/.test(mode)) {
        set([P("m", "mirror", 600, 540), P("l", "laser", 330, 300, 30)]);
        log("rot30: " + ev());
        L.record();
        log("records=" + JSON.stringify(L.getData().records));
      }
      if (/折射/.test(mode)) {
        set([P("s", "semi", 600, 400, 0, { n: 1.5 }), P("l", "laser", 600 - 260 * Math.cos(40 * Math.PI / 180), 400 - 260 * Math.sin(40 * Math.PI / 180), 40)]);
        log("semi a40: " + ev() + " tir=" + L.check({ type: "tir" }));
        set([P("s", "semi", 600, 400, 0, { n: 1.5 }), P("l", "laser", 600 - 260 * Math.cos(60 * Math.PI / 180), 400 - 260 * Math.sin(60 * Math.PI / 180), 60)]);
        log("semi a60: " + ev());
      }
      if (/凸透镜/.test(mode)) {
        [[40, 13.33], [20, 20], [15, 30], [5, 0]].forEach(function (c) {
          var cx = 600 - c[0] * 10;
          set([P("c", "candle", cx, 400), P("v", "convex", 600, 400, 0, { f: 10 }), P("s", "screen", c[1] ? 600 + c[1] * 10 : 1050, 400)]);
          var im = L.state().images[0];
          log("u=" + c[0] + " real=" + im.real + " u=" + (im.u / 10).toFixed(2) + " v=" + (im.v / 10).toFixed(2) + " m=" + (im.m || 0).toFixed(2) +
            " screen=" + (im.screen ? ("blur=" + im.screen.blur.toFixed(1) + " sharp=" + im.screen.sharp) : "none"));
          L.record();
        });
        log("checks reduced/equal/enlarged/virtual=" + ["reduced", "equal", "enlarged", "virtual"].map(function (k) { return L.check({ type: "image", kind: k }); }));
        log("records=" + JSON.stringify(L.getData().records));
        log("steps=" + JSON.stringify(L.steps()));
      }
    } catch (e) { log("ERR " + e.message + " " + e.stack); }
    var pre = document.createElement("pre"); pre.id = "test-out"; pre.textContent = out.join("\n"); document.body.appendChild(pre);
  }, 300);
});
window.onerror = function (m, s, l) { var p = document.createElement("pre"); p.id = "test-err"; p.textContent = "PAGEERR " + m + " @" + l; document.documentElement.appendChild(p); };
