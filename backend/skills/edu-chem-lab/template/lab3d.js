/* 宏观实验台 3D 引擎：Three.js 场景、工位拾取、器材显隐与现象。 */
(function (global) {
  var THREE = global.THREE;
  if (!THREE) { console.error("THREE missing"); return; }

  var renderer, scene, camera, canvas, raycaster, pointer;
  var root, slots = {}, pieces = {}, fx = {};
  var yaw = 0.62, pitch = 0.30, dist = 5.7;
  var orbiting = false, lastX = 0, lastY = 0;
  var selecting = false;
  var needed = {};
  var anim = [];

  function mat(color, opts) {
    opts = opts || {};
    return new THREE.MeshStandardMaterial({
      color: color,
      roughness: opts.roughness != null ? opts.roughness : 0.45,
      metalness: opts.metalness || 0,
      transparent: !!opts.transparent,
      opacity: opts.opacity != null ? opts.opacity : 1,
      emissive: opts.emissive || 0x000000,
      emissiveIntensity: opts.emissiveIntensity || 0
    });
  }
  function glass(color) {
    return new THREE.MeshPhysicalMaterial({
      color: color || 0xc7ecff, roughness: 0.12, metalness: 0.02,
      transparent: true, opacity: 0.42, transmission: 0.55, thickness: 0.5
    });
  }
  function add(parent, mesh, x, y, z) {
    mesh.position.set(x || 0, y || 0, z || 0);
    mesh.castShadow = true; mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }
  function cyl(rTop, rBot, h, matl, seg) {
    return new THREE.Mesh(new THREE.CylinderGeometry(rTop, rBot, h, seg || 24), matl);
  }
  function box(w, h, d, matl) {
    return new THREE.Mesh(new THREE.BoxGeometry(w, h, d), matl);
  }
  function sph(r, matl) {
    return new THREE.Mesh(new THREE.SphereGeometry(r, 20, 16), matl);
  }
  function hexCss(c) {
    return "#" + ("000000" + ((c >>> 0) & 0xffffff).toString(16)).slice(-6);
  }
  function labelSprite(text, color) {
    var c = document.createElement("canvas");
    c.width = 256; c.height = 64;
    var g = c.getContext("2d");
    g.clearRect(0, 0, 256, 64);
    g.font = "bold 28px sans-serif";
    g.fillStyle = color || "#0f766e";
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText(text, 128, 32);
    var tex = new THREE.CanvasTexture(c);
    var spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true }));
    spr.scale.set(0.7, 0.18, 1);
    return spr;
  }

  function makeSlot(name, title, x, y, z, color) {
    var g = new THREE.Group();
    var ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.22, 0.018, 10, 32),
      mat(color || 0x0f766e, { emissive: color || 0x0f766e, emissiveIntensity: 0.35, roughness: 0.3 })
    );
    ring.rotation.x = Math.PI / 2;
    var pad = new THREE.Mesh(
      new THREE.CircleGeometry(0.22, 24),
      mat(color || 0x99f6e4, { transparent: true, opacity: 0.28 })
    );
    pad.rotation.x = -Math.PI / 2;
    pad.position.y = 0.01;
    var hit = new THREE.Mesh(
      new THREE.CylinderGeometry(0.28, 0.28, 0.16, 16),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    hit.position.y = 0.08;
    hit.userData.slot = name;
    var lab = labelSprite(title, color ? hexCss(color) : "#0f766e");
    lab.position.set(0, 0.28, 0);
    g.add(ring, pad, hit, lab);
    g.position.set(x, y, z);
    g.userData.slot = name;
    g.traverse(function (o) { o.userData.slot = name; });
    slots[name] = g;
    root.add(g);
    return g;
  }

  function pieceGroup(id, builder, x, y, z) {
    var g = new THREE.Group();
    builder(g);
    g.position.set(x, y, z);
    g.visible = false;
    pieces[id] = g;
    root.add(g);
    return g;
  }

  function buildStand(g) {
    add(g, cyl(0.16, 0.18, 0.06, mat(0x334155, { metalness: 0.6, roughness: 0.35 })), 0, 0.03, 0);
    add(g, cyl(0.03, 0.03, 0.95, mat(0x64748b, { metalness: 0.7, roughness: 0.28 })), 0, 0.5, 0);
    var arm = box(0.38, 0.04, 0.05, mat(0x475569, { metalness: 0.65 }));
    add(g, arm, 0.16, 0.72, 0);
    add(g, box(0.05, 0.05, 0.12, mat(0x334155, { metalness: 0.6 })), 0.32, 0.72, 0);
  }
  function buildTube(g, tilt) {
    var body = cyl(0.055, 0.06, 0.42, glass(0xd6f0ff), 28);
    add(g, body, 0, 0.28, 0);
    add(g, cyl(0.062, 0.062, 0.03, glass(0xf8fafc), 28), 0, 0.5, 0);
    var powder = cyl(0.045, 0.048, 0.06, mat(0x6b21a8), 16);
    fx.powder = add(g, powder, 0, 0.1, 0);
    var zinc = box(0.05, 0.03, 0.04, mat(0x94a3b8, { metalness: 0.5 }));
    fx.zinc = add(g, zinc, 0.01, 0.12, 0);
    var marble = sph(0.025, mat(0xf8fafc));
    fx.marble = add(g, marble, -0.01, 0.11, 0.01);
    var acid = cyl(0.048, 0.05, 0.16, mat(0x38bdf8, { transparent: true, opacity: 0.45 }), 20);
    fx.acid = add(g, acid, 0, 0.18, 0);
    powder.visible = zinc.visible = marble.visible = acid.visible = false;
    if (tilt) g.rotation.z = tilt;
    fx.tube = g;
  }
  function buildLamp(g) {
    add(g, cyl(0.09, 0.1, 0.08, mat(0xb45309, { roughness: 0.5 })), 0, 0.05, 0);
    add(g, cyl(0.075, 0.08, 0.1, mat(0xf59e0b, { roughness: 0.4 })), 0, 0.13, 0);
    add(g, cyl(0.02, 0.02, 0.04, mat(0x78716c)), 0, 0.2, 0);
    var flame = new THREE.Mesh(
      new THREE.ConeGeometry(0.035, 0.12, 10),
      mat(0xf97316, { emissive: 0xf97316, emissiveIntensity: 0.9, transparent: true, opacity: 0.85 })
    );
    fx.flame = add(g, flame, 0, 0.28, 0);
    var light = new THREE.PointLight(0xff8a3d, 0, 2.4);
    light.position.set(0, 0.3, 0);
    g.add(light);
    fx.flameLight = light;
    flame.visible = false;
  }
  function buildDelivery(g) {
    var curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-0.35, 0.42, 0),
      new THREE.Vector3(0.05, 0.38, 0.05),
      new THREE.Vector3(0.45, 0.22, 0.08),
      new THREE.Vector3(0.85, 0.12, 0.1)
    ]);
    var mesh = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 24, 0.018, 8, false),
      mat(0x475569, { metalness: 0.55, roughness: 0.3 })
    );
    g.add(mesh);
  }
  function buildTrough(g) {
    var wall = mat(0x0369a1, { roughness: 0.35 });
    add(g, box(1.15, 0.06, 0.62, wall), 0, 0.03, 0);
    add(g, box(1.15, 0.22, 0.04, wall), 0, 0.14, 0.29);
    add(g, box(1.15, 0.22, 0.04, wall), 0, 0.14, -0.29);
    add(g, box(0.04, 0.22, 0.62, wall), 0.555, 0.14, 0);
    add(g, box(0.04, 0.22, 0.62, wall), -0.555, 0.14, 0);
    var water = box(1.05, 0.1, 0.52, mat(0x38bdf8, { transparent: true, opacity: 0.45 }));
    fx.troughWater = add(g, water, 0, 0.12, 0);
  }
  function buildBottle(g) {
    var body = cyl(0.12, 0.13, 0.28, glass(0xdbeafe), 24);
    add(g, body, 0, 0.2, 0);
    add(g, cyl(0.05, 0.06, 0.1, glass(0xe0f2fe), 16), 0, 0.38, 0);
    var gas = cyl(0.1, 0.1, 0.1, mat(0xf8fafc, { transparent: true, opacity: 0.55 }), 16);
    fx.gas = add(g, gas, 0, 0.26, 0);
    var water = cyl(0.11, 0.12, 0.05, mat(0x38bdf8, { transparent: true, opacity: 0.5 }), 16);
    fx.bottleWater = add(g, water, 0, 0.1, 0);
    gas.visible = water.visible = false;
    fx.bottle = g;
  }
  function buildSplint(g) {
    add(g, box(0.025, 0.32, 0.025, mat(0xb45309)), 0, 0.2, 0);
    var tip = sph(0.04, mat(0xfbbf24, { emissive: 0xf59e0b, emissiveIntensity: 0.4 }));
    fx.splintGlow = add(g, tip, 0, 0.38, 0);
  }
  function buildBeaker(g) {
    add(g, cyl(0.2, 0.17, 0.32, glass(0xdbeafe), 28), 0, 0.2, 0);
    add(g, cyl(0.21, 0.21, 0.03, glass(0xf8fafc), 28), 0, 0.36, 0);
    var liquid = cyl(0.16, 0.15, 0.12, mat(0x7dd3fc, { transparent: true, opacity: 0.55 }), 20);
    fx.liquid = add(g, liquid, 0, 0.14, 0);
    var metal = box(0.08, 0.03, 0.05, mat(0x94a3b8, { metalness: 0.55 }));
    fx.metal = add(g, metal, 0, 0.16, 0);
    metal.visible = false;
    fx.beakerBubbles = [];
    for (var i = 0; i < 8; i++) {
      var b = sph(0.012 + Math.random() * 0.01, mat(0xffffff, { transparent: true, opacity: 0.7 }));
      b.visible = false;
      fx.beakerBubbles.push(add(g, b, (Math.random() - 0.5) * 0.12, 0.14 + Math.random() * 0.1, (Math.random() - 0.5) * 0.12));
    }
  }
  function buildDropper(g) {
    add(g, sph(0.045, mat(0xf87171)), 0, 0.22, 0);
    add(g, cyl(0.015, 0.015, 0.18, glass(0xe0f2fe), 12), 0, 0.1, 0);
    var drip = sph(0.015, mat(0x38bdf8));
    fx.drip = add(g, drip, 0, 0.0, 0);
    drip.visible = false;
  }
  function buildRod(g) {
    var m = cyl(0.012, 0.012, 0.42, mat(0xe2e8f0, { roughness: 0.2 }), 10);
    m.rotation.z = 0.35;
    add(g, m, 0.08, 0.22, 0);
  }
  function buildGoggles(g) {
    add(g, box(0.28, 0.08, 0.08, mat(0x0f766e, { roughness: 0.4 })), 0, 0.2, 0);
    add(g, sph(0.045, glass(0xffffff)), -0.06, 0.2, 0.03);
    add(g, sph(0.045, glass(0xffffff)), 0.06, 0.2, 0.03);
  }
  function buildFunnel(g) {
    add(g, new THREE.Mesh(new THREE.ConeGeometry(0.18, 0.22, 20, 1, true), glass(0xdbeafe)), 0, 0.42, 0);
    add(g, cyl(0.025, 0.025, 0.18, glass(0xbae6fd), 12), 0, 0.22, 0);
    var paper = new THREE.Mesh(new THREE.ConeGeometry(0.15, 0.16, 16, 1, true), mat(0xf8fafc, { transparent: true, opacity: 0.85 }));
    fx.filterPaper = add(g, paper, 0, 0.4, 0);
    var residue = sph(0.05, mat(0xa8a29e));
    fx.residue = add(g, residue, 0, 0.42, 0);
    paper.visible = residue.visible = false;
  }
  function buildPaper(g) {
    add(g, box(0.16, 0.005, 0.22, mat(0xf8fafc)), 0, 0.02, 0);
  }
  function buildDish(g) {
    add(g, cyl(0.2, 0.16, 0.06, mat(0xcbd5e1, { roughness: 0.35 }), 24), 0, 0.04, 0);
    var liq = cyl(0.16, 0.15, 0.025, mat(0x7dd3fc, { transparent: true, opacity: 0.55 }), 20);
    fx.dishLiquid = add(g, liq, 0, 0.05, 0);
    fx.crystals = new THREE.Group();
    for (var i = 0; i < 6; i++) {
      var c = box(0.03, 0.025, 0.03, mat(0xe0f2fe));
      c.position.set((i % 3 - 1) * 0.05, 0.06, (i < 3 ? -0.04 : 0.04));
      c.rotation.y = i;
      fx.crystals.add(c);
    }
    fx.crystals.visible = false;
    g.add(fx.crystals);
  }
  function buildGauze(g) {
    add(g, box(0.42, 0.02, 0.42, mat(0x94a3b8, { metalness: 0.4, roughness: 0.55 })), 0, 0.02, 0);
  }
  function buildCell(g) {
    add(g, box(1.4, 0.28, 0.7, mat(0x38bdf8, { transparent: true, opacity: 0.35 })), 0, 0.16, 0);
    add(g, box(1.42, 0.04, 0.72, mat(0x0369a1)), 0, 0.02, 0);
    add(g, box(0.04, 0.28, 0.04, mat(0x64748b, { metalness: 0.6 })), -0.35, 0.2, 0);
    add(g, box(0.04, 0.28, 0.04, mat(0x64748b, { metalness: 0.6 })), 0.35, 0.2, 0);
  }
  function buildPower(g) {
    add(g, box(0.36, 0.16, 0.22, mat(0x111827, { roughness: 0.4 })), 0, 0.2, 0);
    var lab = labelSprite("电源", "#fbbf24");
    lab.position.set(0, 0.34, 0.12);
    g.add(lab);
  }
  function buildTubes(g) {
    add(g, cyl(0.06, 0.06, 0.28, glass(0xdbeafe), 16), -0.35, 0.42, 0);
    add(g, cyl(0.06, 0.06, 0.28, glass(0xdbeafe), 16), 0.35, 0.42, 0);
    fx.h2 = labelSprite("H₂", "#0f766e");
    fx.o2 = labelSprite("O₂", "#b45309");
    fx.h2.position.set(-0.35, 0.62, 0.08);
    fx.o2.position.set(0.35, 0.62, 0.08);
    fx.h2.visible = fx.o2.visible = false;
    g.add(fx.h2, fx.o2);
    fx.ratio = labelSprite("体积比约 2 : 1", "#0f766e");
    fx.ratio.scale.set(1.2, 0.22, 1);
    fx.ratio.position.set(0, 0.08, 0.45);
    fx.ratio.visible = false;
    g.add(fx.ratio);
  }
  function buildBalance(g) {
    add(g, box(0.42, 0.04, 0.16, mat(0x78716c)), 0, 0.08, 0);
    add(g, box(0.04, 0.16, 0.04, mat(0x57534e)), 0, 0.16, 0);
    add(g, cyl(0.08, 0.08, 0.02, mat(0xa8a29e), 16), -0.16, 0.1, 0);
    add(g, cyl(0.08, 0.08, 0.02, mat(0xa8a29e), 16), 0.16, 0.1, 0);
  }
  function buildCylinder(g) {
    add(g, cyl(0.07, 0.07, 0.36, glass(0xdbeafe), 20), 0, 0.22, 0);
  }
  function buildWire(g) {
    var curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-0.08, 0.02, 0), new THREE.Vector3(-0.02, 0.12, 0.04),
      new THREE.Vector3(0.04, 0.04, -0.03), new THREE.Vector3(0.1, 0.14, 0.02)
    ]);
    g.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 16, 0.012, 6, false), mat(0x64748b, { metalness: 0.7 })));
  }
  function buildCover(g) {
    add(g, cyl(0.14, 0.14, 0.02, glass(0xe2e8f0), 20), 0, 0.02, 0);
  }
  function buildLime(g) {
    add(g, cyl(0.11, 0.09, 0.22, glass(0xe2e8f0), 20), 0, 0.14, 0);
    var liq = cyl(0.085, 0.08, 0.07, mat(0xe0f2fe, { transparent: true, opacity: 0.55 }), 16);
    fx.limeLiquid = add(g, liq, 0, 0.1, 0);
  }

  function buildRoom() {
    root = new THREE.Group();
    scene.add(root);
    add(root, new THREE.Mesh(new THREE.PlaneGeometry(16, 16), mat(0xc9b896, { roughness: 0.92 })), 0, 0, 0)
      .rotation.x = -Math.PI / 2;
    add(root, box(6.4, 0.02, 3.2, mat(0x64748b, { roughness: 0.8 })), 0, 0.02, 0.1);
    var wall = mat(0xeef3f8, { roughness: 0.88 });
    add(root, box(12, 5, 0.12, wall), 0, 2.4, -3.2);
    add(root, box(0.12, 5, 8, wall), -5.2, 2.4, 0);
    add(root, box(2.4, 1.5, 0.04, mat(0x7dd3fc, { roughness: 0.15, metalness: 0.1, transparent: true, opacity: 0.65 })), 1.4, 2.7, -3.13);
    add(root, box(2.55, 0.06, 0.08, mat(0xf8fafc)), 1.4, 3.48, -3.12);
    add(root, box(2.55, 0.06, 0.08, mat(0xf8fafc)), 1.4, 1.92, -3.12);
    add(root, box(0.06, 1.56, 0.08, mat(0xf8fafc)), 0.16, 2.7, -3.12);
    add(root, box(0.06, 1.56, 0.08, mat(0xf8fafc)), 2.64, 2.7, -3.12);
    add(root, box(2.2, 0.08, 0.32, mat(0x78716c, { roughness: 0.5 })), -2.4, 2.35, -2.95);
    add(root, cyl(0.045, 0.05, 0.18, mat(0x7c3aed)), -2.9, 2.48, -2.95);
    add(root, cyl(0.045, 0.05, 0.16, mat(0x16a34a)), -2.55, 2.47, -2.95);
    add(root, cyl(0.045, 0.05, 0.2, mat(0xdc2626)), -2.2, 2.49, -2.95);
    add(root, cyl(0.04, 0.045, 0.14, mat(0x0284c7)), -1.85, 2.46, -2.95);
    var bench = box(5.2, 0.16, 2.15, mat(0xb8894c, { roughness: 0.58 }));
    add(root, bench, 0, 0.93, 0);
    add(root, box(5.28, 0.08, 0.1, mat(0x7a4a22)), 0, 0.86, 1.08);
    add(root, box(0.14, 0.86, 0.14, mat(0x7a4a22)), -2.35, 0.43, 0.88);
    add(root, box(0.14, 0.86, 0.14, mat(0x7a4a22)), 2.35, 0.43, 0.88);
    add(root, box(0.14, 0.86, 0.14, mat(0x7a4a22)), -2.35, 0.43, -0.88);
    add(root, box(0.14, 0.86, 0.14, mat(0x7a4a22)), 2.35, 0.43, -0.88);
    add(root, box(1.35, 1.55, 0.38, mat(0x64748b, { roughness: 0.45 })), -3.55, 1.72, -2.75);
    add(root, box(0.55, 0.62, 0.04, mat(0xcbd5e1)), -3.82, 1.95, -2.55);
    add(root, box(0.55, 0.62, 0.04, mat(0xcbd5e1)), -3.22, 1.95, -2.55);
    add(root, cyl(0.045, 0.05, 0.08, mat(0x475569, { metalness: 0.6 })), 2.15, 1.08, 0.85);
    add(root, cyl(0.012, 0.012, 0.12, mat(0x94a3b8, { metalness: 0.7 })), 2.15, 1.18, 0.85);
  }

  function layout(kind) {
    var y = 1.02;
    var L = {
      oxygen: function () {
        makeSlot("stand", "铁架台", -1.55, y, 0.05, 0x0f766e);
        makeSlot("tube", "试管", -1.22, y, 0.08, 0x0284c7);
        makeSlot("lamp", "酒精灯", -1.22, y, 0.42, 0xb45309);
        makeSlot("delivery", "导管", -0.35, y, 0.1, 0x475569);
        makeSlot("trough", "水槽", 1.05, y, 0.22, 0x0369a1);
        makeSlot("bottle", "集气瓶", 1.08, y, 0.05, 0x0284c7);
        makeSlot("splint", "木条", 1.75, y, -0.35, 0xb45309);
        makeSlot("lime_beaker", "石灰水", 1.85, y, 0.4, 0x475569);
        makeSlot("paper", "试纸", -0.55, y, -0.55, 0x991b1b);
        makeSlot("wire", "铁丝", 1.05, y, -0.4, 0xbe123c);
        makeSlot("cover", "玻璃片", 1.4, y, 0.2, 0x64748b);
        makeSlot("reagent", "药品", -1.22, y, -0.22, 0x6d28d9);
        pieceGroup("stand", buildStand, -1.55, y, 0.05);
        pieceGroup("tube", function (g) { buildTube(g, -0.28); }, -1.18, y, 0.08);
        pieceGroup("lamp", buildLamp, -1.22, y, 0.42);
        pieceGroup("delivery", buildDelivery, -0.55, y, 0.1);
        pieceGroup("trough", buildTrough, 1.05, y, 0.25);
        pieceGroup("bottle", buildBottle, 1.08, y + 0.08, 0.08);
        pieceGroup("splint", buildSplint, 1.75, y, -0.35);
        pieceGroup("lime_beaker", buildLime, 1.85, y, 0.4);
        pieceGroup("paper", buildPaper, -0.55, y, -0.55);
        pieceGroup("wire", buildWire, 1.05, y, -0.4);
        pieceGroup("cover", buildCover, 1.4, y + 0.36, 0.12);
        fx.bubbles = [];
        for (var i = 0; i < 10; i++) {
          var b = sph(0.015, mat(0xffffff, { transparent: true, opacity: 0.75 }));
          b.visible = false;
          fx.bubbles.push(add(root, b, 1.0, 1.2, 0.2));
        }
        fx.sparks = [];
        for (i = 0; i < 8; i++) {
          var s = sph(0.012, mat(0xf97316, { emissive: 0xf97316, emissiveIntensity: 0.8 }));
          s.visible = false;
          fx.sparks.push(add(root, s, 1.1, 1.4, 0));
        }
        fx.jet = new THREE.Mesh(new THREE.ConeGeometry(0.03, 0.12, 8), mat(0x38bdf8, { emissive: 0x38bdf8, emissiveIntensity: 0.6 }));
        fx.jet.position.set(-0.55, 1.45, 0.1);
        fx.jet.visible = false;
        root.add(fx.jet);
        fx.pop = labelSprite("爆！", "#dc2626");
        fx.pop.scale.set(0.9, 0.28, 1);
        fx.pop.position.set(1.6, 1.7, -0.2);
        fx.pop.visible = false;
        root.add(fx.pop);
      },
      neutralization: function () {
        makeSlot("beaker", "烧杯", 0, y, 0.1, 0x0f766e);
        makeSlot("goggles", "护目镜", -2.0, y, -0.5, 0x0f766e);
        makeSlot("dropper", "胶头滴管", 0.15, y, -0.25, 0xb91c1c);
        makeSlot("rod", "玻璃棒", 0.5, y, 0.15, 0x64748b);
        makeSlot("balance", "天平", -1.55, y, 0.25, 0xb45309);
        makeSlot("cylinder", "量筒", 1.45, y, 0.2, 0x0284c7);
        makeSlot("paper", "称量纸", -1.55, y, -0.25, 0x64748b);
        makeSlot("reagent", "药品", 0, y, -0.05, 0x6d28d9);
        pieceGroup("beaker", buildBeaker, 0, y, 0.1);
        pieceGroup("goggles", buildGoggles, -2.0, y, -0.5);
        pieceGroup("dropper", buildDropper, 0.12, y + 0.28, -0.02);
        pieceGroup("rod", buildRod, 0.42, y, 0.12);
        pieceGroup("balance", buildBalance, -1.55, y, 0.25);
        pieceGroup("cylinder", buildCylinder, 1.45, y, 0.2);
        pieceGroup("paper", buildPaper, -1.55, y, -0.25);
      },
      electrolysis: function () {
        makeSlot("cell", "水槽", 0, y, 0.15, 0x0369a1);
        makeSlot("power", "电源", 0, y, -0.75, 0xb45309);
        makeSlot("tubes", "集气管", 0, y, 0.05, 0x0284c7);
        makeSlot("splint", "木条", 1.7, y, -0.35, 0xb45309);
        makeSlot("reagent", "水", 0, y, 0.35, 0x6d28d9);
        pieceGroup("cell", buildCell, 0, y, 0.15);
        pieceGroup("power", buildPower, 0, y + 0.55, -0.85);
        pieceGroup("tubes", buildTubes, 0, y, 0.15);
        pieceGroup("splint", buildSplint, 1.7, y, -0.35);
      },
      filtration: function () {
        makeSlot("stand", "铁架台", -0.7, y, 0.05, 0x0f766e);
        makeSlot("funnel", "漏斗", 0.05, y, 0.05, 0x0284c7);
        makeSlot("paper", "滤纸", 0.05, y, -0.25, 0x64748b);
        makeSlot("beaker", "烧杯", 0.05, y, 0.4, 0x475569);
        makeSlot("rod", "玻璃棒", -0.45, y, -0.4, 0x64748b);
        makeSlot("reagent", "浊液", 0.5, y, -0.25, 0x6d28d9);
        pieceGroup("stand", buildStand, -0.7, y, 0.05);
        pieceGroup("funnel", buildFunnel, 0.05, y, 0.05);
        pieceGroup("paper", buildPaper, 0.05, y + 0.55, -0.02);
        pieceGroup("beaker", function (g) {
          buildBeaker(g);
          fx.filtrate = fx.liquid;
        }, 0.05, y, 0.42);
        pieceGroup("rod", buildRod, -0.4, y + 0.25, -0.15);
      },
      evaporation: function () {
        makeSlot("stand", "三脚架", 0, y, 0.15, 0x475569);
        makeSlot("gauze", "陶土网", 0, y, 0.0, 0x64748b);
        makeSlot("dish", "蒸发皿", 0, y, -0.05, 0x0284c7);
        makeSlot("lamp", "酒精灯", 0, y, 0.4, 0xb45309);
        makeSlot("rod", "玻璃棒", 0.55, y, -0.25, 0x64748b);
        makeSlot("reagent", "溶液", 0, y, -0.22, 0x6d28d9);
        pieceGroup("stand", function (g) {
          add(g, box(0.7, 0.04, 0.04, mat(0x64748b, { metalness: 0.5 })), 0, 0.22, 0.18);
          add(g, box(0.04, 0.28, 0.04, mat(0x475569, { metalness: 0.5 })), -0.28, 0.12, 0.18);
          add(g, box(0.04, 0.28, 0.04, mat(0x475569, { metalness: 0.5 })), 0.28, 0.12, 0.18);
          add(g, box(0.04, 0.28, 0.04, mat(0x475569, { metalness: 0.5 })), 0, 0.12, -0.22);
        }, 0, y, 0.1);
        pieceGroup("gauze", buildGauze, 0, y + 0.26, 0.05);
        pieceGroup("dish", buildDish, 0, y + 0.3, 0.05);
        pieceGroup("lamp", buildLamp, 0, y, 0.42);
        pieceGroup("rod", buildRod, 0.5, y + 0.28, -0.1);
        fx.steam = [];
        for (var i = 0; i < 6; i++) {
          var st = sph(0.03, mat(0xcbd5e1, { transparent: true, opacity: 0.35 }));
          st.visible = false;
          fx.steam.push(add(root, st, (i - 2) * 0.06, 1.5, 0.05));
        }
      }
    };
    (L[kind] || L.oxygen)();
  }

  function updateCamera() {
    pitch = Math.max(0.18, Math.min(1.15, pitch));
    camera.position.set(
      Math.sin(yaw) * Math.cos(pitch) * dist,
      1.15 + Math.sin(pitch) * dist * 0.85,
      Math.cos(yaw) * Math.cos(pitch) * dist
    );
    camera.lookAt(0, 1.15, 0);
  }

  function tick(t) {
    requestAnimationFrame(tick);
    var pulse = 0.7 + Math.sin(t * 0.004) * 0.3;
    Object.keys(slots).forEach(function (k) {
      var s = slots[k];
      if (!s.visible) return;
      s.scale.setScalar(0.95 + pulse * 0.08);
    });
    if (fx.flame && fx.flame.visible) {
      fx.flame.scale.y = 0.85 + Math.sin(t * 0.02) * 0.2;
      if (fx.flameLight) fx.flameLight.intensity = 1.1 + Math.sin(t * 0.03) * 0.3;
    }
    (fx.bubbles || []).forEach(function (b, i) {
      if (!b.visible) return;
      b.position.y += 0.006;
      if (b.position.y > 1.7) b.position.y = 1.15;
      b.position.x = 1.05 + Math.sin(t * 0.01 + i) * 0.05;
    });
    (fx.beakerBubbles || []).forEach(function (b, i) {
      if (!b.visible) return;
      b.position.y += 0.004;
      if (b.position.y > 0.32) b.position.y = 0.12;
    });
    (fx.steam || []).forEach(function (s, i) {
      if (!s.visible) return;
      s.position.y += 0.004;
      s.material.opacity = 0.28;
      if (s.position.y > 1.9) s.position.y = 1.45;
    });
    (fx.sparks || []).forEach(function (s, i) {
      if (!s.visible) return;
      s.position.x = 1.08 + Math.sin(t * 0.02 + i) * 0.12;
      s.position.y = 1.35 + Math.cos(t * 0.03 + i) * 0.1;
    });
    renderer.render(scene, camera);
  }

  function onPointerDown(e) {
    if (e.button !== 0) return;
    orbiting = true;
    lastX = e.clientX; lastY = e.clientY;
  }
  function onPointerMove(e) {
    if (!orbiting) return;
    yaw -= (e.clientX - lastX) * 0.006;
    pitch -= (e.clientY - lastY) * 0.005;
    lastX = e.clientX; lastY = e.clientY;
    updateCamera();
  }
  function onPointerUp() { orbiting = false; }
  function onWheel(e) {
    dist = Math.max(3.6, Math.min(7.5, dist + e.deltaY * 0.004));
    updateCamera();
  }

  function init(el, sceneKey) {
    canvas = el;
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xb9d4ea);
    scene.fog = new THREE.Fog(0xb9d4ea, 8, 16);
    camera = new THREE.PerspectiveCamera(42, 1, 0.1, 40);
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: false });
    renderer.shadowMap.enabled = true;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();
    scene.add(new THREE.HemisphereLight(0xf0f7ff, 0x8b6914, 0.85));
    var sun = new THREE.DirectionalLight(0xfff4e0, 1.05);
    sun.position.set(3.5, 6, 4);
    sun.castShadow = true;
    scene.add(sun);
    scene.add(new THREE.AmbientLight(0xffffff, 0.25));
    buildRoom();
    layout(sceneKey || "oxygen");
    updateCamera();
    resize();
    canvas.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    canvas.addEventListener("wheel", onWheel, { passive: true });
    requestAnimationFrame(tick);
  }

  function resize() {
    if (!canvas || !renderer) return;
    var w = canvas.clientWidth || 640;
    var h = canvas.clientHeight || 380;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  }

  function setSelecting(on, needMap) {
    selecting = !!on;
    needed = needMap || {};
    Object.keys(slots).forEach(function (k) {
      slots[k].visible = selecting && !!needed[k];
    });
  }
  function setPiece(id, on) {
    if (pieces[id]) pieces[id].visible = !!on;
  }
  function applyEffects(st) {
    st = st || {};
    if (fx.powder) fx.powder.visible = !!st.powder;
    if (fx.zinc) fx.zinc.visible = !!st.zinc;
    if (fx.marble) fx.marble.visible = !!st.marble;
    if (fx.acid) fx.acid.visible = !!st.acid;
    if (fx.flame) {
      fx.flame.visible = !!st.flame || !!st.heat;
      if (fx.flameLight) fx.flameLight.intensity = fx.flame.visible ? 1.2 : 0;
    }
    (fx.bubbles || []).forEach(function (b) { b.visible = !!st.bubbles; });
    if (fx.gas) fx.gas.visible = !!st.collected && !st.air_collect;
    if (fx.bottleWater) fx.bottleWater.visible = !!st.bottle_water;
    if (fx.troughWater && pieces.trough) pieces.trough.visible = pieces.trough.visible && !st.air_collect;
    if (fx.pop) fx.pop.visible = !!st.pop;
    if (fx.jet) fx.jet.visible = !!st.jet_flame;
    (fx.sparks || []).forEach(function (s) { s.visible = !!st.sparks; });
    if (fx.tube) {
      var rot = st.upright ? 0 : (st.tilt_up ? 0.28 : -0.28);
      fx.tube.rotation.z = rot;
    }
    if (fx.liquid) {
      var colors = { pink: 0xf9a8d4, pale: 0xfce7f3, clear: 0x7dd3fc };
      fx.liquid.material.color.setHex(colors[st.liquid] || colors.clear);
      if (st.filtrate === false) fx.liquid.visible = false;
      if (st.filtrate) fx.liquid.visible = true;
    }
    if (fx.drip) fx.drip.visible = !!st.dripping;
    if (fx.metal) fx.metal.visible = !!st.metal;
    (fx.beakerBubbles || []).forEach(function (b) { b.visible = !!st.acid_bubbles; });
    if (fx.h2) fx.h2.visible = !!st.gases;
    if (fx.o2) fx.o2.visible = !!st.gases;
    if (fx.ratio) fx.ratio.visible = !!st.ratio;
    if (fx.filterPaper) fx.filterPaper.visible = !!st.paper;
    if (fx.residue) fx.residue.visible = !!st.residue;
    if (fx.limeLiquid) fx.limeLiquid.material.color.setHex(st.lime_milky ? 0xf8fafc : 0xe0f2fe);
    if (fx.crystals) fx.crystals.visible = !!st.crystals;
    if (fx.dishLiquid) fx.dishLiquid.material.opacity = st.crystals ? 0.25 : 0.55;
    (fx.steam || []).forEach(function (s) { s.visible = !!st.heat; });
  }
  function hitSlot(clientX, clientY) {
    if (!canvas) return "";
    var r = canvas.getBoundingClientRect();
    pointer.x = ((clientX - r.left) / r.width) * 2 - 1;
    pointer.y = -((clientY - r.top) / r.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    var list = [];
    Object.keys(slots).forEach(function (k) {
      if (slots[k].visible) slots[k].traverse(function (o) { if (o.isMesh) list.push(o); });
    });
    var hits = raycaster.intersectObjects(list, false);
    return hits.length && hits[0].object.userData.slot ? hits[0].object.userData.slot : "";
  }

  global.Lab3D = {
    init: init, resize: resize, setSelecting: setSelecting,
    setPiece: setPiece, applyEffects: applyEffects, hitSlot: hitSlot
  };
})(window);
