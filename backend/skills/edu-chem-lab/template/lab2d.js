/* 宏观实验台：写实 2D 器材 + 同形虚线工位。 */
(function (global) {
  var NS = "http://www.w3.org/2000/svg";
  var svg, slots = {}, pieces = {}, fx = {};
  var selecting = false, needed = {};

  function el(name, attrs, html) {
    var n = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (html) n.innerHTML = html;
    return n;
  }
  function tf(s) {
    return "translate(" + s.x + "," + s.y + ") rotate(" + (s.r || 0) + ") scale(" + (s.s || 1) + ")";
  }

  var ART = {
    stand: {
      w: 150, h: 240, label: "铁架台",
      outline: "M8 220 h134 v18 h-56 v-198 h14 v180 h-92z M64 48 h62 v16 H86 v40 H74 V64 H64z",
      paint: '<defs><linearGradient id="g-iron" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#1f2937"/><stop offset=".45" stop-color="#9ca3af"/><stop offset="1" stop-color="#111827"/></linearGradient></defs>' +
        '<path d="M8 220 h134 v18 h-56 v-198 h14 v180 h-92z" fill="url(#g-iron)"/>' +
        '<path d="M64 48 h62 v16 H86 v40 H74 V64 H64z" fill="#374151"/>' +
        '<circle cx="80" cy="80" r="5" fill="#9ca3af"/>'
    },
    tripod: {
      w: 170, h: 130, label: "三脚架",
      outline: "M22 122 L78 34 h14 L148 122 h-16 L85 48 38 122z M60 22 h50 v12 H60z",
      paint: '<path d="M22 122 L78 34 h14 L148 122" fill="none" stroke="#4b5563" stroke-width="8" stroke-linejoin="round"/>' +
        '<line x1="85" y1="40" x2="85" y2="122" stroke="#4b5563" stroke-width="8"/>' +
        '<rect x="60" y="22" width="50" height="12" rx="2" fill="#6b7280"/>'
    },
    tube: {
      w: 64, h: 196, label: "试管",
      outline: "M18 8 h28 a4 4 0 0 1 4 4 v140 a18 22 0 0 1 -36 0 V12 a4 4 0 0 1 4 -4z",
      paint: '<defs><linearGradient id="g-glass" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#94a3b8" stop-opacity=".35"/><stop offset=".22" stop-color="#f8fafc" stop-opacity=".15"/><stop offset=".55" stop-color="#bae6fd" stop-opacity=".45"/><stop offset="1" stop-color="#0369a1" stop-opacity=".28"/></linearGradient></defs>' +
        '<path d="M18 8 h28 a4 4 0 0 1 4 4 v140 a18 22 0 0 1 -36 0 V12 a4 4 0 0 1 4 -4z" fill="url(#g-glass)" stroke="#64748b" stroke-width="1.4"/>' +
        '<path d="M22 16 v148" stroke="#fff" stroke-opacity=".55" stroke-width="4" stroke-linecap="round"/>' +
        '<rect x="16" y="4" width="32" height="8" rx="2" fill="#e2e8f0" stroke="#94a3b8"/>' +
        '<g class="fx-powder" visibility="hidden"><ellipse cx="32" cy="158" rx="11" ry="7" fill="#6b21a8"/><ellipse cx="28" cy="154" rx="4" ry="3" fill="#a855f7"/></g>' +
        '<g class="fx-zinc" visibility="hidden"><rect x="24" y="148" width="16" height="8" rx="1" fill="#94a3b8"/><rect x="26" y="150" width="6" height="4" fill="#e2e8f0"/></g>' +
        '<g class="fx-marble" visibility="hidden"><circle cx="28" cy="154" r="5" fill="#f8fafc" stroke="#cbd5e1"/><circle cx="36" cy="157" r="4" fill="#e2e8f0"/></g>' +
        '<g class="fx-acid" visibility="hidden"><path d="M20 120 h24 v36 a12 16 0 0 1 -24 0z" fill="#38bdf8" opacity=".45"/><ellipse cx="32" cy="120" rx="12" ry="4" fill="#7dd3fc" opacity=".6"/></g>'
    },
    lamp: {
      w: 108, h: 136, label: "酒精灯",
      outline: "M44 18 h20 v16 h10 a38 32 0 1 1 -40 0 h10z",
      paint: '<defs><linearGradient id="g-amber" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fde68a"/><stop offset=".45" stop-color="#f59e0b"/><stop offset="1" stop-color="#b45309"/></linearGradient></defs>' +
        '<path d="M20 54 h68 v48 a34 20 0 0 1 -68 0z" fill="url(#g-amber)" stroke="#92400e" stroke-width="1.4"/>' +
        '<path d="M20 54 h68 v38 a34 18 0 0 1 -68 0z" fill="#fbbf24" opacity=".35"/>' +
        '<ellipse cx="54" cy="54" rx="34" ry="8" fill="#fde68a"/>' +
        '<path d="M24 62 v48" stroke="#fff" stroke-opacity=".35" stroke-width="6"/>' +
        '<rect x="42" y="30" width="24" height="26" rx="3" fill="#78716c"/>' +
        '<rect x="46" y="22" width="16" height="12" rx="2" fill="#a8a29e"/>' +
        '<rect x="51" y="16" width="6" height="10" fill="#e7e5e4"/>' +
        '<g class="fx-flame" visibility="hidden">' +
        '<ellipse cx="54" cy="14" rx="10" ry="16" fill="#f97316" opacity=".9"/>' +
        '<ellipse cx="54" cy="16" rx="5" ry="10" fill="#fde68a"/>' +
        '</g>'
    },
    delivery: {
      w: 250, h: 96, label: "导管",
      outline: "M6 12 h154 q28 0 28 26 v40 h8 v16 h-24 V42 q0 -10 -14 -10 H6z",
      paint: '<path d="M10 20 h148 q22 0 22 20 v34" fill="none" stroke="#94a3b8" stroke-width="9" stroke-linecap="round"/>' +
        '<path d="M10 20 h148 q22 0 22 20 v34" fill="none" stroke="#e0f2fe" stroke-width="5" stroke-linecap="round"/>' +
        '<path d="M180 74 h28" fill="none" stroke="#475569" stroke-width="7" stroke-linecap="round"/>' +
        '<circle cx="10" cy="20" r="5" fill="#cbd5e1"/>'
    },
    trough: {
      w: 230, h: 96, label: "水槽",
      outline: "M10 22 h210 v8 H26 v48 h178 v8 H10z",
      paint: '<rect x="8" y="18" width="214" height="70" rx="6" fill="#e0f2fe" stroke="#0369a1" stroke-width="2.2"/>' +
        '<rect x="14" y="36" width="202" height="46" rx="4" fill="#38bdf8" opacity=".42" class="fx-trough-water"/>' +
        '<ellipse cx="115" cy="38" rx="100" ry="7" fill="#7dd3fc" opacity=".55"/>' +
        '<path d="M16 28 v48" stroke="#fff" stroke-opacity=".4" stroke-width="5"/>'
    },
    bottle: {
      w: 100, h: 168, label: "集气瓶",
      outline: "M38 4 h24 v16 h12 v8 H26 v112 a28 18 0 0 0 48 0 V28 H62 V20 H38z",
      paint:         '<path d="M38 4 h24 v16 h12 v8 H26 v112 a28 18 0 0 0 48 0 V28 H62 V20 H38z" fill="url(#g-glass)" stroke="#64748b" stroke-width="1.5"/>' +
        '<rect x="36" y="2" width="28" height="10" rx="2" fill="#e2e8f0" stroke="#94a3b8"/>' +
        '<path d="M36 36 v110" stroke="#fff" stroke-opacity=".5" stroke-width="5"/>' +
        '<g class="fx-gas" visibility="hidden"><rect x="34" y="70" width="32" height="70" fill="#f8fafc" opacity=".55"/></g>' +
        '<g class="fx-bottle-water" visibility="hidden"><rect x="32" y="130" width="36" height="18" fill="#38bdf8" opacity=".45"/></g>'
    },
    splint: {
      w: 32, h: 156, label: "木条",
      outline: "M10 8 h12 v140 h-12z",
      paint: '<rect x="11" y="28" width="10" height="120" rx="2" fill="#b45309"/>' +
        '<rect x="12" y="30" width="3" height="110" fill="#fbbf24" opacity=".35"/>' +
        '<ellipse class="fx-splint" cx="16" cy="18" rx="10" ry="12" fill="#fbbf24" opacity=".85"/>'
    },
    beaker: {
      w: 124, h: 146, label: "烧杯",
      outline: "M14 8 h78 l8 6 10 -6 h8 l10 128 H10z",
      paint:         '<path d="M14 8 h78 l8 6 10 -6 h8 l10 128 H10z" fill="url(#g-glass)" stroke="#64748b" stroke-width="1.5"/>' +
        '<path d="M12 8 h100" stroke="#94a3b8" stroke-width="2.5"/>' +
        '<path d="M22 22 v100" stroke="#fff" stroke-opacity=".45" stroke-width="6"/>' +
        '<path d="M86 40 h10 M86 58 h10 M86 76 h10" stroke="#94a3b8" stroke-width="1"/>' +
        '<g class="fx-liquid"><path d="M24 78 h76 l4 50 h-84z" fill="#7dd3fc" opacity=".5"/><ellipse cx="62" cy="78" rx="38" ry="6" fill="#bae6fd" opacity=".65"/></g>' +
        '<g class="fx-metal" visibility="hidden"><rect x="48" y="96" width="28" height="10" rx="2" fill="#94a3b8"/></g>' +
        '<g class="fx-beaker-bubbles" visibility="hidden"><circle cx="44" cy="100" r="3" fill="#fff" opacity=".7"/><circle cx="62" cy="90" r="2.5" fill="#fff" opacity=".7"/><circle cx="78" cy="104" r="3" fill="#fff" opacity=".65"/></g>'
    },
    dropper: {
      w: 40, h: 132, label: "胶头滴管",
      outline: "M8 8 a12 14 0 0 1 24 0 v16 H22 v88 H18 V24 H8z",
      paint: '<ellipse cx="20" cy="18" rx="12" ry="14" fill="#ef4444"/>' +
        '<ellipse cx="20" cy="12" rx="6" ry="4" fill="#fecaca"/>' +
        '<rect x="16" y="30" width="8" height="88" rx="2" fill="#e0f2fe" stroke="#64748b"/>' +
        '<path d="M18 36 v70" stroke="#fff" stroke-opacity=".5" stroke-width="2"/>' +
        '<circle class="fx-drip" cx="20" cy="126" r="4" fill="#38bdf8" visibility="hidden"/>'
    },
    rod: {
      w: 188, h: 22, label: "玻璃棒",
      outline: "M6 6 h176 v10 h-176z",
      paint: '<rect x="6" y="6" width="176" height="10" rx="5" fill="#e2e8f0" stroke="#94a3b8"/>' +
        '<rect x="10" y="8" width="70" height="3" fill="#fff" opacity=".6"/>'
    },
    goggles: {
      w: 120, h: 50, label: "护目镜",
      outline: "M8 12 h104 v26 h-104z",
      paint: '<rect x="8" y="14" width="104" height="22" rx="10" fill="#0f766e"/>' +
        '<ellipse cx="40" cy="25" rx="16" ry="12" fill="#e0f2fe" stroke="#134e4a"/>' +
        '<ellipse cx="80" cy="25" rx="16" ry="12" fill="#e0f2fe" stroke="#134e4a"/>' +
        '<ellipse cx="36" cy="22" rx="5" ry="4" fill="#fff" opacity=".5"/>'
    },
    funnel: {
      w: 110, h: 140, label: "漏斗",
      outline: "M8 8 h94 L64 78 h4 v54 h-22 V78 H16z",
      paint: '<path d="M10 10 h90 L62 80 H48z" fill="url(#g-glass)" stroke="#0284c7" stroke-width="1.5"/>' +
        '<rect x="48" y="78" width="14" height="54" fill="#e0f2fe" stroke="#0284c7"/>' +
        '<path d="M22 18 L55 72" stroke="#fff" stroke-opacity=".45" stroke-width="4"/>' +
        '<g class="fx-filter-paper" visibility="hidden"><path d="M22 16 h66 L58 72 H52z" fill="#f8fafc" opacity=".88" stroke="#cbd5e1"/></g>' +
        '<g class="fx-residue" visibility="hidden"><ellipse cx="55" cy="40" rx="16" ry="8" fill="#a8a29e"/></g>'
    },
    paper: {
      w: 84, h: 84, label: "滤纸",
      outline: "M8 8 h68 v68 h-68z",
      paint: '<rect x="10" y="10" width="64" height="64" rx="3" fill="#fffef5" stroke="#d6d3d1"/>' +
        '<path d="M10 10 L74 74 M74 10 L10 74" stroke="#e7e5e4" stroke-width="1"/>' +
        '<circle cx="42" cy="42" r="22" fill="none" stroke="#d6d3d1"/>'
    },
    dish: {
      w: 128, h: 48, label: "蒸发皿",
      outline: "M12 14 Q64 2 116 14 L108 36 Q64 48 20 36z",
      paint: '<path d="M12 14 Q64 2 116 14 L108 36 Q64 48 20 36z" fill="#e2e8f0" stroke="#64748b" stroke-width="1.6"/>' +
        '<ellipse class="fx-dish-liquid" cx="64" cy="22" rx="42" ry="8" fill="#7dd3fc" opacity=".5"/>' +
        '<g class="fx-crystals" visibility="hidden"><rect x="40" y="18" width="8" height="8" fill="#e0f2fe" transform="rotate(20 44 22)"/><rect x="56" y="16" width="7" height="7" fill="#f8fafc" transform="rotate(35 60 20)"/><rect x="70" y="19" width="8" height="8" fill="#bae6fd" transform="rotate(12 74 23)"/></g>'
    },
    gauze: {
      w: 128, h: 24, label: "陶土网",
      outline: "M6 4 h116 v16 h-116z",
      paint: '<rect x="6" y="4" width="116" height="16" fill="#94a3b8"/>' +
        '<rect x="44" y="4" width="40" height="16" fill="#a8a29e"/>' +
        '<path d="M8 8 h112 M8 16 h112 M20 4 v16 M40 4 v16 M60 4 v16 M80 4 v16 M100 4 v16" stroke="#64748b" stroke-width=".6"/>'
    },
    cell: {
      w: 268, h: 118, label: "水槽",
      outline: "M10 20 h248 v10 H24 v68 h220 v10 H10z",
      paint: '<rect x="8" y="16" width="252" height="90" rx="6" fill="#e0f2fe" stroke="#0369a1" stroke-width="2"/>' +
        '<rect x="16" y="40" width="236" height="58" fill="#38bdf8" opacity=".4"/>' +
        '<rect x="70" y="8" width="8" height="98" fill="#94a3b8"/>' +
        '<rect x="190" y="8" width="8" height="98" fill="#cbd5e1"/>'
    },
    power: {
      w: 130, h: 74, label: "电源",
      outline: "M8 10 h114 v54 h-114z",
      paint: '<rect x="8" y="10" width="114" height="54" rx="6" fill="#111827"/>' +
        '<circle cx="36" cy="37" r="10" fill="#dc2626"/><text x="36" y="41" text-anchor="middle" fill="#fff" font-size="12">+</text>' +
        '<circle cx="94" cy="37" r="10" fill="#1d4ed8"/><text x="94" y="41" text-anchor="middle" fill="#fff" font-size="14">−</text>' +
        '<rect x="54" y="18" width="22" height="8" rx="2" fill="#22c55e"/>'
    },
    tubes: {
      w: 156, h: 176, label: "集气管",
      outline: "M20 6 h32 v158 a6 6 0 0 1 -32 0z M104 6 h32 v158 a6 6 0 0 1 -32 0z",
      paint: '<rect x="18" y="8" width="36" height="160" rx="4" fill="url(#g-glass)" stroke="#64748b"/>' +
        '<rect x="102" y="8" width="36" height="160" rx="4" fill="url(#g-glass)" stroke="#64748b"/>' +
        '<g class="fx-h2" visibility="hidden"><rect x="22" y="20" width="28" height="90" fill="#e0f2fe" opacity=".55"/></g>' +
        '<g class="fx-o2" visibility="hidden"><rect x="106" y="70" width="28" height="40" fill="#e0f2fe" opacity=".55"/></g>' +
        '<g class="fx-ratio" visibility="hidden"><text x="78" y="50" text-anchor="middle" fill="#0f766e" font-size="16" font-weight="700">2 : 1</text></g>'
    },
    balance: {
      w: 188, h: 108, label: "天平",
      outline: "M88 8 h12 v50 h-12z M10 58 h168 v12 h-168z M16 70 h52 v28 h-52z M120 70 h52 v28 h-52z",
      paint: '<rect x="90" y="8" width="8" height="52" fill="#57534e"/>' +
        '<rect x="12" y="56" width="164" height="10" rx="2" fill="#78716c"/>' +
        '<rect x="18" y="70" width="50" height="26" rx="3" fill="#a8a29e"/>' +
        '<rect x="120" y="70" width="50" height="26" rx="3" fill="#a8a29e"/>' +
        '<circle cx="94" cy="14" r="6" fill="#44403c"/>'
    },
    cylinder: {
      w: 58, h: 176, label: "量筒",
      outline: "M16 18 h26 v148 H16z M12 6 h34 v14 H12z",
      paint: '<rect x="16" y="10" width="26" height="156" rx="3" fill="url(#g-glass)" stroke="#0284c7"/>' +
        '<path d="M18 18 v140" stroke="#fff" stroke-opacity=".45" stroke-width="3"/>' +
        '<path d="M36 30 h8 M36 50 h8 M36 70 h8 M36 90 h8 M36 110 h8 M36 130 h8" stroke="#0284c7" stroke-width="1"/>' +
        '<rect x="14" y="6" width="30" height="8" rx="2" fill="#e0f2fe" stroke="#0284c7"/>'
    },
    wire: {
      w: 76, h: 156, label: "铁丝",
      outline: "M34 8 v90 M18 110 q18 28 40 0 q-18 20 -40 0",
      paint: '<path d="M38 8 v88" stroke="#78716c" stroke-width="4"/>' +
        '<path d="M20 108 q18 26 38 0 q-14 18 -38 4 q16 16 36 -2" fill="none" stroke="#a8a29e" stroke-width="3.5"/>'
    },
    cover: {
      w: 96, h: 20, label: "玻璃片",
      outline: "M6 4 h84 v12 h-84z",
      paint: '<rect x="6" y="4" width="84" height="12" rx="2" fill="#e0f2fe" stroke="#64748b" opacity=".85"/>'
    },
    lime_beaker: {
      w: 124, h: 146, label: "石灰水",
      outline: "M14 8 h78 l8 6 10 -6 h8 l10 128 H10z",
      paint:         '<path d="M14 8 h78 l8 6 10 -6 h8 l10 128 H10z" fill="url(#g-glass)" stroke="#64748b" stroke-width="1.5"/>' +
        '<path d="M22 22 v100" stroke="#fff" stroke-opacity=".45" stroke-width="6"/>' +
        '<g class="fx-lime-liquid"><path d="M24 78 h76 l4 50 h-84z" fill="#e2e8f0" opacity=".7"/><ellipse cx="62" cy="78" rx="38" ry="6" fill="#f8fafc" opacity=".7"/></g>'
    },
    reagent: {
      w: 72, h: 108, label: "药品",
      outline: "M26 4 h20 v14 h10 v8 H16 v66 a18 14 0 0 0 40 0 V26 H46 V18 H26z",
      paint: '<rect x="24" y="6" width="24" height="16" rx="2" fill="#78716c"/>' +
        '<path d="M18 22 h36 v72 a16 12 0 0 1 -36 0z" fill="#7c3aed" opacity=".8" stroke="#5b21b6"/>' +
        '<rect x="20" y="28" width="8" height="50" fill="#fff" opacity=".25"/>'
    }
  };

  var SCENES = {
    oxygen: [
      { id: "stand", x: 300, y: 20, label: "铁架台" },
      { id: "tube", x: 500, y: 20, label: "试管" },
      { id: "delivery", x: 620, y: 20, label: "导管" },
      { id: "splint", x: 900, y: 20, label: "木条" },
      { id: "wire", x: 900, y: 200, label: "铁丝" },
      { id: "paper", x: 900, y: 360, label: "试纸" },
      { id: "lamp", x: 300, y: 300, label: "酒精灯" },
      { id: "reagent", x: 500, y: 280, label: "药品" },
      { id: "bottle", x: 620, y: 160, label: "集气瓶" },
      { id: "cover", x: 760, y: 160, label: "玻璃片" },
      { id: "trough", x: 620, y: 360, label: "水槽" },
      { id: "lime_beaker", x: 760, y: 340, label: "石灰水" }
    ],
    neutralization: [
      { id: "goggles", x: 310, y: 24, label: "护目镜" },
      { id: "paper", x: 310, y: 120, label: "称量纸" },
      { id: "balance", x: 300, y: 320, label: "天平" },
      { id: "dropper", x: 500, y: 16, label: "胶头滴管" },
      { id: "beaker", x: 500, y: 180, label: "烧杯" },
      { id: "reagent", x: 500, y: 360, label: "药品" },
      { id: "rod", x: 700, y: 200, label: "玻璃棒" },
      { id: "cylinder", x: 820, y: 140, label: "量筒" }
    ],
    electrolysis: [
      { id: "power", x: 400, y: 20, label: "电源" },
      { id: "tubes", x: 400, y: 120, label: "集气管" },
      { id: "cell", x: 360, y: 340, label: "水槽" },
      { id: "reagent", x: 700, y: 340, label: "水" },
      { id: "splint", x: 860, y: 80, label: "木条" }
    ],
    filtration: [
      { id: "stand", x: 300, y: 40, label: "铁架台" },
      { id: "funnel", x: 500, y: 30, label: "漏斗" },
      { id: "paper", x: 660, y: 30, label: "滤纸" },
      { id: "rod", x: 820, y: 40, label: "玻璃棒" },
      { id: "beaker", x: 500, y: 280, label: "烧杯" },
      { id: "reagent", x: 700, y: 280, label: "浊液" }
    ],
    evaporation: [
      { id: "lamp", x: 320, y: 300, label: "酒精灯" },
      { id: "stand", art: "tripod", x: 480, y: 280, label: "三脚架" },
      { id: "gauze", x: 480, y: 40, label: "陶土网" },
      { id: "dish", x: 480, y: 120, label: "蒸发皿" },
      { id: "rod", x: 720, y: 40, label: "玻璃棒" },
      { id: "reagent", x: 720, y: 200, label: "溶液" }
    ]
  };

  function defsHtml() {
    return '<defs>' +
      '<linearGradient id="g-glass" x1="0" y1="0" x2="1" y2="0">' +
      '<stop offset="0" stop-color="#94a3b8" stop-opacity=".35"/>' +
      '<stop offset=".22" stop-color="#f8fafc" stop-opacity=".18"/>' +
      '<stop offset=".55" stop-color="#bae6fd" stop-opacity=".42"/>' +
      '<stop offset="1" stop-color="#0369a1" stop-opacity=".25"/></linearGradient>' +
      '<filter id="f-soft" x="-20%" y="-20%" width="140%" height="140%">' +
      '<feDropShadow dx="0" dy="3" stdDeviation="2.2" flood-color="#0f172a" flood-opacity=".18"/>' +
      '</filter>' +
      '</defs>';
  }

  function icon(id, size, color) {
    var a = ART[id] || ART.reagent;
    var w = size || 44;
    var h = Math.round(w * a.h / a.w);
    var paint = a.paint;
    if (color && id === "reagent") {
      paint = paint.replace("#7c3aed", color).replace("#5b21b6", color);
    }
    return '<svg xmlns="' + NS + '" viewBox="0 0 ' + a.w + " " + a.h + '" width="' + w + '" height="' + h + '">' + defsHtml() + paint + "</svg>";
  }

  function collectFx(root) {
    root.querySelectorAll("[class^='fx-'], [class*=' fx-']").forEach(function (n) {
      n.classList.forEach(function (c) {
        if (c.indexOf("fx-") === 0) {
          if (!fx[c]) fx[c] = [];
          fx[c].push(n);
        }
      });
    });
  }
  function vis(key, on) {
    (fx[key] || []).forEach(function (n) { n.setAttribute("visibility", on ? "visible" : "hidden"); });
  }

  function layout(kind) {
    slots = {}; pieces = {}; fx = {};
    var list = SCENES[kind] || SCENES.oxygen;
    list.forEach(function (spec) {
      var artId = spec.art || spec.id;
      var a = ART[artId] || ART.beaker;
      var slot = el("g", { "class": "slot", "data-slot": spec.id, transform: tf(spec) });
      slot.innerHTML = '<path class="slot-dash" d="' + a.outline + '" fill="none" stroke-linejoin="round" stroke-linecap="round"/>' +
        '<text class="slot-label" x="' + (a.w / 2) + '" y="' + (a.h + 16) + '" text-anchor="middle">' + (spec.label || a.label) + "</text>";
      slot.style.display = "none";
      slots[spec.id] = slot;
      svg.appendChild(slot);

      var piece = el("g", { "class": "piece", "data-piece": spec.id, transform: tf(spec), filter: "url(#f-soft)" });
      piece.innerHTML = a.paint;
      piece.style.display = "none";
      pieces[spec.id] = { el: piece, spec: spec, art: a };
      svg.appendChild(piece);
      collectFx(piece);
    });
    fx.pop = [el("text", { x: 760, y: 120, "class": "fx-pop", fill: "#dc2626", "font-size": "28", "font-weight": "700", visibility: "hidden" }, "爆鸣！")];
    svg.appendChild(fx.pop[0]);
    var jet = el("path", { d: "M210 128 q20 -28 8 -56", fill: "none", stroke: "#38bdf8", "stroke-width": "6", visibility: "hidden" });
    fx["fx-jet"] = [jet];
    svg.appendChild(jet);
    var sparks = el("g", { visibility: "hidden" },
      '<circle cx="560" cy="120" r="4" fill="#f97316"/><circle cx="580" cy="100" r="3" fill="#fbbf24"/><circle cx="540" cy="90" r="3" fill="#f97316"/>');
    fx["fx-sparks"] = [sparks];
    svg.appendChild(sparks);
    var steam = el("g", { visibility: "hidden" },
      '<ellipse cx="450" cy="140" rx="14" ry="8" fill="#cbd5e1" opacity=".45"/><ellipse cx="470" cy="118" rx="12" ry="7" fill="#e2e8f0" opacity=".4"/>');
    fx["fx-steam"] = [steam];
    svg.appendChild(steam);
  }

  function init(host, sceneKey) {
    host.innerHTML = "";
    svg = el("svg", { id: "bench", viewBox: "0 0 1000 520", preserveAspectRatio: "xMidYMid meet" });
    svg.innerHTML = defsHtml();
    host.appendChild(svg);
    layout(sceneKey || "oxygen");
  }

  function setSelecting(on, needMap) {
    selecting = !!on;
    needed = needMap || {};
    Object.keys(slots).forEach(function (k) {
      slots[k].style.display = selecting && needed[k] ? "" : "none";
      slots[k].classList.toggle("needed", !!(selecting && needed[k]));
    });
  }
  function hoverSlot(name) {
    Object.keys(slots).forEach(function (k) {
      slots[k].classList.toggle("hot", k === name);
    });
  }
  function setPiece(id, on) {
    if (!pieces[id]) return;
    pieces[id].el.dataset.placed = on ? "1" : "0";
    pieces[id].el.style.display = on ? "" : "none";
  }
  function applyEffects(st) {
    st = st || {};
    vis("fx-powder", !!st.powder);
    vis("fx-zinc", !!st.zinc);
    vis("fx-marble", !!st.marble);
    vis("fx-acid", !!st.acid);
    vis("fx-flame", !!st.flame || !!st.heat);
    vis("fx-gas", !!st.collected && !st.air_collect);
    vis("fx-bottle-water", !!st.bottle_water);
    vis("fx-drip", !!st.dripping);
    vis("fx-metal", !!st.metal);
    vis("fx-beaker-bubbles", !!st.acid_bubbles);
    vis("fx-h2", !!st.gases);
    vis("fx-o2", !!st.gases);
    vis("fx-ratio", !!st.ratio);
    vis("fx-filter-paper", !!st.paper);
    vis("fx-residue", !!st.residue);
    vis("fx-crystals", !!st.crystals);
    vis("fx-steam", !!st.heat);
    vis("fx-jet", !!st.jet_flame);
    vis("fx-sparks", !!st.sparks);
    vis("fx-pop", !!st.pop);
    if (pieces.trough) {
      var shown = pieces.trough.el.dataset.placed === "1" && !st.air_collect;
      pieces.trough.el.style.display = shown ? "" : "none";
    }
    if (pieces.tube) {
      var spec = Object.assign({}, pieces.tube.spec);
      if (st.upright) spec.r = 0;
      else if (st.tilt_up) spec.r = 26;
      else if (st.tilt_down) spec.r = -26;
      pieces.tube.el.setAttribute("transform", tf(spec));
    }
    (fx["fx-liquid"] || []).forEach(function (n) {
      var colors = { pink: "#f9a8d4", pale: "#fce7f3", clear: "#7dd3fc" };
      n.querySelectorAll("[fill]").forEach(function (p) {
        if (p.tagName.toLowerCase() !== "ellipse") p.setAttribute("fill", colors[st.liquid] || colors.clear);
      });
      if (st.filtrate === false) n.setAttribute("visibility", "hidden");
      if (st.filtrate) n.setAttribute("visibility", "visible");
    });
    (fx["fx-lime-liquid"] || []).forEach(function (n) {
      n.querySelectorAll("path").forEach(function (p) {
        p.setAttribute("fill", st.lime_milky ? "#f8fafc" : "#e2e8f0");
      });
    });
    (fx["fx-dish-liquid"] || []).forEach(function (n) {
      n.setAttribute("opacity", st.crystals ? "0.25" : "0.5");
    });
  }
  function clientToSvg(clientX, clientY) {
    if (!svg) return { x: 0, y: 0 };
    var ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    var pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    var p = pt.matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  }
  function specCenter(spec, art) {
    var s = spec.s || 1;
    var rad = (spec.r || 0) * Math.PI / 180;
    var lx = art.w * s * 0.5;
    var ly = art.h * s * 0.5;
    return {
      x: spec.x + lx * Math.cos(rad) - ly * Math.sin(rad),
      y: spec.y + lx * Math.sin(rad) + ly * Math.cos(rad)
    };
  }
  function snapR(spec, art) {
    var s = spec.s || 1;
    return Math.max(80, Math.max(art.w, art.h) * s * 0.55 + 48);
  }
  function hitSlot(clientX, clientY, preferId) {
    var p = clientToSvg(clientX, clientY);
    if (preferId && slots[preferId] && slots[preferId].style.display !== "none" && pieces[preferId]) {
      var ps = pieces[preferId].spec, pa = pieces[preferId].art;
      var pc = specCenter(ps, pa);
      if (Math.hypot(p.x - pc.x, p.y - pc.y) <= snapR(ps, pa) * 1.2) return preferId;
    }
    var best = "", bestD = 1e9;
    Object.keys(slots).forEach(function (k) {
      if (!slots[k] || slots[k].style.display === "none" || !pieces[k]) return;
      var spec = pieces[k].spec, art = pieces[k].art;
      var c = specCenter(spec, art);
      var d = Math.hypot(p.x - c.x, p.y - c.y);
      if (d <= snapR(spec, art) && d < bestD) { bestD = d; best = k; }
    });
    return best;
  }

  global.Lab2D = {
    init: init, icon: icon, setSelecting: setSelecting, hoverSlot: hoverSlot,
    setPiece: setPiece, applyEffects: applyEffects, hitSlot: hitSlot
  };
})(window);
