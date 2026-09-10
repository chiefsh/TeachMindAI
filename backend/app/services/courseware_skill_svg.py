"""把 skill 的 routed 规格画成静态 SVG（几何 / 曲线 / 反应步骤），供 PPT 导出。"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.courseware_svg import Page

CHEM = {
    "combustion_ch4": ("甲烷燃烧", "CH_4 + 2O_2", "CO_2 + 2H_2O"),
    "combustion_h2": ("氢气燃烧", "2H_2 + O_2", "2H_2O"),
    "electrolysis_water": ("电解水", "2H_2O", "2H_2 + O_2"),
    "redox_na_cl2": ("钠与氯气", "2Na + Cl_2", "2NaCl"),
    "esterification": ("酯化反应", "CH_3COOH + C_2H_5OH", "CH_3COOC_2H_5 + H_2O"),
    "glucose_combustion": ("葡萄糖氧化", "C_6H_{12}O_6 + 6O_2", "6CO_2 + 6H_2O"),
}

LAB = {
    "prep_oxygen_kmno4": ("制取氧气", "2KMnO_4", "K_2MnO_4+MnO_2+O_2"),
    "prep_hydrogen": ("制取氢气", "Zn + 2HCl", "ZnCl_2 + H_2"),
    "prep_co2": ("制取二氧化碳", "CaCO_3 + 2HCl", "CaCl_2+H_2O+CO_2"),
    "electrolysis": ("电解水", "2H_2O", "2H_2 + O_2"),
    "neutralization": ("酸碱中和", "HCl + NaOH", "NaCl + H_2O"),
    "metal_acid": ("金属与酸", "Zn + 2HCl", "ZnCl_2 + H_2"),
    "nh4hco3_decomp": ("碳酸氢铵分解", "NH_4HCO_3", "NH_3+CO_2+H_2O"),
    "iron_in_oxygen": ("铁丝在氧气中燃烧", "3Fe + 2O_2", "Fe_3O_4"),
    "filtration": ("过滤", "浊液", "滤液+残渣"),
    "evaporation": ("蒸发结晶", "溶液", "晶体+水蒸气"),
    "solution_prep": ("配制溶液", "溶质+水", "溶液"),
}

CURVE_TYPES = {
    "ellipse_dot_range": "ellipse",
    "ellipse_chord_range": "ellipse",
    "ellipse_area_max": "ellipse",
    "ellipse_slopeprod_const": "ellipse",
    "parabola_dot_const": "parabola",
    "hyperbola_ecc_range": "hyperbola",
}


def skill_payload(slide: dict) -> dict | None:
    raw = slide.get("skill")
    if isinstance(raw, dict) and raw.get("skill") and raw.get("problem_type"):
        return raw
    return None


def skill_steps(payload: dict) -> list[tuple[str, str]]:
    skill = payload.get("skill") or ""
    ptype = payload.get("problem_type") or ""
    spec = payload.get("spec") or {}
    if skill == "edu-chem-lab" or ptype in LAB:
        name, left, right = LAB.get(ptype, ("虚拟实验", "反应物", "生成物"))
        return [
            ("选取器材", "仪器与药品"),
            ("操作过程", name),
            ("现象与方程", f"${left} \\rightarrow {right}$"),
        ]
    if skill == "edu-chem-reaction" or ptype in CHEM:
        name, left, right = CHEM.get(ptype, ("化学反应", "反应物", "生成物"))
        return [
            ("反应物", f"${left}$"),
            ("过程", name),
            ("生成物", f"${right}$"),
        ]
    if skill == "edu-analytic-geometry" or ptype in CURVE_TYPES or ptype == "curve_explore":
        curve = _curve_kind(ptype, spec)
        labels = {
            "ellipse": ("椭圆", "焦点 $F_1,F_2$", r"$|PF_1|+|PF_2|=2a$"),
            "hyperbola": ("双曲线", "焦点与渐近线", r"$||PF_1|-|PF_2||=2a$"),
            "parabola": ("抛物线", "焦点与准线", r"$|PF|=$ 到准线距离"),
            "circle": ("圆", "圆心与半径", r"$|OP|=r$"),
        }
        a, b, c = labels.get(curve, labels["ellipse"])
        return [("曲线形状", a), ("定义要素", b), ("关键性质", c)]
    body = _solid_kind(ptype, spec)
    names = {
        "cube": "正方体", "cuboid": "长方体", "quad_pyramid": "正四棱锥",
        "tetrahedron": "正四面体", "tri_prism": "正三棱柱",
    }
    return [
        ("认识几何体", names.get(body, "多面体")),
        ("底面与高", "先标底面，再看高"),
        ("体积与表面积", "代入尺寸计算"),
    ]


def paint_skill_stage(p: Page, payload: dict, x: float, y: float, w: float, h: float) -> None:
    skill = payload.get("skill") or ""
    ptype = payload.get("problem_type") or ""
    spec = payload.get("spec") if isinstance(payload.get("spec"), dict) else {}
    if skill == "edu-chem-lab" or ptype in LAB:
        _paint_lab(p, ptype, x, y, w, h)
        return
    if skill == "edu-chem-reaction" or ptype in CHEM:
        _paint_chem(p, ptype, x, y, w, h)
        return
    if skill == "edu-analytic-geometry" or ptype in CURVE_TYPES or ptype == "curve_explore":
        _paint_curve(p, _curve_kind(ptype, spec), spec, x, y, w, h)
        return
    _paint_solid(p, _solid_kind(ptype, spec), spec, x, y, w, h)


def _solid_kind(ptype: str, spec: dict) -> str:
    if ptype == "solid_explore":
        body = str(spec.get("body") or "cuboid")
        return body if body in ("cube", "cuboid", "quad_pyramid", "tetrahedron", "tri_prism") else "cuboid"
    if ptype == "volume":
        return "cuboid"
    if ptype == "line_plane_angle":
        return "quad_pyramid" if str(spec.get("body") or "") == "pyramid" else "cube"
    if ptype == "dihedral":
        return "tetrahedron"
    return "cube"


def _curve_kind(ptype: str, spec: dict) -> str:
    if ptype == "curve_explore":
        curve = str(spec.get("curve") or "ellipse")
        return curve if curve in ("ellipse", "hyperbola", "parabola", "circle") else "ellipse"
    return CURVE_TYPES.get(ptype, "ellipse")


def _iso(x: float, y: float, z: float) -> tuple[float, float]:
    return (x - z) * 0.86, -y + (x + z) * 0.42


def _fit(pts: list[tuple[float, float]], x: float, y: float, w: float, h: float, pad: float = 28):
    xs, ys = zip(*pts)
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    bw, bh = max(maxx - minx, 1e-6), max(maxy - miny, 1e-6)
    s = min((w - 2 * pad) / bw, (h - 2 * pad) / bh)
    ox = x + w / 2 - (minx + maxx) / 2 * s
    oy = y + h / 2 - (miny + maxy) / 2 * s
    return [(ox + px * s, oy + py * s) for px, py in pts]


def _line(p: Page, a: tuple[float, float], b: tuple[float, float], color: str, width: float = 2) -> str:
    from app.services.courseware_svg import _r
    return (
        f'<path id="{p.nid("p")}" d="M {_r(a[0])} {_r(a[1])} L {_r(b[0])} {_r(b[1])}"'
        f' fill="none" stroke="{color}" stroke-width="{_r(width)}" stroke-linecap="round"/>'
    )


def _poly(p: Page, pts: list[tuple[float, float]], fill: str, fo: float, stroke: str) -> str:
    from app.services.courseware_svg import _r
    d = "M " + " L ".join(f"{_r(x)} {_r(y)}" for x, y in pts) + " Z"
    return (
        f'<path id="{p.nid("p")}" d="{d}" fill="{fill}" fill-opacity="{fo}"'
        f' stroke="{stroke}" stroke-width="1.6"/>'
    )


def _paint_solid(p: Page, body: str, spec: dict, x: float, y: float, w: float, h: float) -> None:
    th = p.th
    prim, acc = th["primary"], th["accent"]

    def n(key: str, default: float) -> float:
        try:
            v = float(spec.get(key, default))
        except (TypeError, ValueError):
            v = default
        return max(v, 0.4)

    if body == "cuboid":
        lx, ly, lz = n("lx", 3), n("ly", 4), n("lz", 5)
        m = max(lx, ly, lz)
        lx, ly, lz = lx / m, ly / m, lz / m
        pts3 = {
            "A": (0, 0, 0), "B": (lx, 0, 0), "C": (lx, 0, ly), "D": (0, 0, ly),
            "A1": (0, lz, 0), "B1": (lx, lz, 0), "C1": (lx, lz, ly), "D1": (0, lz, ly),
        }
        edges = [
            ("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"),
            ("A1", "B1"), ("B1", "C1"), ("C1", "D1"), ("D1", "A1"),
            ("A", "A1"), ("B", "B1"), ("C", "C1"), ("D", "D1"),
        ]
        faces = [
            ["A", "B", "C", "D"], ["A1", "B1", "C1", "D1"],
            ["A", "B", "B1", "A1"], ["D", "C", "C1", "D1"],
        ]
    elif body == "quad_pyramid":
        a, ht = n("base_edge", 4), n("height", 3)
        m = max(a, ht)
        a, ht = a / m, ht / m
        pts3 = {
            "A": (0, 0, 0), "B": (a, 0, 0), "C": (a, 0, a), "D": (0, 0, a),
            "P": (a / 2, ht, a / 2),
        }
        edges = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"), ("P", "A"), ("P", "B"), ("P", "C"), ("P", "D")]
        faces = [["A", "B", "C", "D"], ["P", "A", "B"], ["P", "B", "C"]]
    elif body == "tetrahedron":
        e = n("edge", 2)
        pts3 = {
            "A": (0, 0, 0), "B": (e, 0, 0),
            "C": (e * 0.5, 0, e * 0.87),
            "D": (e * 0.5, e * 0.82, e * 0.29),
        }
        edges = [("A", "B"), ("B", "C"), ("C", "A"), ("D", "A"), ("D", "B"), ("D", "C")]
        faces = [["A", "B", "C"], ["D", "A", "B"], ["D", "B", "C"]]
    elif body == "tri_prism":
        a, ht = n("base_edge", 2), n("height", 3)
        m = max(a, ht)
        a, ht = a / m, ht / m
        pts3 = {
            "A": (0, 0, 0), "B": (a, 0, 0), "C": (a * 0.5, 0, a * 0.87),
            "A1": (0, ht, 0), "B1": (a, ht, 0), "C1": (a * 0.5, ht, a * 0.87),
        }
        edges = [
            ("A", "B"), ("B", "C"), ("C", "A"),
            ("A1", "B1"), ("B1", "C1"), ("C1", "A1"),
            ("A", "A1"), ("B", "B1"), ("C", "C1"),
        ]
        faces = [["A", "B", "C"], ["A1", "B1", "C1"], ["A", "B", "B1", "A1"]]
    else:
        e = n("edge", 2)
        pts3 = {
            "A": (0, 0, 0), "B": (e, 0, 0), "C": (e, 0, e), "D": (0, 0, e),
            "A1": (0, e, 0), "B1": (e, e, 0), "C1": (e, e, e), "D1": (0, e, e),
        }
        edges = [
            ("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"),
            ("A1", "B1"), ("B1", "C1"), ("C1", "D1"), ("D1", "A1"),
            ("A", "A1"), ("B", "B1"), ("C", "C1"), ("D", "D1"),
        ]
        faces = [
            ["A", "B", "C", "D"], ["A1", "B1", "C1", "D1"],
            ["A", "B", "B1", "A1"], ["D", "C", "C1", "D1"],
        ]

    raw = [_iso(*pts3[k]) for k in pts3]
    mapped = dict(zip(pts3, _fit(raw, x, y, w, h)))
    bits = [p.rect(x, y, w, h, th["card"], rx=16)]
    for face in faces:
        bits.append(_poly(p, [mapped[k] for k in face], prim, 0.10, prim))
    for a, b in edges:
        bits.append(_line(p, mapped[a], mapped[b], prim, 2.2))
    p.group("ia-viz", x, y, w, h, "".join(bits))


def _paint_curve(p: Page, curve: str, spec: dict, x: float, y: float, w: float, h: float) -> None:
    from app.services.courseware_svg import _r
    th = p.th
    prim, acc, text = th["primary"], th["accent"], th["text"]
    cx, cy = x + w / 2, y + h / 2
    rx, ry = min(w, h) * 0.32, min(w, h) * 0.22
    bits = [p.rect(x, y, w, h, th["card"], rx=16)]
    # axes
    bits.append(_line(p, (x + 28, cy), (x + w - 28, cy), th["muted"], 1.2))
    bits.append(_line(p, (cx, y + 24), (cx, y + h - 24), th["muted"], 1.2))

    def num(key: str, default: float) -> float:
        try:
            return max(float(spec.get(key, default)), 0.2)
        except (TypeError, ValueError):
            return default

    if curve == "circle":
        r = min(w, h) * 0.28
        bits.append(
            f'<circle id="{p.nid("c")}" cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(r)}"'
            f' fill="none" stroke="{prim}" stroke-width="2.4"/>'
        )
        bits.append(p.circle(cx, cy, 5, acc, 1))
        bits.append(p.text(cx + 8, cy - 8, "O", 16, text, "600"))
    elif curve == "hyperbola":
        sa, sb = rx * 0.42, ry * 0.55
        d_right, d_left = [], []
        for i in range(21):
            yy = (-1.25 + 2.5 * i / 20) * sb
            xx = sa * math.sqrt(1 + (yy / max(sb, 1e-6)) ** 2)
            d_right.append((cx + xx, cy + yy))
            d_left.append((cx - xx, cy + yy))
        bits.append(_poly_open(p, d_right, prim))
        bits.append(_poly_open(p, d_left, prim))
        c = math.sqrt(sa * sa + sb * sb) * 0.55
        bits.append(p.circle(cx + c, cy, 5, acc, 1))
        bits.append(p.circle(cx - c, cy, 5, acc, 1))
    elif curve == "parabola":
        pts = []
        for i in range(25):
            t = -1.2 + 2.4 * i / 24
            pts.append((cx + (t * t) * rx * 0.7 - rx * 0.15, cy + t * ry * 1.35))
        bits.append(_poly_open(p, pts, prim))
        bits.append(p.circle(cx + rx * 0.18, cy, 5, acc, 1))
        bits.append(_line(p, (cx - rx * 0.35, y + 36), (cx - rx * 0.35, y + h - 36), acc, 1.6))
    else:
        bits.append(
            f'<ellipse id="{p.nid("e")}" cx="{_r(cx)}" cy="{_r(cy)}" rx="{_r(rx)}" ry="{_r(ry)}"'
            f' fill="none" stroke="{prim}" stroke-width="2.4"/>'
        )
        c = math.sqrt(max(rx * rx - ry * ry, 1))
        bits.append(p.circle(cx - c, cy, 5, acc, 1))
        bits.append(p.circle(cx + c, cy, 5, acc, 1))
        bits.append(p.text(cx - c, cy - 12, "F1", 16, text, "600", anchor="middle"))
        bits.append(p.text(cx + c, cy - 12, "F2", 16, text, "600", anchor="middle"))
        # 动点示意
        px, py = cx + rx * 0.55, cy - ry * 0.72
        bits.append(p.circle(px, py, 6, prim, 1))
        bits.append(_line(p, (px, py), (cx - c, cy), acc, 1.6))
        bits.append(_line(p, (px, py), (cx + c, cy), acc, 1.6))
        bits.append(p.text(px + 10, py - 6, "P", 16, text, "600"))
    p.group("ia-viz", x, y, w, h, "".join(bits))


def _poly_open(p: Page, pts: list[tuple[float, float]], color: str) -> str:
    from app.services.courseware_svg import _r
    d = "M " + " L ".join(f"{_r(x)} {_r(y)}" for x, y in pts)
    return (
        f'<path id="{p.nid("p")}" d="{d}" fill="none" stroke="{color}"'
        f' stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def _paint_lab(p: Page, ptype: str, x: float, y: float, w: float, h: float) -> None:
    th = p.th
    name, left, right = LAB.get(ptype, ("虚拟实验", "反应物", "生成物"))
    bits = [p.rect(x, y, w, h, th["card"], rx=16)]
    bits.append(p.text(x + w / 2, y + 36, "虚拟实验台 · " + name, 20, th["primary"], "700", anchor="middle"))
    bx, by, bw = x + w * 0.18, y + h * 0.58, w * 0.64
    bits.append(p.rect(bx, by, bw, h * 0.18, th["surface"], rx=8))
    cx, cy = x + w / 2, y + h * 0.42
    bits.append(
        f'<ellipse cx="{cx}" cy="{cy + 28}" rx="36" ry="14" fill="{th["accent"]}" fill-opacity="0.25"/>'
    )
    bits.append(
        f'<rect x="{cx - 14}" y="{cy - 40}" width="28" height="56" rx="10" '
        f'fill="{th["surface"]}" stroke="{th["primary"]}" stroke-width="2"/>'
    )
    preview = f"{left} → {right}".replace("_", "").replace("{", "").replace("}", "")
    bits.append(p.text(x + w / 2, y + h - 28, preview[:28], 16, th["text"], "600", anchor="middle"))
    p.group("ia-viz", x, y, w, h, "".join(bits))


def _paint_chem(p: Page, ptype: str, x: float, y: float, w: float, h: float) -> None:
    th = p.th
    name, left, right = CHEM.get(ptype, ("化学反应", "反应物", "生成物"))
    bits = [p.rect(x, y, w, h, th["card"], rx=16)]
    bits.append(p.text(x + w / 2, y + 48, name, 24, th["primary"], "700", anchor="middle"))
    gap = 16
    cw = (w - 64 - gap * 2) / 3
    labels = [("反应物", left), ("→", ""), ("生成物", right)]
    for i, (lab, tex) in enumerate(labels):
        xx = x + 32 + i * (cw + gap)
        yy = y + 90
        if lab == "→":
            bits.append(p.text(xx + cw / 2, yy + 70, "→", 36, th["accent"], "700", anchor="middle"))
            continue
        bits.append(p.rect(xx, yy, cw, 120, th["surface"], rx=12))
        bits.append(p.text(xx + 16, yy + 36, lab, 18, th["muted"], "600"))
        preview = tex.replace("_", "").replace("{", "").replace("}", "")
        bits.append(p.text(xx + 16, yy + 80, preview[:16], 22, th["text"], "700"))
    p.group("ia-viz", x, y, w, h, "".join(bits))
