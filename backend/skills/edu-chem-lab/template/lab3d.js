/* 宏观实验台 3D：实验室环境、物理玻璃器材、倒入/搅拌/加热。 */
(function (global) {
  var THREE = global.THREE;
  if (!THREE) { console.error("THREE missing"); return; }

  var renderer, scene, camera, canvas, raycaster, pointer;
  var currentExpId = "";
  var root, slots = {}, pieces = {}, fx = {};
  var yaw = 0.46, pitch = 0.46, dist = 4.05;
  var lookY = 1.18, orbiting = false, lastX = 0, lastY = 0;
  var selecting = false, needed = {};
  var clock = { t: 0 };
  var pour = { on: false, t: 0, color: 0x38bdf8 };
  var mix = { on: false, t: 0 };
  var pops = [];

  function mat(color, opts) {
    opts = opts || {};
    return new THREE.MeshStandardMaterial({
      color: color,
      roughness: opts.roughness != null ? opts.roughness : 0.45,
      metalness: opts.metalness || 0,
      transparent: !!opts.transparent,
      opacity: opts.opacity != null ? opts.opacity : 1,
      emissive: opts.emissive || 0x000000,
      emissiveIntensity: opts.emissiveIntensity || 0,
      envMapIntensity: opts.metalness > 0.4 ? 1.25 : 1,
      side: opts.side || THREE.FrontSide
    });
  }
  /* 参数对齐 three.js 官方透射玻璃示例：薄壁、低粗糙、折射率 1.5。
     质感来自环境贴图里的灯箱，不靠把玻璃涂白。 */
  function glass(tint) {
    var m = new THREE.MeshPhysicalMaterial({
      color: tint || 0xffffff,
      metalness: 0,
      roughness: 0.015,
      transmission: 1,
      thickness: 0.012,
      ior: 1.5,
      transparent: true,
      opacity: 1,
      envMapIntensity: 1,
      specularIntensity: 1,
      clearcoat: 1,
      clearcoatRoughness: 0.02
    });
    if (m.attenuationColor) {
      m.attenuationColor = new THREE.Color(0xffffff);
      m.attenuationDistance = 2.5;
    }
    return m;
  }
  /* 瓶口、管口的厚边：只有这里发一点灰绿，薄壁保持能看见里面。 */
  function glassRim(radius, tubeR) {
    var lip = glass(0xc5d4c6);
    lip.thickness = 0.2;
    lip.roughness = 0.2;
    lip.transmission = 0.7;
    if (lip.attenuationColor) {
      lip.attenuationColor = new THREE.Color(0x8eaa90);
      lip.attenuationDistance = 0.06;
    }
    var ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, tubeR || 0.007, 8, 32),
      lip
    );
    ring.rotation.x = Math.PI / 2;
    ring.castShadow = false;
    return ring;
  }
  function liquidMat(color) {
    return new THREE.MeshPhysicalMaterial({
      color: color,
      roughness: 0.12,
      metalness: 0,
      transparent: true,
      opacity: 0.94,
      transmission: 0.06,
      thickness: 0.18
    });
  }
  function add(parent, mesh, x, y, z) {
    mesh.position.set(x || 0, y || 0, z || 0);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }
  function cyl(rTop, rBot, h, matl, seg) {
    return new THREE.Mesh(new THREE.CylinderGeometry(rTop, rBot, h, seg || 32), matl);
  }
  function box(w, h, d, matl) {
    return new THREE.Mesh(new THREE.BoxGeometry(w, h, d), matl);
  }
  function sph(r, matl, w, h) {
    return new THREE.Mesh(new THREE.SphereGeometry(r, w || 24, h || 16), matl);
  }
  function lathe(pairs, matl, seg) {
    var pts = pairs.map(function (p) { return new THREE.Vector2(p[0], p[1]); });
    return new THREE.Mesh(new THREE.LatheGeometry(pts, seg || 36), matl);
  }
  function hexCss(c) {
    return "#" + ("000000" + ((c >>> 0) & 0xffffff).toString(16)).slice(-6);
  }
  function parseColor(v) {
    if (v == null) return 0x38bdf8;
    if (typeof v === "number") return v;
    return new THREE.Color(v).getHex();
  }
  function labelSprite(text, color) {
    var c = document.createElement("canvas");
    c.width = 512; c.height = 128;
    var g = c.getContext("2d");
    g.clearRect(0, 0, 512, 128);
    g.font = "700 44px 'Noto Sans SC','PingFang SC',sans-serif";
    g.fillStyle = "rgba(8,14,24,.55)";
    var w = Math.min(480, g.measureText(text).width + 48);
    roundRect(g, (512 - w) / 2, 28, w, 72, 18);
    g.fill();
    g.fillStyle = color || "#e8fffb";
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText(text, 256, 64);
    var tex = new THREE.CanvasTexture(c);
    tex.anisotropy = 4;
    var spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
    spr.scale.set(0.78, 0.2, 1);
    return spr;
  }
  function roundRect(g, x, y, w, h, r) {
    g.beginPath();
    g.moveTo(x + r, y);
    g.arcTo(x + w, y, x + w, y + h, r);
    g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r);
    g.arcTo(x, y, x + w, y, r);
    g.closePath();
  }
  function bottleLabel(title, color) {
    var c = document.createElement("canvas");
    c.width = 256; c.height = 256;
    var g = c.getContext("2d");
    g.fillStyle = "#f7f4ea";
    g.fillRect(0, 0, 256, 256);
    g.fillStyle = hexCss(color || 0x0f766e);
    g.fillRect(0, 0, 256, 18);
    g.fillRect(0, 238, 256, 18);
    g.fillStyle = "#1f2937";
    g.font = "700 36px sans-serif";
    g.textAlign = "center";
    g.textBaseline = "middle";
    wrapText(g, title || "试剂", 128, 128, 210, 40);
    var tex = new THREE.CanvasTexture(c);
    return new THREE.MeshStandardMaterial({ map: tex, roughness: 0.7 });
  }
  function wrapText(g, text, x, y, maxW, lh) {
    var line = "", lines = [], i;
    for (i = 0; i < text.length; i++) {
      var t = line + text[i];
      if (g.measureText(t).width > maxW && line) { lines.push(line); line = text[i]; }
      else line = t;
    }
    if (line) lines.push(line);
    var start = y - (lines.length - 1) * lh / 2;
    lines.forEach(function (ln, n) { g.fillText(ln, x, start + n * lh); });
  }

  function makeSlot(name, title, x, y, z, color) {
    var g = new THREE.Group();
    var col = color || 0x2dd4bf;
    var ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.16, 0.012, 10, 40),
      mat(col, { emissive: col, emissiveIntensity: 0.55, roughness: 0.25, transparent: true, opacity: 0.95 })
    );
    ring.rotation.x = Math.PI / 2;
    var pad = new THREE.Mesh(
      new THREE.CircleGeometry(0.16, 32),
      mat(col, { transparent: true, opacity: 0.16 })
    );
    pad.rotation.x = -Math.PI / 2;
    pad.position.y = 0.012;
    var diamond = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.055),
      mat(col, { emissive: col, emissiveIntensity: 0.9, roughness: 0.2 })
    );
    diamond.position.y = 0.52;
    var hit = new THREE.Mesh(
      new THREE.CylinderGeometry(0.22, 0.22, 0.7, 16),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    hit.position.y = 0.3;
    var lab = labelSprite(title, "#ecfeff");
    lab.position.set(0, 0.68, 0);
    g.add(ring, pad, diamond, hit, lab);
    g.position.set(x, y, z);
    g.userData = { slot: name, bob: Math.random() * 6, diamond: diamond, ring: ring };
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
    g.userData = g.userData || {};
    g.userData.baseY = y;
    pieces[id] = g;
    root.add(g);
    return g;
  }

  function buildStand(g, tilt) {
    var iron = mat(0x6b7280, { metalness: 0.82, roughness: 0.28 });
    var base = mat(0x4b5563, { metalness: 0.7, roughness: 0.4 });
    var screwMat = mat(0xd6d3d1, { metalness: 0.88, roughness: 0.22 });
    add(g, cyl(0.18, 0.22, 0.045, base), 0, 0.025, 0);
    add(g, cyl(0.026, 0.026, 0.78, iron), 0, 0.42, 0);
    add(g, box(0.48, 0.022, 0.028, iron), 0.18, 0.42, 0);
    add(g, box(0.045, 0.05, 0.045, iron), 0.43, 0.42, 0);
    if (tilt == null) {
      add(g, cyl(0.012, 0.012, 0.04, screwMat, 12), 0.43, 0.46, 0);
      return;
    }
    var axis = new THREE.Vector3(-Math.sin(tilt), Math.cos(tilt), 0).normalize();
    var holder = new THREE.Group();
    holder.position.set(0.46, 0.42, 0);
    holder.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), axis);
    var jaw = new THREE.Mesh(new THREE.TorusGeometry(0.07, 0.007, 8, 28, Math.PI * 1.45), iron);
    jaw.rotation.z = 0.9;
    holder.add(jaw);
    var screw = cyl(0.01, 0.01, 0.05, screwMat, 12);
    screw.position.y = 0.09;
    holder.add(screw);
    add(holder, cyl(0.016, 0.016, 0.012, screwMat, 12), 0, 0.112, 0);
    g.add(holder);
  }
  function buildTube(g, tilt) {
    /* 试管要看见管内的药品和棉花。全透射会把管里的物体折射掉，改成薄的半透明玻璃。 */
    var shell = glass(0xd4eaf8);
    shell.transmission = 0;
    shell.opacity = 0.28;
    shell.transparent = true;
    shell.depthWrite = false;
    shell.roughness = 0.06;
    shell.envMapIntensity = 0.35;
    shell.side = THREE.DoubleSide;
    shell.thickness = 0.012;
    /* 外壁上去、内壁回来，才是有壁厚的空心试管，而不是一整块玻璃。 */
    var body = lathe([
      [0.002, 0.016], [0.048, 0.02], [0.052, 0.07], [0.052, 0.49],
      [0.060, 0.515], [0.056, 0.532], [0.040, 0.532], [0.044, 0.50],
      [0.044, 0.09], [0.002, 0.055]
    ], shell, 48);
    add(g, body, 0, 0, 0);
    add(g, glassRim(0.056, 0.006), 0, 0.52, 0);
    var powder = sph(0.042, mat(0x1e293b, { roughness: 0.8 }), 12, 10);
    powder.scale.set(1, 0.45, 1);
    fx.powder = add(g, powder, 0, 0.08, 0);
    var copper = sph(0.038, mat(0xb45309, { roughness: 0.55, metalness: 0.45 }), 12, 10);
    copper.scale.set(1.15, 0.34, 0.9);
    fx.copper = add(g, copper, 0.012, 0.087, 0.005);
    var zinc = box(0.05, 0.028, 0.036, mat(0xa8b0bb, { metalness: 0.55, roughness: 0.35 }));
    fx.zinc = add(g, zinc, 0.01, 0.09, 0);
    var marble = sph(0.024, mat(0xf8fafc, { roughness: 0.45 }));
    fx.marble = add(g, marble, -0.01, 0.085, 0.01);
    var acid = cyl(0.048, 0.05, 0.18, liquidMat(0x38bdf8), 28);
    fx.acid = add(g, acid, 0, 0.16, 0);
    fx.tubeBubbles = [];
    for (var i = 0; i < 10; i++) {
      var b = sph(0.008 + Math.random() * 0.006, mat(0xffffff, { transparent: true, opacity: 0.7 }), 8, 6);
      b.visible = false;
      fx.tubeBubbles.push(add(g, b, (Math.random() - 0.5) * 0.06, 0.12 + Math.random() * 0.12, (Math.random() - 0.5) * 0.06));
    }
    powder.visible = copper.visible = zinc.visible = marble.visible = acid.visible = false;
    /* 管口内侧、橡皮塞之前。用哑光材质，白团才不会融进玻璃高光里。 */
    fx.cotton = add(g, sph(0.032, mat(0xfafafa, { roughness: 0.96 })), 0, 0.4, 0);
    fx.cotton.renderOrder = 4;
    fx.cotton.visible = false;
    if (tilt) g.rotation.z = tilt;
    fx.tube = g;
  }
  function buildLamp(g) {
    var ceramic = mat(0xd3542c, { roughness: 0.55 });
    add(g, lathe([
      [0.02, 0], [0.11, 0.008], [0.124, 0.032], [0.108, 0.07],
      [0.096, 0.15], [0.09, 0.185], [0.058, 0.218], [0.046, 0.242]
    ], ceramic, 36), 0, 0, 0);
    var brass = mat(0xb08d4e, { metalness: 0.78, roughness: 0.3 });
    add(g, cyl(0.06, 0.052, 0.02, brass, 24), 0, 0.252, 0);
    add(g, cyl(0.018, 0.018, 0.012, brass, 16), 0, 0.266, 0);
    add(g, cyl(0.007, 0.008, 0.042, mat(0xf3efe4, { roughness: 0.86 }), 10), 0, 0.286, 0);
    var outer = new THREE.Mesh(
      new THREE.ConeGeometry(0.04, 0.16, 18),
      mat(0xff6a12, { emissive: 0xff4d00, emissiveIntensity: 1.4, transparent: true, opacity: 0.88 })
    );
    var inner = new THREE.Mesh(
      new THREE.ConeGeometry(0.02, 0.1, 12),
      mat(0xfff4c2, { emissive: 0xffe08a, emissiveIntensity: 2, transparent: true, opacity: 0.95 })
    );
    fx.flame = add(g, outer, 0, 0.38, 0);
    fx.flameInner = add(g, inner, 0, 0.36, 0);
    var light = new THREE.PointLight(0xff8a3d, 0, 3.2);
    light.position.set(0, 0.42, 0);
    light.castShadow = false;
    g.add(light);
    fx.flameLight = light;
    outer.visible = inner.visible = false;
  }
  function buildClamp(g) {
    var steel = mat(0xb8c0cc, { metalness: 0.78, roughness: 0.22 });
    var grip = mat(0x1e3a5f, { roughness: 0.38, metalness: 0.15 });
    var handle = cyl(0.016, 0.018, 0.42, grip, 12);
    handle.rotation.z = 1.12;
    add(g, handle, 0.18, 0.32, 0);
    add(g, box(0.04, 0.03, 0.03, steel), 0.02, 0.34, 0);
    [[0.28, 0.07], [0.18, 0.062]].forEach(function (p) {
      var ring = new THREE.Mesh(new THREE.TorusGeometry(p[1], 0.009, 8, 24), steel);
      ring.rotation.y = Math.PI / 2;
      add(g, ring, 0, p[0], 0);
    });
    add(g, box(0.012, 0.12, 0.012, steel), 0.07, 0.23, 0);
  }
  function buildDeliveryPath(g, pts) {
    var glassMat = glass(0xd5e7f2);
    glassMat.thickness = 0.01;
    glassMat.roughness = 0.02;
    var vectors = pts.map(function (p) {
      return new THREE.Vector3(p[0], p[1], p[2]);
    });
    if (vectors.length < 2) return;
    var curve = new THREE.CatmullRomCurve3(vectors, false, "catmullrom", 0.2);
    var mesh = new THREE.Mesh(
      new THREE.TubeGeometry(curve, Math.max(32, vectors.length * 18), 0.0085, 8, false),
      glassMat
    );
    mesh.castShadow = true;
    g.add(mesh);
  }
  /* 导管画在世界坐标：起点从橡皮塞穿出，终点伸进集气瓶（瓶底或倒扣瓶口）。
     axisOut 是试管口朝外的方向，橡皮塞沿这个方向做成圆台。 */
  function hose(worldPts, axisOut) {
    return function (g) {
      var o = worldPts[0];
      var pts = worldPts.map(function (p) {
        return [p[0] - o[0], p[1] - o[1], p[2] - o[2]];
      });
      var axis = axisOut
        ? new THREE.Vector3(axisOut[0], axisOut[1], axisOut[2])
        : new THREE.Vector3(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1], pts[1][2] - pts[0][2]);
      if (axis.lengthSq() < 1e-8) axis.set(0, 1, 0);
      axis.normalize();
      var rubber = mat(0x6b2a14, { roughness: 0.84 });
      var stopper = cyl(0.064, 0.026, 0.082, rubber, 22);
      stopper.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), axis);
      /* 橡皮塞大部分留在管外，只有细端伸进管口，免得挡住管内的棉花。 */
      stopper.position.copy(axis.clone().multiplyScalar(0.02));
      g.add(stopper);
      buildDeliveryPath(g, pts);
    };
  }
  function buildTrough(g) {
    var plastic = mat(0x6f93ad, { roughness: 0.32, metalness: 0.06 });
    var rim = mat(0x8eacbf, { roughness: 0.22, metalness: 0.08 });
    add(g, box(1.15, 0.04, 0.62, plastic), 0, 0.02, 0);
    add(g, box(1.15, 0.2, 0.035, plastic), 0, 0.12, 0.292);
    add(g, box(1.15, 0.2, 0.035, plastic), 0, 0.12, -0.292);
    add(g, box(0.035, 0.2, 0.62, plastic), 0.557, 0.12, 0);
    add(g, box(0.035, 0.2, 0.62, plastic), -0.557, 0.12, 0);
    add(g, box(1.18, 0.025, 0.05, rim), 0, 0.22, 0.3);
    add(g, box(1.18, 0.025, 0.05, rim), 0, 0.22, -0.3);
    add(g, box(0.05, 0.025, 0.66, rim), 0.57, 0.22, 0);
    add(g, box(0.05, 0.025, 0.66, rim), -0.57, 0.22, 0);
    fx.troughWater = add(g, box(1.04, 0.08, 0.5, liquidMat(0x5aa4c4)), 0, 0.08, 0);
    var skin = new THREE.Mesh(
      new THREE.PlaneGeometry(1.02, 0.48),
      new THREE.MeshPhysicalMaterial({
        color: 0x8ec4d8, roughness: 0.05, metalness: 0.02,
        transparent: true, opacity: 0.2, envMapIntensity: 0.7
      })
    );
    skin.rotation.x = -Math.PI / 2;
    skin.castShadow = false;
    add(g, skin, 0, 0.125, 0);
  }
  function buildBottle(g) {
    var shell = glass(0xeef7f4);
    shell.side = THREE.DoubleSide;
    shell.thickness = 0.012;
    /* 广口集气瓶：直筒、平底、厚瓶口，没有瓶颈。 */
    add(g, lathe([
      [0.002, 0.01], [0.108, 0.012], [0.112, 0.026], [0.104, 0.04],
      [0.104, 0.43], [0.114, 0.45], [0.118, 0.462], [0.090, 0.462],
      [0.096, 0.438], [0.096, 0.04], [0.002, 0.028]
    ], shell, 48), 0, 0, 0);
    add(g, glassRim(0.104, 0.008), 0, 0.456, 0);
    fx.gas = add(g, cyl(0.088, 0.088, 0.1, mat(0xf8fafc, { transparent: true, opacity: 0.5 }), 16), 0, 0.26, 0);
    fx.bottleWater = add(g, cyl(0.09, 0.09, 0.05, liquidMat(0x38bdf8), 16), 0, 0.08, 0);
    fx.gas.visible = fx.bottleWater.visible = false;
    fx.bottle = g;
  }
  function buildInvBottle(g) {
    /* 口朝下的广口集气瓶：直筒，瓶口在水面下，瓶底朝上。 */
    var shell = glass(0xeef7f4);
    shell.side = THREE.DoubleSide;
    shell.thickness = 0.012;
    add(g, lathe([
      [0.118, 0.002], [0.112, 0.016], [0.104, 0.032], [0.104, 0.45],
      [0.108, 0.478], [0.002, 0.492], [0.002, 0.472], [0.096, 0.458],
      [0.096, 0.036], [0.090, 0.002]
    ], shell, 48), 0, 0, 0);
    add(g, glassRim(0.104, 0.008), 0, 0.01, 0);
    fx.gas = add(g, cyl(0.088, 0.088, 0.14, mat(0xf8fafc, { transparent: true, opacity: 0.5 }), 16), 0, 0.32, 0);
    fx.bottleWater = add(g, cyl(0.088, 0.09, 0.028, liquidMat(0x38bdf8), 20), 0, 0.03, 0);
    fx.gas.visible = fx.bottleWater.visible = false;
    fx.bottle = g;
  }
  function buildSplint(g) {
    add(g, box(0.022, 0.34, 0.022, mat(0xb45309, { roughness: 0.7 })), 0, 0.2, 0);
    fx.splintGlow = add(g, sph(0.038, mat(0xfbbf24, { emissive: 0xf59e0b, emissiveIntensity: 0.55 })), 0, 0.4, 0);
    fx.splintFlame = add(g, new THREE.Mesh(
      new THREE.ConeGeometry(0.035, 0.13, 14),
      mat(0xfff3a3, { emissive: 0xff8a00, emissiveIntensity: 1.8, transparent: true, opacity: 0.94 })
    ), 0, 0.48, 0);
    fx.splintFlame.visible = false;
  }
  function vesselMat() {
    var m = glass();
    m.side = THREE.DoubleSide;
    m.thickness = 0.02;
    m.roughness = 0.08;
    m.envMapIntensity = 0.28;
    return m;
  }
  function buildBeaker(g) {
    add(g, lathe([
      [0.002, 0.01], [0.175, 0.012], [0.188, 0.028], [0.18, 0.04],
      [0.18, 0.34], [0.198, 0.368], [0.168, 0.382], [0.172, 0.35],
      [0.172, 0.045], [0.002, 0.032]
    ], vesselMat(), 40), 0, 0, 0);
    add(g, glassRim(0.183, 0.007), 0, 0.372, 0);
    var spout = box(0.06, 0.03, 0.04, vesselMat());
    spout.rotation.z = -0.4;
    add(g, spout, 0.19, 0.37, 0);
    fx.liquid = add(g, cyl(0.165, 0.155, 0.14, liquidMat(0x7dd3fc), 28), 0, 0.12, 0);
    fx.metal = add(g, box(0.08, 0.028, 0.05, mat(0x94a3b8, { metalness: 0.55 })), 0, 0.14, 0);
    fx.metal.visible = false;
    fx.beakerBubbles = [];
    for (var i = 0; i < 12; i++) {
      var b = sph(0.01 + Math.random() * 0.008, mat(0xffffff, { transparent: true, opacity: 0.7 }), 8, 6);
      b.visible = false;
      fx.beakerBubbles.push(add(g, b, (Math.random() - 0.5) * 0.14, 0.1 + Math.random() * 0.1, (Math.random() - 0.5) * 0.14));
    }
  }
  function buildDropper(g) {
    add(g, sph(0.048, mat(0xef4444, { roughness: 0.45 })), 0, 0.24, 0);
    add(g, cyl(0.014, 0.014, 0.2, glass(0xe0f2fe), 14), 0, 0.1, 0);
    fx.drip = add(g, sph(0.014, liquidMat(0x38bdf8)), 0, 0, 0);
    fx.drip.visible = false;
  }
  function buildRod(g) {
    var m = cyl(0.011, 0.011, 0.46, glass(0xf1f5f9), 12);
    m.rotation.z = 0.42;
    add(g, m, 0.1, 0.24, 0);
  }
  function buildGoggles(g) {
    add(g, box(0.3, 0.07, 0.07, mat(0x134e4a, { roughness: 0.4 })), 0, 0.18, 0);
    add(g, sph(0.046, glass(0xffffff)), -0.07, 0.18, 0.03);
    add(g, sph(0.046, glass(0xffffff)), 0.07, 0.18, 0.03);
  }
  function buildFunnel(g) {
    var bowl = new THREE.Mesh(new THREE.ConeGeometry(0.18, 0.22, 28, 1, true), glass(0xdbeafe));
    bowl.rotation.x = Math.PI;
    add(g, bowl, 0, 0.42, 0);
    add(g, glassRim(0.18, 0.007), 0, 0.53, 0);
    add(g, cyl(0.02, 0.02, 0.18, vesselMat(), 16), 0, 0.22, 0);
    var paper = new THREE.Mesh(new THREE.ConeGeometry(0.15, 0.16, 18, 1, true), mat(0xf8fafc, { transparent: true, opacity: 0.88 }));
    paper.rotation.x = Math.PI;
    fx.filterPaper = add(g, paper, 0, 0.44, 0);
    fx.residue = add(g, sph(0.05, mat(0xa8a29e, { roughness: 0.8 })), 0, 0.46, 0);
    fx.filterPaper.visible = fx.residue.visible = false;
  }
  function buildPaper(g) {
    fx.testPaper = add(g, box(0.16, 0.004, 0.22, mat(0xfca5a5, { roughness: 0.9 })), 0, 0.02, 0);
  }
  function buildSpoon(g) {
    var steel = mat(0xcbd5e1, { metalness: 0.72, roughness: 0.24 });
    var handle = cyl(0.009, 0.009, 0.36, steel, 10);
    handle.rotation.z = Math.PI / 2;
    add(g, handle, 0.16, 0.12, 0);
    var bowl = sph(0.052, steel, 20, 12);
    bowl.scale.set(1.25, 0.3, 0.8);
    add(g, bowl, -0.04, 0.12, 0);
  }
  function buildTweezers(g) {
    var steel = mat(0xb8c0cc, { metalness: 0.78, roughness: 0.22 });
    [-1, 1].forEach(function (side) {
      var arm = box(0.42, 0.012, 0.018, steel);
      arm.rotation.z = side * 0.07;
      add(g, arm, 0.16, 0.13 + side * 0.018, 0);
    });
    add(g, box(0.06, 0.045, 0.026, steel), -0.04, 0.13, 0);
  }
  function buildCotton(g) {
    var cotton = new THREE.Group();
    for (var i = 0; i < 7; i++) {
      add(cotton, sph(0.035, mat(0xffffff, { roughness: 0.95 }), 12, 8),
        (i % 3 - 1) * 0.035, 0.04 + Math.floor(i / 3) * 0.025, (i % 2) * 0.025);
    }
    g.add(cotton);
  }
  /* 塞进试管口的小团棉花，直径要小于试管，挡在橡皮塞内侧。 */
  function buildCottonPlug(g) {
    /* 疏松小团收在试管内径里，略深于管口，让橡皮塞留在它外侧。 */
    var fluff = mat(0xfafafa, { roughness: 0.96 });
    var shade = mat(0xd6d3d1, { roughness: 1 });
    [[0, 0, 0, 0.032, fluff], [-0.01, 0.01, 0.004, 0.014, shade],
      [0.011, -0.008, -0.003, 0.013, fluff], [0, 0.004, -0.008, 0.011, shade]].forEach(function (p) {
      add(g, sph(p[3], p[4], 12, 8), p[0], p[1], p[2]);
    });
  }
  function buildTestTube(g) {
    add(g, lathe([
      [0.002, 0.014], [0.04, 0.016], [0.044, 0.05], [0.044, 0.37],
      [0.052, 0.392], [0.034, 0.404], [0.036, 0.37], [0.036, 0.06], [0.002, 0.04]
    ], vesselMat(), 32), 0, 0, 0);
    add(g, glassRim(0.046, 0.005), 0, 0.394, 0);
  }
  function buildAbsorber(g) {
    add(g, lathe([
      [0.002, 0.01], [0.12, 0.012], [0.128, 0.03], [0.12, 0.28],
      [0.06, 0.35], [0.055, 0.44], [0.064, 0.458], [0.042, 0.458],
      [0.046, 0.36], [0.1, 0.28], [0.1, 0.04], [0.002, 0.03]
    ], vesselMat(), 36), 0, 0, 0);
    add(g, glassRim(0.055, 0.005), 0, 0.45, 0);
    add(g, cyl(0.105, 0.11, 0.12, liquidMat(0x93c5fd), 20), 0, 0.09, 0);
  }
  function buildSpringClamp(g) {
    var steel = mat(0x94a3b8, { metalness: 0.8, roughness: 0.24 });
    add(g, box(0.18, 0.025, 0.035, steel), 0, 0.1, 0);
    var a = box(0.13, 0.018, 0.025, steel); a.rotation.z = 0.28; add(g, a, -0.08, 0.13, 0);
    var b = box(0.13, 0.018, 0.025, steel); b.rotation.z = -0.28; add(g, b, 0.08, 0.13, 0);
    add(g, new THREE.Mesh(new THREE.TorusGeometry(0.035, 0.008, 8, 18), steel), 0, 0.1, 0);
  }
  function buildConicalFlask(g) {
    add(g, lathe([
      [0.002, 0.012], [0.19, 0.02], [0.2, 0.05], [0.14, 0.32],
      [0.058, 0.46], [0.052, 0.56], [0.06, 0.578], [0.04, 0.578],
      [0.044, 0.46], [0.12, 0.32], [0.17, 0.06], [0.002, 0.04]
    ], vesselMat(), 40), 0, 0, 0);
    add(g, glassRim(0.052, 0.005), 0, 0.57, 0);
    fx.massLiquid = add(g, cyl(0.13, 0.17, 0.12, liquidMat(0x2563eb), 24), 0, 0.1, 0);
    fx.massLiquid.visible = false;
    var inner = new THREE.Group();
    add(inner, cyl(0.038, 0.038, 0.25, glass(0xdbeafe), 16), 0, 0.14, 0);
    fx.innerLiquid = add(inner, cyl(0.031, 0.031, 0.1, liquidMat(0x2563eb), 14), 0, 0.08, 0);
    inner.rotation.z = -0.48;
    inner.position.set(0.03, 0.23, 0);
    g.add(inner);
    add(g, cyl(0.062, 0.04, 0.06, mat(0x6b2a14, { roughness: 0.84 }), 18), 0, 0.6, 0);
    fx.massIron = add(g, box(0.025, 0.19, 0.025, mat(0x94a3b8, { metalness: 0.68 })), -0.1, 0.16, 0);
    fx.massCopper = add(g, box(0.034, 0.11, 0.032, mat(0xb45309, { metalness: 0.48 })), -0.1, 0.13, 0.002);
    fx.massCopper.visible = false;
  }
  function buildIndicatorSet(g) {
    function cup(x, z, label) {
      var cupGroup = new THREE.Group();
      add(cupGroup, lathe([
        [0.002, 0.008], [0.082, 0.01], [0.09, 0.024], [0.086, 0.24],
        [0.096, 0.262], [0.074, 0.27], [0.076, 0.24], [0.076, 0.03], [0.002, 0.022]
      ], vesselMat(), 28), 0, 0, 0);
      add(cupGroup, glassRim(0.086, 0.005), 0, 0.264, 0);
      var liq = add(cupGroup, cyl(0.077, 0.075, 0.1, liquidMat(0x7dd3fc), 18), 0, 0.08, 0);
      var lab = labelSprite(label, "#e2e8f0"); lab.scale.set(0.38, 0.1, 1); lab.position.set(0, 0.34, 0);
      cupGroup.add(lab); cupGroup.position.set(x, 0, z); g.add(cupGroup);
      return liq;
    }
    fx.indAcidLitmus = cup(-0.42, 0, "盐酸+石蕊");
    fx.indBaseLitmus = cup(-0.14, 0, "碱+石蕊");
    fx.indAcidPhen = cup(0.18, 0, "盐酸+酚酞");
    fx.indBasePhen = cup(0.46, 0, "碱+酚酞");
  }
  function buildBurnSpoon(g, substance) {
    buildSpoon(g);
    var sampleColor = substance === "sulfur" ? 0xeab308 : (substance === "phosphorus" ? 0xdc2626 : 0x1e293b);
    fx.burnSample = add(g, sph(0.035, mat(sampleColor, { roughness: 0.8 })),
      -0.04, 0.145, 0);
    fx.burnFlame = add(g, new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.18, 18),
      mat(0x60a5fa, { emissive: 0x3b82f6, emissiveIntensity: 2, transparent: true, opacity: 0.92 })),
      -0.04, 0.25, 0);
    fx.burnFlame.visible = false;
  }
  function buildDish(g) {
    var porcelain = mat(0xf4f4f5, { roughness: 0.38, metalness: 0.02 });
    add(g, lathe([
      [0.03, 0.008], [0.16, 0.012], [0.205, 0.03], [0.19, 0.062], [0.16, 0.072], [0.14, 0.05]
    ], porcelain, 36), 0, 0, 0);
    fx.dishLiquid = add(g, cyl(0.15, 0.14, 0.022, liquidMat(0x7dd3fc), 20), 0, 0.04, 0);
    fx.crystals = new THREE.Group();
    for (var i = 0; i < 7; i++) {
      var c = box(0.028, 0.022, 0.028, mat(0xe0f2fe, { roughness: 0.25 }));
      c.position.set((i % 3 - 1) * 0.05, 0.055, (i < 3 ? -0.035 : 0.035));
      c.rotation.y = i * 0.7;
      fx.crystals.add(c);
    }
    fx.crystals.visible = false;
    g.add(fx.crystals);
  }
  function buildGauze(g) {
    var iron = mat(0x9ca3af, { metalness: 0.72, roughness: 0.32 });
    var ring = new THREE.Mesh(new THREE.RingGeometry(0.15, 0.2, 28), iron);
    ring.rotation.x = -Math.PI / 2;
    add(g, ring, 0, 0.02, 0);
    add(g, cyl(0.145, 0.145, 0.012, mat(0xe7e5e4, { roughness: 0.72 }), 28), 0, 0.02, 0);
  }
  function buildCell(g) {
    var plastic = mat(0x6f93ad, { roughness: 0.32, metalness: 0.06 });
    var rim = mat(0x8eacbf, { roughness: 0.22, metalness: 0.08 });
    add(g, box(1.46, 0.04, 0.74, plastic), 0, 0.02, 0);
    add(g, box(1.46, 0.2, 0.03, plastic), 0, 0.13, 0.355);
    add(g, box(1.46, 0.2, 0.03, plastic), 0, 0.13, -0.355);
    add(g, box(0.03, 0.2, 0.74, plastic), 0.715, 0.13, 0);
    add(g, box(0.03, 0.2, 0.74, plastic), -0.715, 0.13, 0);
    add(g, box(1.5, 0.02, 0.045, rim), 0, 0.23, 0.36);
    add(g, box(1.5, 0.02, 0.045, rim), 0, 0.23, -0.36);
    add(g, box(1.36, 0.08, 0.64, liquidMat(0x5aa4c4)), 0, 0.08, 0);
    add(g, box(0.04, 0.28, 0.04, mat(0x1d4ed8, { metalness: 0.6 })), -0.35, 0.2, 0);
    add(g, box(0.04, 0.28, 0.04, mat(0xdc2626, { metalness: 0.6 })), 0.35, 0.2, 0);
  }
  function buildPower(g) {
    add(g, box(0.38, 0.16, 0.22, mat(0x111827, { roughness: 0.38 })), 0, 0.2, 0);
    add(g, sph(0.028, mat(0xdc2626, { roughness: 0.3 })), -0.12, 0.22, 0.12);
    add(g, sph(0.028, mat(0x1d4ed8, { roughness: 0.3 })), 0.12, 0.22, 0.12);
    var pos = labelSprite("+", "#fecaca");
    pos.scale.set(0.28, 0.08, 1);
    pos.position.set(-0.12, 0.34, 0.14);
    var neg = labelSprite("−", "#bfdbfe");
    neg.scale.set(0.28, 0.08, 1);
    neg.position.set(0.12, 0.34, 0.14);
    g.add(pos, neg);
  }
  function buildTubes(g) {
    function gasTube(x) {
      var shell = lathe([
        [0.058, 0.0], [0.05, 0.02], [0.046, 0.28], [0.002, 0.3],
        [0.002, 0.275], [0.038, 0.26], [0.038, 0.03], [0.046, 0.0]
      ], vesselMat(), 28);
      add(g, shell, x, 0.29, 0);
      add(g, glassRim(0.052, 0.005), x, 0.3, 0);
    }
    gasTube(-0.35);
    gasTube(0.35);
    fx.h2gas = add(g, cyl(0.042, 0.042, 0.18, mat(0xe0f2fe, { transparent: true, opacity: 0.55 }), 16), -0.35, 0.48, 0);
    fx.o2gas = add(g, cyl(0.042, 0.042, 0.09, mat(0xffedd5, { transparent: true, opacity: 0.55 }), 16), 0.35, 0.40, 0);
    fx.h2gas.visible = fx.o2gas.visible = false;
    fx.h2 = labelSprite("− H₂", "#99f6e4"); fx.o2 = labelSprite("+ O₂", "#fdba74");
    fx.h2.position.set(-0.35, 0.68, 0.08); fx.o2.position.set(0.35, 0.68, 0.08);
    fx.h2.visible = fx.o2.visible = false;
    g.add(fx.h2, fx.o2);
    fx.ratio = labelSprite("H₂ : O₂ ≈ 2 : 1", "#99f6e4");
    fx.ratio.scale.set(1.2, 0.22, 1);
    fx.ratio.position.set(0, 0.1, 0.45);
    fx.ratio.visible = false;
    g.add(fx.ratio);
  }
  function buildBalance(g) {
    add(g, box(0.44, 0.035, 0.16, mat(0x78716c, { metalness: 0.4 })), 0, 0.08, 0);
    add(g, box(0.035, 0.16, 0.035, mat(0x57534e)), 0, 0.16, 0);
    add(g, cyl(0.08, 0.08, 0.018, mat(0xa8a29e, { metalness: 0.5 }), 20), -0.16, 0.1, 0);
    add(g, cyl(0.08, 0.08, 0.018, mat(0xa8a29e, { metalness: 0.5 }), 20), 0.16, 0.1, 0);
  }
  function buildCylinder(g) {
    add(g, lathe([
      [0.002, 0.008], [0.068, 0.01], [0.072, 0.39], [0.082, 0.41],
      [0.055, 0.424], [0.06, 0.39], [0.06, 0.03], [0.002, 0.024]
    ], vesselMat(), 32), 0, 0, 0);
    add(g, glassRim(0.074, 0.005), 0, 0.412, 0);
  }
  function buildReagent(g, color, title) {
    var col = color || 0x7c3aed;
    add(g, lathe([
      [0.002, 0.008], [0.055, 0.01], [0.06, 0.03], [0.05, 0.17],
      [0.03, 0.21], [0.028, 0.25], [0.034, 0.262], [0.022, 0.262],
      [0.024, 0.21], [0.042, 0.17], [0.046, 0.04], [0.002, 0.028]
    ], vesselMat(), 28), 0, 0, 0);
    var fill = cyl(0.045, 0.048, 0.12, liquidMat(col), 20);
    add(g, fill, 0, 0.08, 0);
    add(g, cyl(0.03, 0.03, 0.04, mat(0x44403c, { roughness: 0.5 })), 0, 0.27, 0);
    var lab = new THREE.Mesh(new THREE.PlaneGeometry(0.08, 0.08), bottleLabel(title || "药品", col));
    lab.position.set(0, 0.1, 0.056);
    g.add(lab);
  }
  /* 螺旋铁丝从瓶口垂下，下端系火柴，伸到瓶底水层上方。 */
  function buildWire(g) {
    var pts = [new THREE.Vector3(0, 0.62, 0)];
    var top = 0.42, bot = 0.16, turns = 4.5, n = 64;
    for (var i = 0; i <= n; i++) {
      var t = i / n;
      var ang = t * turns * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(ang) * 0.036, top - t * (top - bot), Math.sin(ang) * 0.036));
    }
    g.add(new THREE.Mesh(
      new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 96, 0.006, 6, false),
      mat(0x94a3b8, { metalness: 0.75, roughness: 0.28 })
    ));
    add(g, cyl(0.005, 0.005, 0.04, mat(0xf5f0e6, { roughness: 0.75 }), 8), 0, bot - 0.02, 0);
    add(g, sph(0.016, mat(0xb91c1c, { roughness: 0.5 })), 0, bot - 0.045, 0);
  }
  function buildCover(g) {
    add(g, cyl(0.14, 0.14, 0.016, glass(0xe2e8f0), 24), 0, 0.02, 0);
  }
  function buildCandleBeaker(g) {
    add(g, lathe([
      [0.002, 0.012], [0.24, 0.014], [0.26, 0.03], [0.25, 0.5],
      [0.28, 0.53], [0.23, 0.545], [0.24, 0.5], [0.24, 0.04], [0.002, 0.03]
    ], vesselMat(), 40), 0, 0, 0);
    add(g, glassRim(0.255, 0.008), 0, 0.532, 0);
    function candle(x, h, flameKey) {
      add(g, cyl(0.032, 0.034, h, mat(0xf8fafc, { roughness: 0.7 }), 12), x, h / 2 + 0.02, 0);
      add(g, cyl(0.004, 0.004, 0.028, mat(0x44403c), 6), x, h + 0.03, 0);
      var flame = add(g, sph(0.024, mat(0xf97316, { emissive: 0xea580c, emissiveIntensity: 0.85 })), x, h + 0.07, 0);
      var inner = add(g, sph(0.012, mat(0xfde68a, { emissive: 0xfacc15, emissiveIntensity: 0.9 })), x, h + 0.065, 0);
      flame.visible = inner.visible = false;
      fx[flameKey] = flame;
      fx[flameKey + "Inner"] = inner;
    }
    candle(-0.09, 0.16, "flameLow");
    candle(0.1, 0.32, "flameHigh");
    fx.co2Low = add(g, cyl(0.24, 0.23, 0.12, mat(0x64748b, { transparent: true, opacity: 0.32 }), 20), 0, 0.08, 0);
    fx.co2Mid = add(g, cyl(0.24, 0.23, 0.26, mat(0x94a3b8, { transparent: true, opacity: 0.28 }), 20), 0, 0.16, 0);
    fx.co2Low.visible = fx.co2Mid.visible = false;
    var lo = labelSprite("较低处", "#334155");
    lo.scale.set(0.42, 0.1, 1);
    lo.position.set(-0.09, 0.04, 0.28);
    var hi = labelSprite("较高处", "#334155");
    hi.scale.set(0.42, 0.1, 1);
    hi.position.set(0.1, 0.04, 0.28);
    g.add(lo, hi);
  }
  function buildConditionBeaker(g) {
    add(g, lathe([
      [0.002, 0.012], [0.24, 0.014], [0.26, 0.03], [0.25, 0.5],
      [0.28, 0.53], [0.23, 0.545], [0.24, 0.5], [0.24, 0.04], [0.002, 0.03]
    ], vesselMat(), 40), 0, 0, 0);
    add(g, glassRim(0.255, 0.008), 0, 0.532, 0);
    fx.hotWater = add(g, cyl(0.24, 0.23, 0.28, liquidMat(0xfb923c), 20), 0, 0.16, 0);
    add(g, box(0.5, 0.012, 0.28, mat(0xb45309, { metalness: 0.45 })), 0, 0.34, 0);
    fx.wpAir = add(g, sph(0.03, mat(0xf8fafc)), -0.12, 0.38, 0);
    fx.flameWp = add(g, sph(0.022, mat(0xf97316, { emissive: 0xea580c, emissiveIntensity: 0.85 })), -0.12, 0.44, 0);
    fx.rpAir = add(g, sph(0.03, mat(0xdc2626)), 0.12, 0.38, 0);
    fx.wpWater = add(g, sph(0.028, mat(0xf8fafc)), 0, 0.12, 0);
    fx.wpO2 = add(g, sph(0.02, mat(0xf97316, { emissive: 0xea580c, emissiveIntensity: 0.7 })), 0, 0.2, 0);
    fx.hotWater.visible = fx.wpAir.visible = fx.flameWp.visible = fx.rpAir.visible = fx.wpWater.visible = fx.wpO2.visible = false;
  }
  function buildRustTubes(g) {
    function tube(x, label, withWater, oil) {
      var shell = lathe([
        [0.002, 0.012], [0.048, 0.014], [0.05, 0.4], [0.058, 0.418],
        [0.04, 0.43], [0.042, 0.39], [0.042, 0.04], [0.002, 0.03]
      ], vesselMat(), 24);
      add(g, shell, x, 0, 0);
      add(g, glassRim(0.052, 0.004), x, 0.418, 0);
      if (withWater) add(g, cyl(0.04, 0.04, 0.16, liquidMat(0x38bdf8), 16), x, 0.1, 0);
      if (oil) add(g, cyl(0.04, 0.04, 0.03, liquidMat(0xca8a04), 16), x, 0.2, 0);
      var nail = add(g, box(0.018, 0.12, 0.018, mat(0x94a3b8, { metalness: 0.55 })), x, 0.12, 0);
      if (label === "水+空气") fx.rustNail = nail;
      var t = labelSprite(label, "#334155");
      t.scale.set(0.5, 0.12, 1);
      t.position.set(x, 0.02, 0.12);
      g.add(t);
    }
    tube(-0.28, "水+空气", true, false);
    tube(0, "油封隔空气", true, true);
    tube(0.28, "干燥剂", false, false);
  }

  function buildLime(g) {
    add(g, lathe([
      [0.002, 0.01], [0.15, 0.012], [0.162, 0.026], [0.155, 0.28],
      [0.172, 0.308], [0.145, 0.322], [0.148, 0.29], [0.148, 0.04], [0.002, 0.028]
    ], vesselMat(), 40), 0, 0, 0);
    add(g, glassRim(0.16, 0.006), 0, 0.312, 0);
    var spout = box(0.055, 0.024, 0.036, vesselMat());
    spout.rotation.z = -0.4;
    add(g, spout, 0.175, 0.31, 0);
    fx.limeLiquid = add(g, cyl(0.148, 0.138, 0.12, liquidMat(0xe8f1f8), 20), 0, 0.1, 0);
  }

  function tileFloor() {
    var geo = new THREE.PlaneGeometry(18, 18, 18, 18);
    var pos = geo.attributes.position;
    var colors = [];
    for (var i = 0; i < pos.count; i++) {
      var x = pos.getX(i), y = pos.getY(i);
      var odd = (Math.floor(x + 9) + Math.floor(y + 9)) % 2;
      var c = odd ? 0.16 : 0.13;
      colors.push(c, c + 0.01, c + 0.03);
    }
    geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    var mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      vertexColors: true, roughness: 0.88, metalness: 0.04
    }));
    mesh.rotation.x = -Math.PI / 2;
    mesh.receiveShadow = true;
    return mesh;
  }

  function buildRoom() {
    root = new THREE.Group();
    scene.add(root);
    add(root, tileFloor(), 0, 0, 0);
    var wall = mat(0xd7e3ee, { roughness: 0.9 });
    add(root, box(14, 5.2, 0.12, wall), 0, 2.5, -3.4);
    add(root, box(0.12, 5.2, 8, wall), -5.4, 2.5, 0);
    add(root, box(0.12, 5.2, 8, wall), 5.4, 2.5, 0);
    var win = box(2.6, 1.55, 0.04, mat(0x9ecfff, { roughness: 0.08, metalness: 0.15, transparent: true, opacity: 0.55 }));
    add(root, win, 1.5, 2.85, -3.33);
    add(root, box(2.76, 0.06, 0.08, mat(0xf8fafc)), 1.5, 3.64, -3.32);
    add(root, box(2.76, 0.06, 0.08, mat(0xf8fafc)), 1.5, 2.06, -3.32);
    var cabinet = mat(0x3f4a57, { roughness: 0.48, metalness: 0.12 });
    add(root, box(3.4, 1.7, 0.42, cabinet), -2.6, 2.55, -3.12);
    add(root, box(1.5, 0.62, 0.03, glass(0xcfe8ff)), -3.35, 2.7, -2.9);
    add(root, box(1.5, 0.62, 0.03, glass(0xcfe8ff)), -1.85, 2.7, -2.9);
    [[-3.4, 0x7c3aed], [-3.05, 0x16a34a], [-2.7, 0xdc2626], [-2.35, 0x0284c7], [-2.0, 0xd97706]].forEach(function (b) {
      add(root, cyl(0.045, 0.05, 0.16 + Math.random() * 0.06, mat(b[1], { roughness: 0.35 })), b[0], 2.05, -2.88);
    });
    var epoxy = mat(0x4a545f, { roughness: 0.34, metalness: 0.16 });
    add(root, box(5.4, 0.12, 2.2, epoxy), 0, 0.98, 0.05);
    add(root, box(5.5, 0.06, 0.08, mat(0x1c2128, { roughness: 0.5 })), 0, 0.92, 1.14);
    var oak = mat(0x6b4a2b, { roughness: 0.62 });
    [[-2.4, 0.9], [2.4, 0.9], [-2.4, -0.8], [2.4, -0.8]].forEach(function (p) {
      add(root, box(0.12, 0.92, 0.12, oak), p[0], 0.46, p[1]);
    });
    add(root, box(5.3, 0.7, 2.05, mat(0x3b2a1a, { roughness: 0.7 })), 0, 0.35, 0.05);
    var led = box(3.2, 0.03, 0.06, mat(0xf8fafc, { emissive: 0xf1f5ff, emissiveIntensity: 1.4 }));
    add(root, led, -2.4, 3.38, -2.88);
    add(root, cyl(0.05, 0.05, 0.08, mat(0x94a3b8, { metalness: 0.6 })), 2.25, 1.08, 0.9);
    add(root, cyl(0.012, 0.012, 0.12, mat(0xcbd5e1, { metalness: 0.7 })), 2.25, 1.18, 0.9);
  }

  function makeFx(kind) {
    fx.bubbles = [];
    for (var i = 0; i < 12; i++) {
      var b = sph(0.014, mat(0xffffff, { transparent: true, opacity: 0.75 }), 8, 6);
      b.visible = false;
      fx.bubbles.push(add(root, b, 1.0, 1.2, 0.2));
    }
    fx.sparks = [];
    for (i = 0; i < 8; i++) {
      var s = sph(0.012, mat(0xf97316, { emissive: 0xf97316, emissiveIntensity: 0.9 }), 8, 6);
      s.visible = false;
      fx.sparks.push(add(root, s, 1.1, 1.4, 0));
    }
    fx.smoke = [];
    for (i = 0; i < 10; i++) {
      var sm = sph(0.035 + (i % 3) * 0.008,
        mat(0xffffff, { transparent: true, opacity: 0.34, roughness: 1 }), 10, 8);
      sm.visible = false;
      fx.smoke.push(add(root, sm, 0.05 + (i % 2) * 0.03, 1.48 + (i % 5) * 0.06, 0.06));
    }
    fx.charcoalLight = new THREE.PointLight(0xffffff, 0, 2.8);
    fx.charcoalLight.position.set(0.05, 1.55, 0.06);
    root.add(fx.charcoalLight);
    fx.jet = new THREE.Mesh(new THREE.ConeGeometry(0.03, 0.12, 10), mat(0x38bdf8, { emissive: 0x38bdf8, emissiveIntensity: 0.6 }));
    fx.jet.position.set(-0.55, 1.45, 0.1);
    fx.jet.visible = false;
    root.add(fx.jet);
    fx.pop = labelSprite("爆鸣！", "#fecaca");
    fx.pop.scale.set(0.95, 0.28, 1);
    fx.pop.position.set(1.6, 1.7, -0.2);
    fx.pop.visible = false;
    root.add(fx.pop);
    if (kind === "evaporation") {
      fx.steam = [];
      for (i = 0; i < 8; i++) {
        var st = sph(0.03, mat(0xcbd5e1, { transparent: true, opacity: 0.32 }), 8, 6);
        st.visible = false;
        fx.steam.push(add(root, st, (i - 3) * 0.05, 1.78, 0.05));
      }
    }
    fx.stream = cyl(0.012, 0.008, 0.32, liquidMat(0x7dd3fc), 10);
    fx.stream.visible = false;
    root.add(fx.stream);
    fx.pourer = new THREE.Group();
    buildReagent(fx.pourer, 0x38bdf8, "加入");
    fx.pourer.visible = false;
    root.add(fx.pourer);
  }

  function layout(kind, expId) {
    var y = 1.05;
    var id = expId || kind || "oxygen";
    function S(name, title, x, z, c) { makeSlot(name, title, x, y, z, c || 0x2dd4bf); }
    function placeHose(hid, pts, axis) {
      var o = pts[0];
      var mid = pts[Math.floor(pts.length / 2)];
      S(hid, "导管", mid[0], mid[2], 0x94a3b8);
      pieceGroup(hid, hose(pts, axis), o[0], o[1], o[2]);
    }
    function mouthAxis(tilt) {
      return [-Math.sin(tilt), Math.cos(tilt), 0];
    }
    function invertBottle(g) {
      buildInvBottle(g);
    }
    function tiltTube(angle) {
      return function (g) {
        buildTube(g, angle);
        g.userData.tilt0 = angle;
      };
    }
    var L = {
      prep_oxygen_kmno4: function () {
        /* 固体加热：灯在闭口端下，试管口略向下，导管通入水槽倒扣集气瓶。 */
        var sx = -1.65, sz = 0;
        var clampX = sx + 0.46, clampY = y + 0.42;
        var tilt = -1.66;
        var tx = clampX - 0.28, ty = clampY - 0.006, tz = sz;
        var mouth = [tx + 0.53, ty - 0.047, tz];
        var troughX = 0.22, troughZ = 0.08;
        fx.collectAt = { x: troughX, y: 1.18, z: troughZ };
        S("stand", "铁架台", sx, sz);
        S("tube", "试管", tx, tz, 0x38bdf8);
        S("lamp", "酒精灯", tx + 0.02, 0.08, 0xf59e0b);
        S("trough", "水槽", troughX, 0.22, 0x0ea5e9);
        S("bottle", "集气瓶", troughX, -0.2, 0x38bdf8);
        S("splint", "木条", 1.45, -0.28, 0xf59e0b);
        /* 药匙放在台面左前角，不要搁在酒精灯和水槽之间，避免看成棉花。 */
        S("spoon", "药匙", -2.15, 0.62, 0xcbd5e1);
        /* 棉花在试管口内侧、橡皮塞之前。 */
        var cottonAt = 0.46;
        S("cotton", "棉花", tx - Math.sin(tilt) * cottonAt, tz, 0xf8fafc);
        S("reagent", "药品", sx, -0.38, 0xa78bfa);
        pieceGroup("stand", function (g) { buildStand(g, tilt); }, sx, y, sz);
        pieceGroup("tube", tiltTube(tilt), tx, ty, tz);
        pieceGroup("lamp", buildLamp, tx + 0.02, y, 0.08);
        placeHose("delivery", [
          mouth,
          [mouth[0] + 0.48, mouth[1] - 0.02, 0.02],
          [troughX - 0.42, 1.17, troughZ],
          [troughX - 0.05, 1.185, troughZ],
          [troughX, 1.21, troughZ]
        ], mouthAxis(tilt));
        pieceGroup("trough", buildTrough, troughX, y, troughZ);
        pieceGroup("bottle", invertBottle, troughX, y + 0.12, troughZ);
        pieceGroup("splint", buildSplint, 1.45, y, -0.28);
        var spoon = pieceGroup("spoon", buildSpoon, -2.15, y, 0.62);
        spoon.rotation.y = 0.8;
        var plug = new THREE.Group();
        buildCottonPlug(plug);
        /* 管轴上、距管口约两厘米的内侧。z 必须是 0，否则会鼓出玻璃。 */
        plug.position.set(0, 0.4, 0);
        plug.visible = false;
        fx.tube.add(plug);
        pieces.cotton = plug;
        plug.name = "cotton-plug";
      },
      nh4hco3_decomp: function () {
        var sx = -1.45, sz = 0;
        var clampX = sx + 0.46, clampY = y + 0.42;
        var tilt = -1.66;
        var tx = clampX - 0.28, ty = clampY - 0.006, tz = sz;
        var mouth = [tx + 0.53, ty - 0.047, tz];
        S("stand", "铁架台", sx, sz);
        S("tube", "试管", tx, tz, 0x38bdf8);
        S("lamp", "酒精灯", tx + 0.02, 0.08, 0xf59e0b);
        S("paper", "试纸", mouth[0] + 0.08, -0.12, 0xf87171);
        S("lime_beaker", "石灰水", mouth[0] + 0.38, 0.08, 0x94a3b8);
        S("reagent", "药品", sx, -0.38, 0xa78bfa);
        pieceGroup("stand", function (g) { buildStand(g, tilt); }, sx, y, sz);
        pieceGroup("tube", tiltTube(tilt), tx, ty, tz);
        pieceGroup("lamp", buildLamp, tx + 0.02, y, 0.08);
        pieceGroup("paper", buildPaper, mouth[0] + 0.08, y + 0.08, -0.12);
        pieceGroup("lime_beaker", buildLime, mouth[0] + 0.38, y, 0.08);
        placeHose("delivery", [
          mouth,
          [mouth[0] + 0.2, mouth[1] - 0.02, 0.03],
          [mouth[0] + 0.38, y + 0.24, 0.08],
          [mouth[0] + 0.38, y + 0.08, 0.08]
        ], mouthAxis(tilt));
      },
      prep_hydrogen: function () {
        /* 固液不加热：试管直立夹在铁架台，导管通入水槽倒扣集气瓶。 */
        var sx = -1.55, sz = 0;
        var tubeX = sx + 0.46;
        var mouth = [tubeX, y + 0.53, sz];
        var troughX = 0.22, troughZ = 0.08;
        fx.collectAt = { x: troughX, y: 1.18, z: troughZ };
        S("stand", "铁架台", sx, sz);
        S("tube", "试管", tubeX, sz, 0x38bdf8);
        S("trough", "水槽", troughX, 0.22, 0x0ea5e9);
        S("bottle", "集气瓶", troughX, -0.2, 0x38bdf8);
        S("splint", "木条", 1.4, -0.28, 0xf59e0b);
        S("test_tube", "验纯试管", 1.08, 0.12, 0x38bdf8);
        S("reagent", "药品", sx, -0.38, 0xa78bfa);
        pieceGroup("stand", function (g) { buildStand(g, 0); }, sx, y, sz);
        pieceGroup("tube", tiltTube(0), tubeX, y, sz);
        placeHose("delivery", [
          mouth,
          [mouth[0] + 0.4, mouth[1] - 0.02, 0.02],
          [troughX - 0.42, 1.17, troughZ],
          [troughX - 0.05, 1.185, troughZ],
          [troughX, 1.21, troughZ]
        ], [0, 1, 0]);
        pieceGroup("trough", buildTrough, troughX, y, troughZ);
        pieceGroup("bottle", invertBottle, troughX, y + 0.12, troughZ);
        pieceGroup("splint", buildSplint, 1.4, y, -0.28);
        var purity = pieceGroup("test_tube", buildTestTube, 1.08, y, 0.12);
        purity.userData.home = purity.position.clone();
        /* 验纯、点燃时改走这根：管口露在空气里，不伸进水下的集气瓶。 */
        var openEnd = [mouth[0] + 0.62, mouth[1] + 0.12, 0.04];
        fx.h2OpenEnd = openEnd;
        fx.h2JetAt = { x: openEnd[0] + 0.07, y: openEnd[1] + 0.04, z: openEnd[2] };
        fx.h2Open = pieceGroup("h2_open", hose([
          mouth,
          [mouth[0] + 0.28, mouth[1] + 0.06, 0.02],
          openEnd
        ], [0, 1, 0]), mouth[0], mouth[1], mouth[2]);
        fx.h2Open.visible = false;
      },
      prep_co2: function () {
        /* 向上排空气：试管直立，导管伸入正放集气瓶底部，瓶口盖玻璃片，石灰水烧杯在右侧。 */
        var sx = -1.55, sz = 0;
        var tubeX = sx + 0.46;
        var mouth = [tubeX, y + 0.53, sz];
        var bx = -0.08, bz = 0.04;
        fx.collectAt = { x: bx, y: y + 0.06, z: bz };
        S("stand", "铁架台", sx, sz);
        S("tube", "试管", tubeX, sz, 0x38bdf8);
        S("bottle", "集气瓶", bx, bz, 0x38bdf8);
        S("lime_beaker", "石灰水", bx + 0.78, 0.12, 0x94a3b8);
        S("splint", "木条", 1.42, -0.28, 0xf59e0b);
        S("reagent", "药品", sx, -0.38, 0xa78bfa);
        pieceGroup("stand", function (g) { buildStand(g, 0); }, sx, y, sz);
        pieceGroup("tube", tiltTube(0), tubeX, y, sz);
        placeHose("delivery", [
          mouth,
          [mouth[0] + 0.22, mouth[1], 0.02],
          [bx, mouth[1] - 0.04, bz],
          [bx, y + 0.06, bz]
        ], [0, 1, 0]);
        pieceGroup("bottle", function (g) {
          buildBottle(g);
          add(g, cyl(0.13, 0.13, 0.014, glass(0xe2e8f0), 24), 0, 0.47, 0);
        }, bx, y, bz);
        pieceGroup("lime_beaker", buildLime, bx + 0.78, y, 0.12);
        pieceGroup("splint", buildSplint, 1.42, y, -0.28);
      },
      iron_in_oxygen: function () {
        S("lamp", "酒精灯", -0.95, 0.1, 0xf59e0b);
        S("wire", "铁丝", 0.05, -0.22, 0xfb7185);
        S("bottle", "集气瓶", 0.05, 0.08, 0x38bdf8);
        S("cover", "玻璃片", 0.72, -0.18, 0xcbd5e1);
        S("reagent", "药品", -0.95, -0.35, 0xa78bfa);
        pieceGroup("lamp", buildLamp, -0.95, y, 0.1);
        pieceGroup("bottle", buildBottle, 0.05, y, 0.06);
        /* 直柄伸出瓶口，螺旋和火柴头在瓶内、水面之上。 */
        pieceGroup("wire", buildWire, 0.05, y, 0.06);
        pieceGroup("cover", buildCover, 0.72, y, -0.18);
        fx.collectAt = { x: 0.05, y: 1.4, z: 0.06 };
      },
      neutralization: function () {
        S("goggles", "护目镜", -1.25, -0.18);
        S("beaker", "烧杯", 0, 0.08);
        S("dropper", "胶头滴管", 0, -0.22, 0xf87171);
        S("rod", "玻璃棒", 0.32, 0.1, 0x94a3b8);
        S("reagent", "药品", 0.85, -0.22, 0xa78bfa);
        pieceGroup("goggles", buildGoggles, -1.25, y, -0.18);
        pieceGroup("beaker", buildBeaker, 0, y, 0.06);
        pieceGroup("dropper", buildDropper, 0, y + 0.32, 0.06);
        pieceGroup("rod", buildRod, 0.16, y, 0.08);
      },
      metal_acid: function () {
        S("goggles", "护目镜", -1.25, -0.18);
        S("beaker", "烧杯", 0, 0.06);
        S("rod", "玻璃棒", 0.18, 0.08, 0x94a3b8);
        S("reagent", "药品", 0.85, -0.22, 0xa78bfa);
        pieceGroup("goggles", buildGoggles, -1.25, y, -0.18);
        pieceGroup("beaker", buildBeaker, 0, y, 0.06);
        pieceGroup("rod", buildRod, 0.16, y, 0.08);
      },
      solution_prep: function () {
        S("balance", "天平", -1.25, 0.1, 0xf59e0b);
        S("paper", "称量纸", -1.38, 0.1, 0xcbd5e1);
        S("cylinder", "量筒", 0.55, 0.1, 0x38bdf8);
        S("beaker", "烧杯", 0, 0.06);
        S("rod", "玻璃棒", 0.18, 0.08, 0x94a3b8);
        S("reagent", "药品", 1.1, -0.22, 0xa78bfa);
        pieceGroup("balance", buildBalance, -1.25, y, 0.1);
        pieceGroup("paper", buildPaper, -1.38, y + 0.12, 0.1);
        pieceGroup("cylinder", buildCylinder, 0.55, y, 0.1);
        pieceGroup("beaker", buildBeaker, 0, y, 0.06);
        pieceGroup("rod", buildRod, 0.16, y, 0.08);
      },
      electrolysis: function () {
        S("cell", "水槽", 0.2, 0.16, 0x0ea5e9);
        S("power", "电源", -1.35, 0.08, 0xf59e0b);
        S("tubes", "集气管", 0.2, -0.2, 0x38bdf8);
        S("splint", "木条", 1.45, -0.28, 0xf59e0b);
        S("reagent", "水", 0.2, -0.4, 0xa78bfa);
        pieceGroup("cell", buildCell, 0.2, y, 0.08);
        pieceGroup("power", buildPower, -1.35, y, 0.08);
        pieceGroup("tubes", buildTubes, 0.2, y, 0.08);
        pieceGroup("splint", buildSplint, 1.45, y, -0.28);
      },
      filtration: function () {
        var sx = -0.35, sz = 0;
        var fx_ = sx + 0.46;
        S("stand", "铁架台", sx, sz);
        S("funnel", "漏斗", fx_, -0.2, 0x38bdf8);
        S("paper", "滤纸", 0.95, -0.22, 0xcbd5e1);
        S("source_beaker", "浊液烧杯", -1.05, -0.12, 0xa8a29e);
        S("beaker", "烧杯", fx_, 0.22, 0x94a3b8);
        S("rod", "玻璃棒", fx_ + 0.12, -0.12, 0x94a3b8);
        S("reagent", "浊液", 0.95, 0.12, 0xa78bfa);
        pieceGroup("stand", buildStand, sx, y, sz);
        pieceGroup("funnel", buildFunnel, fx_, y, sz);
        pieceGroup("paper", buildPaper, 0.95, y, -0.22);
        /* 烧杯口靠玻璃棒，棒靠滤纸，漏斗颈靠接收烧杯内壁。 */
        var src = pieceGroup("source_beaker", buildBeaker, fx_ - 0.47, y + 0.34, 0.12);
        src.rotation.z = -0.7;
        pieceGroup("beaker", function (g) { buildBeaker(g); fx.filtrate = fx.liquid; }, fx_ + 0.1, y, sz);
        pieceGroup("rod", buildRod, fx_ - 0.06, y + 0.32, 0.14);
      },
      evaporation: function () {
        S("stand", "三脚架", 0, 0.06, 0x94a3b8);
        S("gauze", "陶土网", 0, 0.06, 0xcbd5e1);
        S("dish", "蒸发皿", 0, 0.06, 0x38bdf8);
        S("lamp", "酒精灯", 0, 0.06, 0xf59e0b);
        S("rod", "玻璃棒", 0.38, -0.06, 0x94a3b8);
        S("reagent", "溶液", 1.05, -0.18, 0xa78bfa);
        pieceGroup("lamp", buildLamp, 0, y, 0.06);
        /* 灯焰顶约在桌面上方 0.46，网和蒸发皿要高于焰尖。 */
        pieceGroup("stand", function (g) {
          add(g, box(0.7, 0.035, 0.035, mat(0x64748b, { metalness: 0.55 })), 0, 0.52, 0.16);
          add(g, box(0.035, 0.52, 0.035, mat(0x475569, { metalness: 0.55 })), -0.28, 0.26, 0.16);
          add(g, box(0.035, 0.52, 0.035, mat(0x475569, { metalness: 0.55 })), 0.28, 0.26, 0.16);
          add(g, box(0.035, 0.52, 0.035, mat(0x475569, { metalness: 0.55 })), 0, 0.26, -0.2);
        }, 0, y, 0.06);
        pieceGroup("gauze", buildGauze, 0, y + 0.54, 0.06);
        pieceGroup("dish", buildDish, 0, y + 0.57, 0.06);
        pieceGroup("rod", buildRod, 0.38, y + 0.55, -0.06);
      },
      metal_oxide_acid: function () {
        var tilt = -0.92;
        var tx = 0.02, ty = y + 0.12, tz = 0.06;
        S("tube", "试管", tx, tz, 0x38bdf8);
        S("lamp", "酒精灯", tx, 0.22, 0xf59e0b);
        S("rod", "试管夹", tx + 0.35, -0.18, 0x94a3b8);
        S("spoon", "药匙或纸槽", 0.82, -0.2, 0x94a3b8);
        S("reagent", "药品", -0.95, 0.08, 0xa78bfa);
        pieceGroup("lamp", buildLamp, tx, y, tz);
        pieceGroup("tube", tiltTube(tilt), tx, ty, tz);
        pieceGroup("rod", buildClamp, tx + 0.15, ty + 0.24, tz);
        pieceGroup("spoon", buildSpoon, 0.82, y, -0.2);
      },
      co2_candles: function () {
        S("bottle", "二氧化碳", -0.95, 0.08, 0x64748b);
        S("beaker", "烧杯", 0.35, 0.08, 0x38bdf8);
        pieceGroup("bottle", buildBottle, -0.95, y, 0.08);
        pieceGroup("beaker", buildCandleBeaker, 0.35, y, 0.08);
      },
      air_oxygen: function () {
        S("lamp", "酒精灯", -1.05, 0.1, 0xf59e0b);
        S("wire", "燃烧匙", 0.02, -0.22, 0xfb7185);
        S("bottle", "集气瓶", 0.02, 0.08, 0x38bdf8);
        S("beaker", "烧杯", 0.85, 0.1, 0x0ea5e9);
        S("delivery", "密闭导管", 0.43, 0.08, 0x94a3b8);
        S("clamp", "弹簧夹", 0.48, -0.16, 0xcbd5e1);
        S("reagent", "红磷", -1.05, -0.35, 0xa78bfa);
        pieceGroup("lamp", buildLamp, -1.05, y, 0.1);
        pieceGroup("bottle", function (g) {
          buildBottle(g);
          for (var i = 1; i < 5; i++) {
            var mark = new THREE.Mesh(new THREE.TorusGeometry(0.116, 0.003, 6, 32),
              mat(0x0f766e, { emissive: 0x0f766e, emissiveIntensity: 0.3 }));
            mark.rotation.x = Math.PI / 2;
            add(g, mark, 0, 0.08 + i * 0.065, 0);
          }
        }, 0.02, y, 0.06);
        /* 燃烧匙从瓶口伸入，勺头在瓶内，柄留在塞外。 */
        pieceGroup("wire", function (g) {
          var steel = mat(0xcbd5e1, { metalness: 0.72, roughness: 0.24 });
          add(g, cyl(0.009, 0.009, 0.42, steel, 10), 0, 0.36, 0);
          var bowl = sph(0.042, steel, 16, 10);
          bowl.scale.set(1.15, 0.32, 0.85);
          add(g, bowl, 0, 0.13, 0);
          fx.burnSample = add(g, sph(0.028, mat(0xdc2626, { roughness: 0.8 })), 0, 0.15, 0);
          fx.burnFlame = add(g, new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.16, 16),
            mat(0x60a5fa, { emissive: 0x3b82f6, emissiveIntensity: 2, transparent: true, opacity: 0.92 })), 0, 0.26, 0);
          fx.burnFlame.visible = false;
        }, 0.02, y, 0.06);
        pieceGroup("beaker", buildBeaker, 0.85, y, 0.08);
        placeHose("delivery", [
          [0.1, y + 0.46, 0.06],
          [0.42, y + 0.48, 0.06],
          [0.85, y + 0.28, 0.08],
          [0.85, y + 0.1, 0.08]
        ], [1, 0, 0]);
        var clamp = pieceGroup("clamp", buildSpringClamp, 0.3, y + 0.38, 0.06);
        clamp.rotation.y = Math.PI / 2;
        fx.collectAt = { x: 0.02, y: 1.4, z: 0.06 };
      },
      combustion_conditions: function () {
        S("beaker", "烧杯", 0.05, 0.08, 0x38bdf8);
        S("cover", "薄铜片", 0.05, -0.18, 0xb45309);
        S("delivery", "通氧导管", -0.62, 0.08, 0x94a3b8);
        S("tweezers", "镊子", 0.82, -0.2, 0x94a3b8);
        S("reagent", "磷和氧气", -1.0, -0.24, 0xa78bfa);
        pieceGroup("beaker", buildConditionBeaker, 0.05, y, 0.08);
        pieceGroup("cover", buildCover, 0.72, y, -0.18);
        pieceGroup("tweezers", buildTweezers, 0.82, y, -0.2);
        placeHose("delivery", [
          [-0.72, y + 0.42, 0.08],
          [-0.42, y + 0.42, 0.08],
          [0.05, y + 0.2, 0.08],
          [0.05, y + 0.1, 0.08]
        ]);
      },
      charcoal_in_oxygen: function () {
        S("lamp", "酒精灯", -1.05, 0.08, 0xf59e0b);
        S("wire", "坩埚钳", 0.02, -0.2, 0x94a3b8);
        S("bottle", "氧气瓶", 0.02, 0.08, 0x38bdf8);
        S("lime_beaker", "石灰水", 0.86, 0.08, 0xe2e8f0);
        S("reagent", "木炭和氧气", -1.05, -0.34, 0xa78bfa);
        pieceGroup("lamp", buildLamp, -1.05, y, 0.08);
        pieceGroup("bottle", buildBottle, 0.02, y, 0.06);
        pieceGroup("wire", function (g) { buildBurnSpoon(g, "charcoal"); }, 0.02, y + 0.18, 0.06);
        pieceGroup("lime_beaker", buildLime, 0.86, y, 0.08);
        fx.collectAt = { x: 0.02, y: 1.45, z: 0.06 };
      },
      sulfur_in_oxygen: function () {
        S("lamp", "酒精灯", -1.18, 0.08, 0xf59e0b);
        S("wire", "燃烧匙", -0.12, -0.18, 0x94a3b8);
        S("bottle", "氧气瓶", -0.12, 0.08, 0x38bdf8);
        S("goggles", "护目镜", 0.72, -0.2, 0x2dd4bf);
        S("absorber", "尾气吸收瓶", 0.95, 0.1, 0x60a5fa);
        S("reagent", "硫和氧气", -1.18, -0.34, 0xa78bfa);
        pieceGroup("lamp", buildLamp, -1.18, y, 0.08);
        pieceGroup("bottle", buildBottle, -0.12, y, 0.06);
        pieceGroup("wire", function (g) {
          var steel = mat(0xcbd5e1, { metalness: 0.72, roughness: 0.24 });
          add(g, cyl(0.008, 0.008, 0.34, steel, 10), 0, 0.4, 0);
          var bowl = sph(0.036, steel, 14, 10);
          bowl.scale.set(1.1, 0.32, 0.8);
          add(g, bowl, 0, 0.2, 0);
          fx.burnSample = add(g, sph(0.026, mat(0xeab308, { roughness: 0.75 })), 0, 0.22, 0);
          fx.burnFlame = add(g, new THREE.Mesh(new THREE.ConeGeometry(0.045, 0.14, 14),
            mat(0x60a5fa, { emissive: 0x3b82f6, emissiveIntensity: 2, transparent: true, opacity: 0.92 })), 0, 0.32, 0);
          fx.burnFlame.visible = false;
        }, -0.12, y, 0.06);
        pieceGroup("goggles", buildGoggles, 0.72, y, -0.2);
        var absorber = pieceGroup("absorber", buildAbsorber, 0.95, y, 0.1);
        /* 导管从瓶口沿前方通入碱液液面下，避免被瓶壁挡住看不见。 */
        buildDeliveryPath(absorber, [
          [-0.9, 0.5, 0.1],
          [-0.4, 0.58, 0.12],
          [0.04, 0.5, 0.1],
          [0.04, 0.06, 0.08]
        ]);
      },
      charcoal_reduce_cuo: function () {
        var sx = -1.42, tx = -1.22, ty = y + 0.42, tilt = -1.66;
        var mouth = [tx + 0.53, ty - 0.047, 0.02];
        S("stand", "铁架台", sx, 0.02);
        S("tube", "反应试管", tx, 0.02, 0x38bdf8);
        S("lamp", "酒精灯", tx - 0.05, 0.14, 0xf59e0b);
        S("delivery", "导管", -0.28, 0.02, 0x94a3b8);
        S("lime_beaker", "石灰水", 0.45, 0.08, 0xe2e8f0);
        S("reagent", "混合粉末", sx, -0.38, 0xa78bfa);
        pieceGroup("stand", function (g) { buildStand(g, tilt); }, sx, y, 0.02);
        pieceGroup("tube", tiltTube(tilt), tx, ty, 0.02);
        pieceGroup("lamp", buildLamp, tx - 0.05, y, 0.14);
        pieceGroup("lime_beaker", buildLime, 0.45, y, 0.08);
        placeHose("delivery", [
          mouth, [-0.45, mouth[1], 0.02], [0.45, y + 0.25, 0.08], [0.45, y + 0.08, 0.08]
        ], mouthAxis(tilt));
      },
      mass_conservation: function () {
        S("balance", "天平", -0.72, 0.08, 0xf59e0b);
        S("beaker", "密闭锥形瓶", 0.12, 0.08, 0x38bdf8);
        S("reagent", "铁和硫酸铜", 1.05, -0.24, 0xa78bfa);
        pieceGroup("balance", buildBalance, -0.72, y, 0.08);
        pieceGroup("beaker", buildConicalFlask, 0.12, y + 0.1, 0.08);
      },
      metal_displace: function () {
        S("goggles", "护目镜", -1.05, -0.2, 0x2dd4bf);
        S("beaker", "硫酸铜烧杯", 0.02, 0.08, 0x38bdf8);
        S("rod", "打磨铁钉", 0.15, 0.06, 0x94a3b8);
        S("reagent", "硫酸铜", 0.92, -0.24, 0xa78bfa);
        pieceGroup("goggles", buildGoggles, -1.05, y, -0.2);
        pieceGroup("beaker", buildBeaker, 0.02, y, 0.08);
        pieceGroup("rod", function (g) {
          fx.displaceIron = add(g, box(0.025, 0.36, 0.025, mat(0x94a3b8, { metalness: 0.68 })), 0, 0.24, 0);
          fx.displaceCopper = add(g, box(0.033, 0.2, 0.032, mat(0xb45309, { metalness: 0.48 })), 0, 0.17, 0);
          fx.displaceCopper.visible = false;
        }, 0.08, y + 0.08, 0.08);
      },
      acid_indicator: function () {
        S("goggles", "护目镜", -1.16, -0.2, 0x2dd4bf);
        S("beaker", "两组容器", 0.05, 0.08, 0x38bdf8);
        S("dropper", "专用滴管", 0.05, -0.24, 0xf87171);
        S("reagent", "酸碱和指示剂", 1.02, -0.24, 0xa78bfa);
        pieceGroup("goggles", buildGoggles, -1.16, y, -0.2);
        pieceGroup("beaker", buildIndicatorSet, 0.05, y, 0.08);
        pieceGroup("dropper", buildDropper, 0.05, y + 0.42, 0.08);
      },
      dilute_h2so4: function () {
        S("goggles", "护目镜", -1.18, -0.2, 0x2dd4bf);
        S("beaker", "盛水烧杯", 0.02, 0.08, 0x38bdf8);
        S("rod", "玻璃棒", 0.18, 0.08, 0x94a3b8);
        S("reagent", "浓硫酸和水", 0.94, -0.24, 0xa78bfa);
        pieceGroup("goggles", buildGoggles, -1.18, y, -0.2);
        pieceGroup("beaker", buildBeaker, 0.02, y, 0.08);
        pieceGroup("rod", buildRod, 0.17, y + 0.06, 0.08);
      },
      iron_rust: function () {
        S("tube", "对照试管", 0, 0.06, 0x38bdf8);
        S("lamp", "酒精灯", -0.9, 0.08, 0xf59e0b);
        S("cotton", "棉花", 0.28, 0.06, 0xf8fafc);
        S("reagent", "铁钉、水等", 1.05, -0.24, 0xa78bfa);
        pieceGroup("tube", buildRustTubes, 0, y, 0.06);
        pieceGroup("lamp", buildLamp, -0.9, y, 0.08);
        /* 第三支试管口：棉花挡住空气中的水蒸气，下面才是干燥剂。 */
        pieceGroup("cotton", buildCottonPlug, 0.28, y + 0.44, 0.06);
      }
    };
    L.oxygen = L.prep_oxygen_kmno4;
    L.gas_wet = L.prep_hydrogen;
    L.gas_air = L.prep_co2;
    L.burn = L.iron_in_oxygen;
    L.oxide = L.metal_oxide_acid;
    (L[id] || L[kind] || L.prep_oxygen_kmno4)();
    makeFx(kind);
  }

  /* 室内灯箱环境，取自 three.js RoomEnvironment（上游是 model-viewer）。
     玻璃和金属映的是这几块亮面，而不是一面灰墙。 */
  function buildStudioEnv() {
    var s = new THREE.Scene();
    var geometry = new THREE.BoxGeometry();
    geometry.deleteAttribute("uv");
    var roomMaterial = new THREE.MeshStandardMaterial({ side: THREE.BackSide });
    var boxMaterial = new THREE.MeshStandardMaterial();
    function area(intensity) {
      var material = new THREE.MeshBasicMaterial();
      material.color.setScalar(intensity);
      return material;
    }
    var mainLight = new THREE.PointLight(0xffffff, 5, 28, 2);
    mainLight.position.set(0.418, 16.199, 0.3);
    s.add(mainLight);
    var room = new THREE.Mesh(geometry, roomMaterial);
    room.position.set(-0.757, 13.219, 0.717);
    room.scale.set(31.713, 28.305, 28.591);
    s.add(room);
    [[-10.906, 2.009, 1.846, 0, -0.195, 0, 2.328, 7.905, 4.651],
      [-5.607, -0.754, -0.758, 0, 0.994, 0, 1.97, 1.534, 3.955],
      [6.167, 0.857, 7.803, 0, 0.561, 0, 3.927, 6.285, 3.687],
      [-2.017, 0.018, 6.124, 0, 0.333, 0, 2.002, 4.566, 2.064],
      [2.291, -0.756, -2.621, 0, -0.286, 0, 1.546, 1.552, 1.496],
      [-2.193, -0.369, -5.547, 0, 0.516, 0, 3.875, 3.487, 2.986]].forEach(function (b) {
      var box = new THREE.Mesh(geometry, boxMaterial);
      box.position.set(b[0], b[1], b[2]);
      box.rotation.set(b[3], b[4], b[5]);
      box.scale.set(b[6], b[7], b[8]);
      s.add(box);
    });
    [[-16.116, 14.37, 8.208, 0.1, 2.428, 2.739, 50],
      [-16.109, 18.021, -8.207, 0.1, 2.425, 2.751, 50],
      [14.904, 12.198, -1.832, 0.15, 4.265, 6.331, 17],
      [-0.462, 8.89, 14.52, 4.38, 5.441, 0.088, 43],
      [3.235, 11.486, -12.541, 2.5, 2, 0.1, 20],
      [0, 20, 0, 1, 0.1, 1, 100]].forEach(function (L) {
      var light = new THREE.Mesh(geometry, area(L[6]));
      light.position.set(L[0], L[1], L[2]);
      light.scale.set(L[3], L[4], L[5]);
      s.add(light);
    });
    return s;
  }
  function setupEnv() {
    var g = new THREE.PMREMGenerator(renderer);
    var s = buildStudioEnv();
    scene.environment = g.fromScene(s, 0.04).texture;
    g.dispose();
    var dumped = [];
    s.traverse(function (obj) {
      if (obj.geometry && dumped.indexOf(obj.geometry) < 0) {
        dumped.push(obj.geometry);
        obj.geometry.dispose();
      }
      if (obj.material && dumped.indexOf(obj.material) < 0) {
        dumped.push(obj.material);
        obj.material.dispose();
      }
    });
  }

  function updateCamera() {
    pitch = Math.max(0.16, Math.min(1.12, pitch));
    camera.position.set(
      Math.sin(yaw) * Math.cos(pitch) * dist,
      lookY + Math.sin(pitch) * dist * 0.72,
      Math.cos(yaw) * Math.cos(pitch) * dist
    );
    camera.lookAt(0, lookY, 0.05);
  }

  function tick(now) {
    requestAnimationFrame(tick);
    clock.t = now;
    Object.keys(slots).forEach(function (k) {
      var s = slots[k];
      if (!s.visible) return;
      var bob = 0.52 + Math.sin(now * 0.003 + s.userData.bob) * 0.05;
      if (s.userData.diamond) s.userData.diamond.position.y = bob;
      if (s.userData.ring) s.userData.ring.rotation.z = now * 0.001;
    });
    if (fx.flame && fx.flame.visible) {
      var flick = 0.88 + Math.sin(now * 0.021) * 0.16 + Math.sin(now * 0.053) * 0.08;
      fx.flame.scale.set(0.92 + Math.sin(now * 0.04) * 0.08, flick, 1);
      if (fx.flameInner) fx.flameInner.scale.y = 0.9 + Math.sin(now * 0.03) * 0.12;
      if (fx.flameLight) fx.flameLight.intensity = 1.6 + Math.sin(now * 0.03) * 0.45;
    }
    var cx = (fx.collectAt && fx.collectAt.x) || 0.4;
    var cy0 = (fx.collectAt && fx.collectAt.y) || 1.16;
    var cz = (fx.collectAt && fx.collectAt.z) || 0.08;
    (fx.bubbles || []).forEach(function (b, i) {
      if (!b.visible) return;
      b.position.y += 0.006;
      if (b.position.y > cy0 + 0.42) b.position.y = cy0;
      b.position.x = cx + Math.sin(now * 0.01 + i) * 0.04;
      b.position.z = cz;
    });
    (fx.beakerBubbles || []).concat(fx.tubeBubbles || []).forEach(function (b, i) {
      if (!b.visible) return;
      b.position.y += 0.004;
      if (b.position.y > 0.32) b.position.y = 0.1;
    });
    (fx.steam || []).forEach(function (s, i) {
      if (!s.visible) return;
      s.position.y += 0.004;
      if (s.position.y > 2.15) s.position.y = 1.72;
      s.material.opacity = 0.18 + Math.sin(now * 0.01 + i) * 0.1;
    });
    (fx.sparks || []).forEach(function (s, i) {
      if (!s.visible) return;
      s.position.x = cx + Math.sin(now * 0.02 + i) * 0.08;
      s.position.y = cy0 + 0.18 + Math.cos(now * 0.03 + i) * 0.1;
      s.position.z = cz;
    });
    (fx.smoke || []).forEach(function (s, i) {
      if (!s.visible) return;
      s.position.y += 0.0025 + (i % 3) * 0.0005;
      s.position.x += Math.sin(now * 0.003 + i) * 0.0007;
      if (s.position.y > 1.95) s.position.y = 1.46;
      s.material.opacity = 0.2 + Math.sin(now * 0.006 + i) * 0.09;
    });
    if (fx.burnFlame && fx.burnFlame.visible) {
      fx.burnFlame.scale.y = 0.9 + Math.sin(now * 0.028) * 0.16;
    }
    Object.keys(pieces).forEach(function (k) {
      var g = pieces[k];
      if (!g || !g.userData.shown) return;
      if (k === highlightId) g.scale.setScalar(1 + Math.sin(now * 0.008) * 0.045);
      else if (Math.abs(g.scale.x - 1) > 0.001) g.scale.setScalar(1);
    });
    if (pour.on) tickPour(0.016);
    if (mix.on) tickMix(0.016);
    for (var i = pops.length - 1; i >= 0; i--) {
      pops[i].t += 0.05;
      var k = Math.min(1, pops[i].t);
      var s = 1 - Math.pow(1 - k, 3);
      pops[i].obj.scale.setScalar(0.2 + 0.8 * s);
      if (k >= 1) pops.splice(i, 1);
    }
    renderer.render(scene, camera);
  }
  function tickPour(dt) {
    pour.t += dt;
    var bottle = fx.pourer;
    if (!bottle) { pour.on = false; return; }
    bottle.visible = true;
    var target = pieces.tube || pieces.beaker || pieces.dish;
    var tx = target ? target.position.x - 0.38 : -0.4;
    var ty = target ? target.position.y + 0.42 : 1.45;
    var tz = target ? target.position.z : 0.1;
    bottle.position.set(tx, ty, tz);
    if (pour.t < 0.35) bottle.rotation.z = -pour.t * 2.2;
    else if (pour.t < 1.15) {
      bottle.rotation.z = -0.77;
      if (fx.stream) {
        fx.stream.visible = true;
        fx.stream.material.color.setHex(pour.color);
        fx.stream.position.set(tx + 0.18, ty - 0.18, tz);
      }
      var liq = fx.acid || fx.liquid;
      if (liq) {
        liq.visible = true;
        liq.scale.y = Math.min(1, 0.35 + pour.t * 0.6);
      }
    } else {
      if (fx.stream) fx.stream.visible = false;
      bottle.rotation.z += (0 - bottle.rotation.z) * 0.12;
      if (pour.t > 1.7) {
        bottle.visible = false;
        bottle.rotation.z = 0;
        pour.on = false;
      }
    }
  }
  function tickMix(dt) {
    mix.t += dt;
    var rod = pieces.rod;
    if (rod && rod.visible) rod.rotation.y = Math.sin(mix.t * 14) * 0.55;
    var liq = fx.liquid || fx.acid;
    if (liq) liq.rotation.y += 0.08;
    if (mix.t > 1.25) {
      mix.on = false;
      if (rod) rod.rotation.y = 0;
    }
  }

  function onPointerDown(e) {
    if (e.button !== 0) return;
    orbiting = true;
    lastX = e.clientX; lastY = e.clientY;
  }
  function onPointerMove(e) {
    if (!orbiting) return;
    yaw -= (e.clientX - lastX) * 0.0055;
    pitch -= (e.clientY - lastY) * 0.0045;
    lastX = e.clientX; lastY = e.clientY;
    updateCamera();
  }
  function onPointerUp() { orbiting = false; }
  function onWheel(e) {
    dist = Math.max(2.8, Math.min(7.2, dist + e.deltaY * 0.0035));
    updateCamera();
  }

  function init(el, sceneKey, expId) {
    canvas = el;
    currentExpId = expId || sceneKey || "";
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xc5d3df);
    scene.fog = new THREE.Fog(0xc5d3df, 11, 22);
    camera = new THREE.PerspectiveCamera(34, 1, 0.08, 40);
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: false });
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    if (THREE.SRGBColorSpace) renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();
    setupEnv();
    scene.add(new THREE.HemisphereLight(0xf3f7fb, 0x5c5348, 0.55));
    var sun = new THREE.DirectionalLight(0xfff8ee, 1.55);
    sun.position.set(3.2, 6.4, 2.2);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    sun.shadow.bias = -0.0004;
    sun.shadow.camera.near = 1;
    sun.shadow.camera.far = 16;
    sun.shadow.camera.left = -4;
    sun.shadow.camera.right = 4;
    sun.shadow.camera.top = 4;
    sun.shadow.camera.bottom = -4;
    scene.add(sun);
    scene.add(new THREE.AmbientLight(0xffffff, 0.12));
    var fill = new THREE.DirectionalLight(0xd7e6f5, 0.45);
    fill.position.set(-3.5, 2.4, 2.6);
    scene.add(fill);
    buildRoom();
    layout(sceneKey || "oxygen", expId);
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
    if (!pieces[id]) return;
    if (id === "reagent") {
      pieces[id].visible = false;
      return;
    }
    var show = !!on;
    pieces[id].userData.shown = show;
    if (show) {
      pieces[id].visible = true;
      pieces[id].scale.setScalar(1);
    } else {
      pieces[id].visible = false;
    }
  }
  function applyEffects(st) {
    st = st || {};
    if (fx.powder) {
      fx.powder.visible = (!!st.powder || !!st.oxide) && st.liquid !== "blue";
      var powderColors = { purple: 0x3b0764, white: 0xf8fafc, black: 0x111827 };
      fx.powder.material.color.setHex(powderColors[st.powder_color] || 0x1e293b);
    }
    if (fx.copper) fx.copper.visible = !!st.copper;
    if (fx.zinc) fx.zinc.visible = !!st.zinc;
    if (fx.marble) fx.marble.visible = !!st.marble;
    if (fx.cotton) fx.cotton.visible = !!st.cotton;
    if (fx.acid) {
      fx.acid.visible = !!st.acid || !!st.oxide_acid || st.liquid === "blue";
      if (st.liquid === "blue") {
        fx.acid.material.color.setHex(0x1d4ed8);
        if (fx.acid.material.emissive) {
          fx.acid.material.emissive.setHex(0x1d4ed8);
          fx.acid.material.emissiveIntensity = 0.35;
        }
      }
    }
    var lit = !!st.flame || !!st.heat;
    if (fx.flame) fx.flame.visible = lit;
    if (fx.flameInner) fx.flameInner.visible = lit;
    if (fx.flameLight) fx.flameLight.intensity = lit ? 1.6 : 0;
    if (fx.splintFlame) fx.splintFlame.visible = !!st.splint_on;
    if (fx.splintGlow) {
      fx.splintGlow.visible = true;
      fx.splintGlow.material.emissiveIntensity = st.splint_on ? 2.4 : 0.55;
    }
    if (fx.burnFlame) {
      var sulfur = st.sulfur_flame;
      fx.burnFlame.visible = !!sulfur || !!st.charcoal_glow;
      if (st.charcoal_glow) {
        fx.burnFlame.material.color.setHex(0xffffff);
        fx.burnFlame.material.emissive.setHex(0xffffff);
        fx.burnFlame.material.emissiveIntensity = 3;
        fx.burnFlame.scale.set(1.35, 1.3, 1.35);
      } else if (sulfur) {
        var pale = sulfur === "pale_blue";
        fx.burnFlame.material.color.setHex(pale ? 0x93c5fd : 0x6d28d9);
        fx.burnFlame.material.emissive.setHex(pale ? 0x60a5fa : 0x4338ca);
        fx.burnFlame.material.emissiveIntensity = pale ? 1.7 : 2.8;
        fx.burnFlame.scale.set(pale ? 0.8 : 1.15, pale ? 0.85 : 1.25, pale ? 0.8 : 1.15);
      }
    }
    if (fx.charcoalLight) fx.charcoalLight.intensity = st.charcoal_glow ? 2.8 : 0;
    (fx.smoke || []).forEach(function (s) { s.visible = !!st.white_smoke; });
    (fx.bubbles || []).forEach(function (b) {
      b.visible = !!st.bubbles || !!st.acid_bubbles;
      b.scale.setScalar(b.visible ? 2.4 : 1);
    });
    (fx.tubeBubbles || []).forEach(function (b) {
      b.visible = !!st.acid_bubbles || !!st.oxide_bubbles || !!st.bubbles;
      b.scale.setScalar(b.visible ? 2.6 : 1);
    });
    if (fx.gas) {
      fx.gas.visible = (!!st.collected && !st.air_collect) || !!st.co2_fill;
      if (fx.gas.material) {
        fx.gas.material.color.setHex(0xbef264);
        fx.gas.material.opacity = fx.gas.visible ? 0.88 : 0.45;
      }
      fx.gas.scale.set(fx.gas.visible ? 1.08 : 1, fx.gas.visible ? 1.7 : 1, fx.gas.visible ? 1.08 : 1);
    }
    if (fx.flameLow) fx.flameLow.visible = !!st.lit && !st.low_out;
    if (fx.flameLowInner) fx.flameLowInner.visible = !!st.lit && !st.low_out;
    if (fx.flameHigh) fx.flameHigh.visible = !!st.lit && !st.high_out;
    if (fx.flameHighInner) fx.flameHighInner.visible = !!st.lit && !st.high_out;
    if (fx.co2Low) fx.co2Low.visible = !!st.co2_low || !!st.co2_mid;
    if (fx.co2Mid) fx.co2Mid.visible = !!st.co2_mid;
    if (pieces.bottle && st.pouring) pieces.bottle.rotation.z = -0.72;
    else if (pieces.bottle) pieces.bottle.rotation.z = 0;
    if (fx.bottleWater) {
      fx.bottleWater.visible = !!st.bottle_water || !!st.water_rise;
      if (st.water_rise) fx.bottleWater.scale.set(1, 2.4, 1);
      else fx.bottleWater.scale.set(1, 1, 1);
    }
    if (fx.hotWater) fx.hotWater.visible = !!st.hot_water;
    if (fx.wpAir) fx.wpAir.visible = !!st.wp_air;
    if (fx.flameWp) fx.flameWp.visible = !!st.wp_air;
    if (fx.rpAir) fx.rpAir.visible = !!st.rp_air;
    if (fx.wpWater) fx.wpWater.visible = !!st.wp_water;
    if (fx.wpO2) fx.wpO2.visible = !!st.wp_o2;
    if (fx.rustNail && st.rust) fx.rustNail.material.color.setHex(0xb45309);
    if (fx.troughWater && pieces.trough) pieces.trough.visible = pieces.trough.visible && !st.air_collect;
    if (fx.pop) fx.pop.visible = !!st.pop;
    if (currentExpId === "prep_hydrogen" && pieces.delivery) {
      var openAir = !!pieces.delivery.userData.shown && (!!st.jet_flame || !!st.pop);
      pieces.delivery.visible = !!pieces.delivery.userData.shown && !openAir;
      if (fx.h2Open) fx.h2Open.visible = openAir;
      if (pieces.test_tube && pieces.test_tube.userData.home) {
        if (st.pop && pieces.test_tube.userData.shown && fx.h2OpenEnd) {
          pieces.test_tube.rotation.z = Math.PI;
          pieces.test_tube.position.set(fx.h2OpenEnd[0], fx.h2OpenEnd[1] + 0.4, fx.h2OpenEnd[2]);
        } else {
          pieces.test_tube.rotation.z = 0;
          pieces.test_tube.position.copy(pieces.test_tube.userData.home);
          pieces.test_tube.visible = !!pieces.test_tube.userData.shown;
        }
      }
      if (fx.pop && fx.h2OpenEnd && st.pop) {
        fx.pop.position.set(fx.h2OpenEnd[0] + 0.42, fx.h2OpenEnd[1] + 0.28, fx.h2OpenEnd[2]);
      }
      if (fx.jet && fx.h2JetAt && st.jet_flame) {
        fx.jet.position.set(fx.h2JetAt.x, fx.h2JetAt.y, fx.h2JetAt.z);
        fx.jet.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(0.92, 0.35, 0).normalize());
      }
    }
    if (fx.jet) fx.jet.visible = !!st.jet_flame;
    (fx.sparks || []).forEach(function (s) { s.visible = !!st.sparks; });
    if (fx.tube) {
      var rot = st.upright ? 0 : (st.tilt_up ? 0.28 : (typeof fx.tube.userData.tilt0 === "number" ? fx.tube.userData.tilt0 : -0.28));
      if (st.upright || st.tilt_up || st.tilt_down) fx.tube.rotation.z = rot;
    }
    if (fx.liquid) {
      var colors = { pink: 0xec4899, pale: 0xf9a8d4, clear: 0x38bdf8, blue: 0x1d4ed8, red: 0xef4444 };
      var liquidHex = colors[st.liquid] || colors.clear;
      fx.liquid.material.color.setHex(liquidHex);
      if (fx.liquid.material.emissive) {
        fx.liquid.material.emissive.setHex(liquidHex);
        fx.liquid.material.emissiveIntensity = st.liquid && st.liquid !== "clear" ? 0.32 : 0.08;
      }
      fx.liquid.material.opacity = 0.94;
      if (st.filtrate === false) fx.liquid.visible = false;
      if (st.filtrate) fx.liquid.visible = true;
    }
    if (fx.drip) fx.drip.visible = !!st.dripping;
    if (fx.metal) fx.metal.visible = !!st.metal;
    if (fx.testPaper) fx.testPaper.material.color.setHex(st.wet_paper && st.lime_milky ? 0x2563eb : 0xf87171);
    if (currentExpId === "metal_displace" && fx.displaceCopper) {
      fx.displaceCopper.visible = !!st.metal;
      if (fx.liquid && st.metal) fx.liquid.material.color.setHex(0x60a5fa);
    }
    if (currentExpId === "mass_conservation" && fx.massLiquid) {
      var reacted = !!st.mass_reacted;
      fx.massLiquid.material.color.setHex(reacted ? 0x86b7a7 : 0x2563eb);
      fx.massLiquid.visible = reacted;
      if (fx.innerLiquid) fx.innerLiquid.visible = !reacted;
      if (fx.massIron) fx.massIron.visible = !reacted;
      if (fx.massCopper) fx.massCopper.visible = reacted;
    }
    if (currentExpId === "acid_indicator" && fx.indAcidLitmus) {
      fx.indAcidLitmus.material.color.setHex(0x7c3aed);
      fx.indBaseLitmus.material.color.setHex(0x7c3aed);
      fx.indAcidPhen.material.color.setHex(0x7dd3fc);
      fx.indBasePhen.material.color.setHex(0x7dd3fc);
      if (st.liquid === "red") fx.indAcidLitmus.material.color.setHex(0xdc2626);
      if (st.liquid === "blue") {
        fx.indAcidLitmus.material.color.setHex(0xdc2626);
        fx.indBaseLitmus.material.color.setHex(0x2563eb);
      }
      if (st.liquid === "pink") {
        fx.indAcidLitmus.material.color.setHex(0xdc2626);
        fx.indBaseLitmus.material.color.setHex(0x2563eb);
        fx.indBasePhen.material.color.setHex(0xec4899);
      }
    }
    (fx.beakerBubbles || []).forEach(function (b) { b.visible = !!st.acid_bubbles; });
    if (fx.h2) fx.h2.visible = !!st.gases;
    if (fx.o2) fx.o2.visible = !!st.gases;
    if (fx.h2gas) fx.h2gas.visible = !!st.gases;
    if (fx.o2gas) fx.o2gas.visible = !!st.gases;
    if (fx.ratio) fx.ratio.visible = !!st.ratio;
    if (fx.filterPaper) fx.filterPaper.visible = !!st.paper;
    if (fx.residue) fx.residue.visible = !!st.residue;
    if (fx.limeLiquid) {
      fx.limeLiquid.material.color.setHex(st.lime_milky ? 0xffffff : 0x7dd3fc);
      fx.limeLiquid.material.opacity = st.lime_milky ? 0.98 : 0.55;
    }
    if (fx.crystals) fx.crystals.visible = !!st.crystals;
    if (fx.dishLiquid) fx.dishLiquid.material.opacity = st.crystals ? 0.25 : 0.55;
    (fx.steam || []).forEach(function (s) { s.visible = !!st.heat; });
  }
  function hoverSlot(name) {
    Object.keys(slots).forEach(function (k) {
      var s = slots[k];
      var hot = k === name;
      if (s.userData.diamond) s.userData.diamond.scale.setScalar(hot ? 1.35 : 1);
    });
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
  var highlightId = "";
  function highlight(id) { highlightId = id || ""; }
  function hitPiece(clientX, clientY) {
    if (!canvas) return "";
    var r = canvas.getBoundingClientRect();
    pointer.x = ((clientX - r.left) / r.width) * 2 - 1;
    pointer.y = -((clientY - r.top) / r.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    var list = [];
    Object.keys(pieces).forEach(function (k) {
      var g = pieces[k];
      if (!g || !g.visible || k === "reagent" || !g.userData.shown) return;
      g.traverse(function (o) {
        if (o.isMesh) { o.userData.piece = k; list.push(o); }
      });
    });
    var hits = raycaster.intersectObjects(list, false);
    return hits.length ? (hits[0].object.userData.piece || "") : "";
  }
  function playPour(color) {
    pour.on = true;
    pour.t = 0;
    pour.color = parseColor(color);
    if (fx.pourer) fx.pourer.visible = true;
  }
  function playMix() {
    mix.on = true;
    mix.t = 0;
  }
  function playPlace(id) {
    if (pieces[id]) setPiece(id, true);
  }
  function resetView() {
    yaw = 0.42; pitch = 0.38; dist = 4.4;
    updateCamera();
  }

  global.Lab3D = {
    init: init, resize: resize, setSelecting: setSelecting,
    setPiece: setPiece, applyEffects: applyEffects, hitSlot: hitSlot, hoverSlot: hoverSlot,
    hitPiece: hitPiece, highlight: highlight,
    playPour: playPour, playMix: playMix, playPlace: playPlace, resetView: resetView
  };
})(window);
