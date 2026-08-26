#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""立体几何 skill runner（子进程入口）。

用法：
    python3 solid_geometry_runner.py '<spec_json>' <out_html_path>

spec_json 至少含 problem_type，例如：
    {"problem_type": "line_plane_angle", "body": "pyramid", "base_edge": 2, "height": 1}
    {"problem_type": "line_plane_angle", "body": "cube"}
    {"problem_type": "volume", "lx": 3, "ly": 4, "lz": 5}
    {"problem_type": "solid_explore", "body": "quad_pyramid", "base_edge": 4, "height": 3}

进程隔离运行，避免与其它 skill 的同名模块（geometry_kernel 等）冲突。
"""
import json
import sys
from pathlib import Path

# backend/app/services/skill_runners/solid_geometry_runner.py -> parents[3] = backend
SKILL_DIR = Path(__file__).resolve().parents[3] / "skills" / "edu-solid-geometry"
SCRIPTS_DIR = SKILL_DIR / "scripts"


def _load_generate():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import generate  # noqa: E402
    return generate


def _int(spec: dict, key: str, default: int) -> int:
    try:
        v = int(spec.get(key, default))
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 通用立体图形探究台（solid_explore）
#
# 不绑定某道具体的题，而是把几何体本身做成可旋转的 3D 教具：棱长标注、底面与高
# 的高亮，加上 sympy 精确推出的体积、表面积。用来覆盖「认识棱柱棱锥」「体积表面积
# 公式」这类没有固定题面、但同样需要 3D 才讲得清的知识点。
# ---------------------------------------------------------------------------
SOLID_BODIES = ("cube", "cuboid", "quad_pyramid", "tetrahedron", "tri_prism")


def _tex(expr) -> str:
    import sympy as sp
    return sp.latex(sp.simplify(expr))


def _solid_body(gen, spec: dict) -> dict:
    """按 body 组装几何体素材：坐标、拓扑、计数、标注、体积与表面积推导。"""
    import sympy as sp
    gk, bodies = gen.gk, gen.bodies
    body = str(spec.get("body", "cube")).lower()

    if body in ("cuboid", "box", "rect_prism"):
        lx, ly, lz = _int(spec, "lx", 3), _int(spec, "ly", 4), _int(spec, "lz", 5)
        a, b, h = sp.Integer(lx), sp.Integer(ly), sp.Integer(lz)
        vol, area = a * b * h, sp.expand(2 * (a * b + b * h + a * h))
        return {
            "meta": "立体图形探究 · 长方体",
            "title": f"长方体 ABCD-A₁B₁C₁D₁ 的长、宽、高分别为 {lx}、{ly}、{lz}，认识它并求体积与表面积",
            "points": gk.cuboid(a, b, h),
            "topo": bodies.cuboid(),
            "counts": (8, 12, 6),
            "measures": [("A", "B", _tex(a)), ("A", "D", _tex(b)), ("A", "A1", _tex(h))],
            "base": ["A", "B", "C", "D"],
            "height": ("A", "A1"),
            "intro": (r"<p>长方体由三组互相平行的矩形围成。从同一个顶点 $A$ 出发的三条棱 "
                      r"$AB$、$AD$、$AA_1$ 两两垂直，正是它的长、宽、高：</p>"
                      rf"$$AB={_tex(a)},\quad AD={_tex(b)},\quad AA_1={_tex(h)}$$"),
            "vol_formula": r"V=\text{长}\times\text{宽}\times\text{高}",
            "vol_subst": rf"V={_tex(a)}\times{_tex(b)}\times{_tex(h)}={_tex(vol)}",
            "vol": vol,
            "area_formula": r"S=2(ab+bh+ah)",
            "area_subst": (rf"S=2\left({_tex(a)}\times{_tex(b)}+{_tex(b)}\times{_tex(h)}"
                           rf"+{_tex(a)}\times{_tex(h)}\right)={_tex(area)}"),
            "area": area,
        }

    if body in ("cube", "hexahedron"):
        e = _int(spec, "edge", 2)
        a = sp.Integer(e)
        vol, area = a ** 3, 6 * a ** 2
        return {
            "meta": "立体图形探究 · 正方体",
            "title": f"正方体 ABCD-A₁B₁C₁D₁ 的棱长为 {e}，认识它并求体积与表面积",
            "points": gk.cube(a),
            "topo": bodies.cuboid(),
            "counts": (8, 12, 6),
            "measures": [("A", "B", _tex(a)), ("A", "A1", _tex(a))],
            "base": ["A", "B", "C", "D"],
            "height": ("A", "A1"),
            "intro": (r"<p>正方体是六个面都为正方形的长方体，$12$ 条棱等长。</p>"
                      rf"<p>这里棱长 $a={_tex(a)}$，从顶点 $A$ 出发的三条棱两两垂直。</p>"),
            "vol_formula": r"V=a^3",
            "vol_subst": rf"V={_tex(a)}^3={_tex(vol)}",
            "vol": vol,
            "area_formula": r"S=6a^2\quad(\text{六个全等的正方形面})",
            "area_subst": rf"S=6\times{_tex(a)}^2={_tex(area)}",
            "area": area,
        }

    if body in ("quad_pyramid", "pyramid", "regular_quad_pyramid"):
        be, ht = _int(spec, "base_edge", 4), _int(spec, "height", 3)
        a, h = sp.Integer(be), sp.Integer(ht)
        base_area = a ** 2
        vol = gk.volume_pyramid(base_area, h)
        slant = sp.sqrt(h ** 2 + (a / 2) ** 2)              # 侧面斜高
        area = sp.simplify(base_area + 2 * a * slant)
        pts = gk.regular_quad_pyramid(a, h)
        topo = bodies.quad_pyramid(apex="P", base=("A", "B", "C", "D"))
        topo["spheres"] = topo["spheres"] + ["O"]
        return {
            "meta": "立体图形探究 · 正四棱锥",
            "title": f"正四棱锥 P-ABCD 的底面边长为 {be}、高为 {ht}，认识它并求体积与表面积",
            "points": pts,
            "topo": topo,
            "counts": (5, 8, 5),
            "measures": [("A", "B", _tex(a)), ("P", "O", _tex(h))],
            "base": ["A", "B", "C", "D"],
            "height": ("P", "O"),
            "intro": (r"<p>正四棱锥的底面是正方形，顶点 $P$ 在底面中心 $O$ 的正上方，"
                      r"因此 $PO\perp$ 底面 $ABCD$，$PO$ 就是这个棱锥的高。</p>"
                      rf"<p>底面边长 $a={_tex(a)}$，高 $h={_tex(h)}$。</p>"),
            "vol_formula": r"V=\frac13 S_{\text{底}}h",
            "vol_subst": (rf"S_{{\text{{底}}}}={_tex(a)}^2={_tex(base_area)},\quad "
                          rf"V=\frac13\times{_tex(base_area)}\times{_tex(h)}={_tex(vol)}"),
            "vol": vol,
            "area_formula": r"S=S_{\text{底}}+4\times\frac12 a h'\quad\left(h'=\sqrt{h^2+\left(\tfrac a2\right)^2}\ \text{为斜高}\right)",
            "area_subst": (rf"h'=\sqrt{{{_tex(h)}^2+\left(\frac{{{_tex(a)}}}{{2}}\right)^2}}={_tex(slant)},\quad "
                           rf"S={_tex(base_area)}+2\times{_tex(a)}\times{_tex(slant)}={_tex(area)}"),
            "area": area,
        }

    if body in ("tetrahedron", "tri_pyramid", "regular_tetrahedron"):
        e = _int(spec, "edge", 2)
        a = sp.Integer(e)
        pts = gk.regular_tetrahedron(a)
        pts["G"] = sp.simplify((pts["A"] + pts["B"] + pts["C"]) / 3)   # 底面重心，用来画高
        vol = gk.volume_tetra(pts["A"], pts["B"], pts["C"], pts["D"])
        area = sp.simplify(sp.sqrt(3) * a ** 2)
        height = sp.simplify(sp.sqrt(sum(c ** 2 for c in (pts["D"] - pts["G"]))))
        topo = bodies.tri_pyramid(apex="D", base=("A", "B", "C"))
        topo["spheres"] = topo["spheres"] + ["G"]
        return {
            "meta": "立体图形探究 · 正四面体",
            "title": f"正四面体 D-ABC 的棱长为 {e}，认识它并求体积与表面积",
            "points": pts,
            "topo": topo,
            "counts": (4, 6, 4),
            "measures": [("A", "B", _tex(a)), ("D", "G", _tex(height))],
            "base": ["A", "B", "C"],
            "height": ("D", "G"),
            "intro": (r"<p>正四面体的四个面都是全等的正三角形，六条棱等长。</p>"
                      rf"<p>取底面 $\triangle ABC$ 的重心 $G$，则 $DG\perp$ 底面，"
                      rf"$DG={_tex(height)}$ 就是它的高（棱长 $a={_tex(a)}$）。</p>"),
            "vol_formula": r"V=\frac13 S_{\text{底}}h=\frac{\sqrt2}{12}a^3",
            "vol_subst": rf"V=\frac{{\sqrt2}}{{12}}\times{_tex(a)}^3={_tex(vol)}",
            "vol": vol,
            "area_formula": r"S=4\times\frac{\sqrt3}{4}a^2=\sqrt3\,a^2",
            "area_subst": rf"S=\sqrt3\times{_tex(a)}^2={_tex(area)}",
            "area": area,
        }

    if body in ("tri_prism", "prism", "regular_tri_prism"):
        be, ht = _int(spec, "base_edge", 2), _int(spec, "height", 3)
        a, h = sp.Integer(be), sp.Integer(ht)
        pts = {
            "A": gk.V(0, 0, 0), "B": gk.V(a, 0, 0), "C": gk.V(a / 2, a * sp.sqrt(3) / 2, 0),
            "A1": gk.V(0, 0, h), "B1": gk.V(a, 0, h), "C1": gk.V(a / 2, a * sp.sqrt(3) / 2, h),
        }
        base_area = sp.simplify(sp.sqrt(3) / 4 * a ** 2)
        vol = gk.volume_prism(base_area, h)
        area = sp.simplify(2 * base_area + 3 * a * h)
        return {
            "meta": "立体图形探究 · 正三棱柱",
            "title": f"正三棱柱 ABC-A₁B₁C₁ 的底面边长为 {be}、高为 {ht}，认识它并求体积与表面积",
            "points": pts,
            "topo": bodies.prism(("A", "B", "C"), ("A1", "B1", "C1")),
            "counts": (6, 9, 5),
            "measures": [("A", "B", _tex(a)), ("A", "A1", _tex(h))],
            "base": ["A", "B", "C"],
            "height": ("A", "A1"),
            "intro": (r"<p>正三棱柱的上下底面是全等的正三角形，三条侧棱与底面垂直且相等，"
                      r"三个侧面都是矩形。</p>"
                      rf"<p>底面边长 $a={_tex(a)}$，侧棱（即高）$h={_tex(h)}$。</p>"),
            "vol_formula": r"V=S_{\text{底}}h",
            "vol_subst": (rf"S_{{\text{{底}}}}=\frac{{\sqrt3}}{{4}}\times{_tex(a)}^2={_tex(base_area)},\quad "
                          rf"V={_tex(base_area)}\times{_tex(h)}={_tex(vol)}"),
            "vol": vol,
            "area_formula": r"S=2S_{\text{底}}+3ah",
            "area_subst": (rf"S=2\times{_tex(base_area)}+3\times{_tex(a)}\times{_tex(h)}={_tex(area)}"),
            "area": area,
        }

    raise ValueError(f"不支持的几何体: {body}")


def _build_solid_explore(gen, spec: dict) -> dict:
    """把 _solid_body 的素材组装成 lesson.html 需要的 lesson / steps / model。"""
    info = _solid_body(gen, spec)
    gk = gen.gk
    pts = info["points"]

    span = max(float(abs(c)) for p in pts.values() for c in p) or 1.0
    tp = gk.to_three(pts, scale=3.0 / span)
    center = gen._centroid(tp)
    axis_size = gen.tp_span(tp)

    def cam(dx, dy, dz):
        return {"x": center[0] + dx, "y": center[1] + dy, "z": center[2] + dz}

    elements = {
        "Axis": {"type": "axes", "size": axis_size},
        "Base": {"type": "plane", "pts": info["base"]},
        "Height": {"type": "line", "a": info["height"][0], "b": info["height"][1],
                   "color": "emphasis", "depthTest": False},
    }
    for a, b, label in info["measures"]:
        elements[f"M_{a}{b}"] = {"type": "measure", "a": a, "b": b, "label": label}
    measure_keys = [k for k in elements if k.startswith("M_")]

    vcount, ecount, fcount = info["counts"]
    vol_tex, area_tex = _tex(info["vol"]), _tex(info["area"])

    model = {
        "target": center,
        "initialCamera": [center[0] + 5, center[1] + 4, center[2] + 6],
        "points": tp,
        "spheres": info["topo"]["spheres"],
        "edges": info["topo"]["edges"],
        "elements": elements,
    }
    lesson = {
        "language": "zh-CN",
        "meta": info["meta"],
        "title": info["title"],
        "answerLabel": "体积与表面积",
        "answerValue": f"$V={vol_tex},\\ S={area_tex}$",
    }
    steps = [
        {
            "title": "认识这个几何体",
            "content": (info["intro"] +
                        f"<p>它有 <b>{vcount}</b> 个顶点、<b>{ecount}</b> 条棱、<b>{fcount}</b> 个面。"
                        "拖动右侧 3D 场景可以任意旋转观察，滚轮缩放。</p>"),
            "highlight": ["Axis"] + measure_keys,
            "cameraPos": cam(5, 4, 6),
        },
        {
            "title": "找出底面和高",
            "content": (r"<p>蓝色高亮的是<b>底面</b>，洋红色线段是<b>高</b>——高必须垂直于底面，"
                        r"它是套用体积公式前唯一容易找错的量。</p>"
                        r"<p>转动一下几何体，从侧面看更容易确认这条高确实与底面垂直。</p>"),
            "highlight": ["Base", "Height"] + measure_keys,
            "cameraPos": cam(6, 2, 4),
        },
        {
            "title": "计算体积",
            "content": (r"<p>套用体积公式：</p>"
                        rf"$${info['vol_formula']}$$"
                        r"<p>代入本题数据：</p>"
                        rf"$${info['vol_subst']}$$"),
            "highlight": ["Base", "Height"] + measure_keys,
            "cameraPos": cam(5, 5, 5),
        },
        {
            "title": "计算表面积",
            "content": (r"<p>表面积是所有面的面积之和：</p>"
                        rf"$${info['area_formula']}$$"
                        rf"$${info['area_subst']}$$"
                        rf"<p>所以体积 $V={vol_tex}$，表面积 $S={area_tex}$。</p>"),
            "highlight": measure_keys,
            "cameraPos": cam(4, 4, 7),
        },
    ]
    return {"lesson": lesson, "steps": steps, "model": model, "_answer": area_tex}


def build(spec: dict):
    gen = _load_generate()
    ptype = spec.get("problem_type")

    if ptype == "solid_explore":
        return _build_solid_explore(gen, spec)

    if ptype == "line_plane_angle":
        body = str(spec.get("body", "pyramid")).lower()
        if body == "cube":
            return gen.build_cube_data()
        base_edge = _int(spec, "base_edge", 2)
        height = _int(spec, "height", 1)
        return gen.build_data(base_edge=base_edge, height=height)

    if ptype == "volume":
        lx = _int(spec, "lx", 3)
        ly = _int(spec, "ly", 4)
        lz = _int(spec, "lz", 5)
        return gen.build_box_volume_data(lx, ly, lz)

    if ptype == "skew_lines":
        return gen.build_cube_skew_lines_data(_int(spec, "edge", 1))

    if ptype == "dihedral":
        return gen.build_tetra_dihedral_data()

    if ptype == "point_plane_distance":
        return gen.build_cube_point_plane_distance_data(_int(spec, "edge", 1))

    raise ValueError(f"不支持的 problem_type: {ptype}")


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: solid_geometry_runner.py <spec_json> <out_html>", file=sys.stderr)
        return 2
    try:
        spec = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"spec JSON 解析失败: {e}", file=sys.stderr)
        return 2
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)

    gen = _load_generate()
    data = build(spec)
    # 自检：最终步骤须包含计算所得答案（与答案卡同源）
    answer = data.get("_answer")
    if answer is not None:
        assert answer in data["steps"][-1]["content"], "最终步骤未包含计算所得答案"
        data.pop("_answer", None)
    gen.render_html(data, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
