#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析几何 skill runner（子进程入口）。

用法：
    python3 analytic_geometry_runner.py '<spec_json>' <out_html_path>

spec_json 至少含 problem_type：
    {"problem_type": "ellipse_dot_range"}                          # generate.py 里注册的固定示例题
    {"problem_type": "curve_explore", "curve": "ellipse", "a": 2, "b": 1}
    {"problem_type": "curve_explore", "curve": "hyperbola", "a": 2, "b": 1, "orient": "x"}
    {"problem_type": "curve_explore", "curve": "parabola", "p": 2, "axis": "x"}
    {"problem_type": "curve_explore", "curve": "circle", "r": 2}

进程隔离运行，避免与其它 skill 的同名模块冲突。
"""
import json
import sys
from pathlib import Path

# backend/app/services/skill_runners/analytic_geometry_runner.py -> parents[3] = backend
SKILL_DIR = Path(__file__).resolve().parents[3] / "skills" / "edu-analytic-geometry"
SCRIPTS_DIR = SKILL_DIR / "scripts"

CURVES = ("ellipse", "hyperbola", "parabola", "circle")


def _load_generate():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import generate  # noqa: E402
    return generate


def _num(spec: dict, key: str, default, lo=None):
    """取正数参数；非法或不在下界之上时回退默认值。"""
    try:
        v = float(spec.get(key, default))
    except (TypeError, ValueError):
        return default
    if v <= 0 or (lo is not None and v <= lo):
        return default
    return v


def _n(v: float) -> str:
    """浮点 → 表达式字面量（给前端表达式引擎用）。"""
    return repr(round(float(v), 10))


# ---------------------------------------------------------------------------
# 通用圆锥曲线画板（curve_explore）
#
# 不绑定某道题，而是把曲线本身做成可拖动的画板：曲线 + 焦点/顶点/准线/渐近线，
# 再挂一个沿曲线跑的动点，实时显示焦半径，并用「定值指示器」把第一定义
# （和为 2a / 差为 2a / 到焦点=到准线 / 到圆心为定值）当场演示出来。
# 覆盖「圆锥曲线的定义与几何性质」这类没有固定题面的知识点。
# ---------------------------------------------------------------------------
def _build_curve_explore(gen, spec: dict) -> dict:
    import sympy as sp
    conics, K = gen.conics, gen.K
    curve = str(spec.get("curve", "ellipse")).lower()
    if curve not in CURVES:
        raise ValueError(f"不支持的曲线: {curve}")

    fmt = gen.f      # sympy → float
    pt = gen.pt      # 静态点

    if curve == "ellipse":
        a = _num(spec, "a", 2.0)
        b = _num(spec, "b", 1.0)
        if abs(a - b) < 1e-9:
            b = a / 2                                   # a==b 是圆，避开 conics.ellipse 的报错
        E = conics.ellipse(sp.nsimplify(a), sp.nsimplify(b))
        A, B = fmt(E["a"]), fmt(E["b"])
        c, two = fmt(E["c"]), 2 * max(A, B)
        f1, f2 = E["foci"]["F1"], E["foci"]["F2"]
        f1x, f1y, f2x, f2y = fmt(f1[0]), fmt(f1[1]), fmt(f2[0]), fmt(f2[1])
        major = "x" if A > B else "y"

        points = {"O": pt((0, 0), "aux", "O"),
                  "F1": pt(f1, "fixed", "F₁", True), "F2": pt(f2, "fixed", "F₂", True)}
        for name, v in E["vertices"].items():
            points[name] = pt(v, "point", name)
        scalars = [
            {"name": "T", "expr": "t*PI/180"},
            {"name": "PX", "expr": f"{_n(A)}*cos(T)"},
            {"name": "PY", "expr": f"{_n(B)}*sin(T)"},
            {"name": "R1", "expr": f"sqrt((PX-({_n(f1x)}))*(PX-({_n(f1x)}))+(PY-({_n(f1y)}))*(PY-({_n(f1y)})))"},
            {"name": "R2", "expr": f"sqrt((PX-({_n(f2x)}))*(PX-({_n(f2x)}))+(PY-({_n(f2y)}))*(PY-({_n(f2y)})))"},
            {"name": "SUM", "expr": "R1+R2"},
        ]
        board = {
            "view": {"xRange": [-1.8 * max(A, c), 1.8 * max(A, c)],
                     "yRange": [-1.5 * max(B, c), 1.5 * max(B, c)]},
            "conics": [gen.conic_board(E, label=f"C: ${E['eq_latex']}$")],
            "points": points,
            "param": {"name": "t", "label": "动点参数角 $t$", "min": 0, "max": 360, "step": 1,
                      "value": 50, "unit": "°", "standard": 50, "ticks": ["0°", "180°", "360°"]},
            "scalars": scalars,
            "derived": [
                {"type": "point_on_conic", "name": "P", "conic": "C", "t": "@param",
                 "color": "ptA", "label": "P", "emphasis": True},
                {"type": "segment", "name": "s1", "a": "P", "b": "F1", "color": "vecA"},
                {"type": "segment", "name": "s2", "a": "P", "b": "F2", "color": "vecB"},
            ],
            "readouts": [
                {"id": "P", "label": "动点 P 坐标", "type": "coord", "of": "P", "color": "ptA"},
                {"id": "r1", "label": "焦半径 $|PF_1|$", "type": "distance", "a": "P", "b": "F1", "color": "vecA"},
                {"id": "r2", "label": "焦半径 $|PF_2|$", "type": "distance", "a": "P", "b": "F2", "color": "vecB"},
                {"id": "sum", "label": "$|PF_1|+|PF_2|$", "type": "expr", "expr": "SUM",
                 "digits": 3, "highlight": True},
            ],
            "constant": {"of": "sum", "label": f"$2a={K.tex(2 * max(E['a'], E['b']))}$"},
            "legend": [{"color": "fixed", "text": "焦点 F₁ F₂"}, {"color": "ptA", "text": "动点 P"},
                       {"color": "vecA", "text": "焦半径 PF₁"}, {"color": "vecB", "text": "焦半径 PF₂"}],
        }
        lesson = {
            "language": "zh-CN",
            "title": "椭圆的定义与几何性质",
            "problem": ("<p class='font-medium text-slate-800'>【探究】</p>"
                        f"<p>椭圆 $C:{E['eq_latex']}$。拖动滑块让点 $P$ 沿椭圆运动，"
                        "观察两条焦半径 $|PF_1|$、$|PF_2|$ 各自怎么变、它们的和又怎么变。</p>"),
            "answerLabel": "焦半径之和",
            "answer": f"${K.tex(2 * max(E['a'], E['b']))}$",
        }
        steps = [
            {"title": "标准方程与基本量",
             "content": (f"<p>椭圆的标准方程为 $${E['eq_latex']}$$</p>"
                         f"<p>半长轴 $a={K.tex(max(E['a'], E['b']))}$，半短轴 $b={K.tex(min(E['a'], E['b']))}$，"
                         f"半焦距 $c=\\sqrt{{a^2-b^2}}={K.tex(E['c'])}$，"
                         f"焦点在 ${major}$ 轴上。</p>")},
            {"title": "离心率决定椭圆的“扁”",
             "content": (f"<p>离心率 $e=\\dfrac{{c}}{{a}}={K.tex(E['ecc'])}$。</p>"
                         "<p>$e$ 越接近 $0$ 椭圆越圆，越接近 $1$ 越扁。它只与形状有关，与大小无关。</p>")},
            {"title": "第一定义：焦半径之和是定值",
             "content": ("<p>拖动滑块可以看到：$|PF_1|$ 和 $|PF_2|$ 各自一直在变，"
                         "但控制台里的 $|PF_1|+|PF_2|$ 始终不动。</p>"
                         f"<p>这正是椭圆的定义——到两定点距离之和等于定值 $2a$：</p>"
                         f"$$|PF_1|+|PF_2|={K.tex(2 * max(E['a'], E['b']))}$$")},
        ]
        return {"lesson": lesson, "steps": steps, "board": board}

    if curve == "hyperbola":
        a = _num(spec, "a", 1.0)
        b = _num(spec, "b", 1.0)
        orient = "y" if str(spec.get("orient", "x")).lower() == "y" else "x"
        H = conics.hyperbola(sp.nsimplify(a), sp.nsimplify(b), orient=orient)
        A, B, c = fmt(H["a"]), fmt(H["b"]), fmt(H["c"])
        f1, f2 = H["foci"]["F1"], H["foci"]["F2"]
        f1x, f1y, f2x, f2y = fmt(f1[0]), fmt(f1[1]), fmt(f2[0]), fmt(f2[1])

        points = {"O": pt((0, 0), "aux", "O"),
                  "F1": pt(f1, "fixed", "F₁", True), "F2": pt(f2, "fixed", "F₂", True)}
        for name, v in H["vertices"].items():
            points[name] = pt(v, "point", name)
        # 引擎里双曲线参数点走 cosh/sinh，这里用 exp 复刻同一条公式，保证读数与画面同源
        ch, sh = "(exp(s)+exp(-s))/2", "(exp(s)-exp(-s))/2"
        px = f"{_n(A)}*{ch}" if orient == "x" else f"{_n(B)}*{sh}"
        py = f"{_n(B)}*{sh}" if orient == "x" else f"{_n(A)}*{ch}"
        scalars = [
            {"name": "PX", "expr": px},
            {"name": "PY", "expr": py},
            {"name": "R1", "expr": f"sqrt((PX-({_n(f1x)}))*(PX-({_n(f1x)}))+(PY-({_n(f1y)}))*(PY-({_n(f1y)})))"},
            {"name": "R2", "expr": f"sqrt((PX-({_n(f2x)}))*(PX-({_n(f2x)}))+(PY-({_n(f2y)}))*(PY-({_n(f2y)})))"},
            {"name": "DIFF", "expr": "abs(R1-R2)"},
        ]
        rng = 2.2 * max(A, B, c)
        board = {
            "view": {"xRange": [-rng, rng], "yRange": [-0.75 * rng, 0.75 * rng]},
            "conics": [gen.conic_board(H, label=f"C: ${H['eq_latex']}$")],
            "points": points,
            "param": {"name": "s", "label": "动点参数 $s$", "min": -2.2, "max": 2.2, "step": 0.01,
                      "value": 0.8, "standard": 0.8, "ticks": ["-2.2", "0", "2.2"]},
            "scalars": scalars,
            "derived": [
                {"type": "point_on_conic", "name": "P", "conic": "C", "t": "@param",
                 "color": "ptA", "label": "P", "emphasis": True},
                {"type": "segment", "name": "s1", "a": "P", "b": "F1", "color": "vecA"},
                {"type": "segment", "name": "s2", "a": "P", "b": "F2", "color": "vecB"},
            ],
            "readouts": [
                {"id": "P", "label": "动点 P 坐标", "type": "coord", "of": "P", "color": "ptA"},
                {"id": "r1", "label": "焦半径 $|PF_1|$", "type": "distance", "a": "P", "b": "F1", "color": "vecA"},
                {"id": "r2", "label": "焦半径 $|PF_2|$", "type": "distance", "a": "P", "b": "F2", "color": "vecB"},
                {"id": "diff", "label": "$\\bigl||PF_1|-|PF_2|\\bigr|$", "type": "expr", "expr": "DIFF",
                 "digits": 3, "highlight": True},
            ],
            "constant": {"of": "diff", "label": f"$2a={K.tex(2 * H['a'])}$"},
            "legend": [{"color": "asymptote", "text": "渐近线"}, {"color": "fixed", "text": "焦点 F₁ F₂"},
                       {"color": "ptA", "text": "动点 P（单支）"}],
        }
        asym = K.tex(H["asymptote_slopes"][0])
        lesson = {
            "language": "zh-CN",
            "title": "双曲线的定义与渐近线",
            "problem": ("<p class='font-medium text-slate-800'>【探究】</p>"
                        f"<p>双曲线 $C:{H['eq_latex']}$。拖动滑块让点 $P$ 沿一支运动，"
                        "观察两条焦半径之差，以及曲线与虚线渐近线的关系。</p>"),
            "answerLabel": "焦半径之差的绝对值",
            "answer": f"${K.tex(2 * H['a'])}$",
        }
        steps = [
            {"title": "标准方程与基本量",
             "content": (f"<p>双曲线的标准方程为 $${H['eq_latex']}$$</p>"
                         f"<p>实半轴 $a={K.tex(H['a'])}$，虚半轴 $b={K.tex(H['b'])}$，"
                         f"半焦距 $c=\\sqrt{{a^2+b^2}}={K.tex(H['c'])}$，"
                         f"离心率 $e=\\dfrac{{c}}{{a}}={K.tex(H['ecc'])}>1$。</p>")},
            {"title": "渐近线：双曲线的走向",
             "content": (f"<p>渐近线斜率为 $\\pm{asym}$，画板上用虚线画出。</p>"
                         "<p>点 $P$ 跑得越远，曲线就越贴近渐近线，但永远不会相交——"
                         "渐近线决定了双曲线张开的“方向”。</p>")},
            {"title": "第一定义：焦半径之差是定值",
             "content": ("<p>拖动滑块，$|PF_1|$ 与 $|PF_2|$ 都在变，但它们差的绝对值不变：</p>"
                         f"$$\\bigl||PF_1|-|PF_2|\\bigr|=2a={K.tex(2 * H['a'])}$$"
                         "<p>这就是双曲线的定义。椭圆看“和”，双曲线看“差”。</p>")},
        ]
        return {"lesson": lesson, "steps": steps, "board": board}

    if curve == "parabola":
        p = _num(spec, "p", 2.0)
        axis = "y" if str(spec.get("axis", "x")).lower() == "y" else "x"
        Pa = conics.parabola(sp.nsimplify(p), axis=axis)
        pf = fmt(Pa["p"])
        focus = Pa["focus"]
        fx, fy = fmt(focus[0]), fmt(focus[1])
        d_at = fmt(Pa["directrix"][1])                  # 准线 x=-p/2 或 y=-p/2

        tmax = round(2.4 * max(pf, 1.0), 3)
        points = {"O": pt((0, 0), "aux", "O(顶点)"),
                  "F": pt(focus, "fixed", "F", True),
                  "Dref": {"xy": [d_at, 0] if axis == "x" else [0, d_at], "hidden": True}}
        # 准线：axis='x' 时为竖直线 x = -p/2（x = m y + c，m=0）；axis='y' 时为水平线
        if axis == "x":
            directrix = {"type": "line_x_eq_my_c", "name": "d", "m": 0, "c": d_at,
                         "color": "directrix", "dashed": True, "label": "准线"}
            px, py = "t*t/(2*" + _n(pf) + ")", "t"
            dist_dir = f"abs(PX-({_n(d_at)}))"
        else:
            directrix = {"type": "line_through_point_dir", "name": "d", "point": "Dref",
                         "dir": [1, 0], "color": "directrix", "dashed": True, "label": "准线"}
            px, py = "t", "t*t/(2*" + _n(pf) + ")"
            dist_dir = f"abs(PY-({_n(d_at)}))"
        scalars = [
            {"name": "PX", "expr": px},
            {"name": "PY", "expr": py},
            {"name": "RF", "expr": f"sqrt((PX-({_n(fx)}))*(PX-({_n(fx)}))+(PY-({_n(fy)}))*(PY-({_n(fy)})))"},
            {"name": "RD", "expr": dist_dir},
            {"name": "GAP", "expr": "abs(RF-RD)"},
        ]
        span = max(tmax * tmax / (2 * pf), tmax) * 1.25
        board = {
            "view": {"xRange": [-span, span], "yRange": [-0.75 * span, 0.75 * span]},
            "conics": [gen.conic_board(Pa, label=f"C: ${Pa['eq_latex']}$")],
            "points": points,
            "param": {"name": "t", "label": "动点参数 $t$", "min": -tmax, "max": tmax, "step": 0.01,
                      "value": round(0.8 * pf, 2), "standard": round(0.8 * pf, 2),
                      "ticks": [str(-tmax), "0", str(tmax)]},
            "scalars": scalars,
            "derived": [
                directrix,
                {"type": "point_on_conic", "name": "P", "conic": "C", "t": "@param",
                 "color": "ptA", "label": "P", "emphasis": True},
                {"type": "foot_perp", "name": "H", "point": "P", "line": "d", "color": "aux", "label": "H"},
                {"type": "segment", "name": "s1", "a": "P", "b": "F", "color": "vecA"},
                {"type": "segment", "name": "s2", "a": "P", "b": "H", "color": "vecB", "dashed": True},
            ],
            "readouts": [
                {"id": "P", "label": "动点 P 坐标", "type": "coord", "of": "P", "color": "ptA"},
                {"id": "rf", "label": "到焦点 $|PF|$", "type": "distance", "a": "P", "b": "F", "color": "vecA"},
                {"id": "rd", "label": "到准线 $|PH|$", "type": "distance", "a": "P", "b": "H", "color": "vecB"},
                {"id": "gap", "label": "$\\bigl||PF|-|PH|\\bigr|$", "type": "expr", "expr": "GAP",
                 "digits": 3, "highlight": True},
            ],
            "constant": {"of": "gap", "label": "$0$（两段恒等长）"},
            "legend": [{"color": "directrix", "text": "准线"}, {"color": "fixed", "text": "焦点 F"},
                       {"color": "vecA", "text": "PF"}, {"color": "vecB", "text": "PH（到准线）"}],
        }
        dir_eq = f"{Pa['directrix'][0]}={K.tex(Pa['directrix'][1])}"
        lesson = {
            "language": "zh-CN",
            "title": "抛物线的定义、焦点与准线",
            "problem": ("<p class='font-medium text-slate-800'>【探究】</p>"
                        f"<p>抛物线 $C:{Pa['eq_latex']}$。拖动滑块让点 $P$ 沿抛物线运动，"
                        "比较它到焦点的距离和到准线的距离。</p>"),
            "answerLabel": "到焦点与到准线的距离之差",
            "answer": "$0$",
        }
        steps = [
            {"title": "标准方程、焦点与准线",
             "content": (f"<p>抛物线的标准方程为 $${Pa['eq_latex']}$$</p>"
                         f"<p>其中 $p={K.tex(Pa['p'])}$，焦点 $F\\left({K.tex(focus[0])},{K.tex(focus[1])}\\right)$，"
                         f"准线 ${dir_eq}$。焦点到准线的距离恰为 $p$。</p>")},
            {"title": "定义：到焦点 = 到准线",
             "content": ("<p>拖动滑块，红色线段 $PF$ 与蓝色虚线段 $PH$ 的长度始终相等：</p>"
                         "$$|PF|=|PH|$$"
                         "<p>抛物线就是到定点（焦点）与到定直线（准线）距离相等的点的轨迹，"
                         "也可以说它的离心率恒为 $e=1$。</p>")},
            {"title": "焦半径公式",
             "content": (f"<p>把 $|PH|$ 写成坐标形式，就得到常用的焦半径公式（$axis={axis}$）：</p>"
                         + (f"$$|PF|=x_P+\\frac{{{K.tex(Pa['p'])}}}{{2}}$$" if axis == "x"
                            else f"$$|PF|=y_P+\\frac{{{K.tex(Pa['p'])}}}{{2}}$$")
                         + "<p>解抛物线的题时，把「到焦点的距离」换成「到准线的距离」往往能少算一大截。</p>")},
        ]
        return {"lesson": lesson, "steps": steps, "board": board}

    # circle
    r = _num(spec, "r", 2.0)
    cx = float(spec.get("cx", 0) or 0)
    cy = float(spec.get("cy", 0) or 0)
    C = conics.circle((sp.nsimplify(cx), sp.nsimplify(cy)), sp.nsimplify(r))
    R = fmt(C["r"])
    board = {
        "view": {"xRange": [cx - 2 * R, cx + 2 * R], "yRange": [cy - 1.5 * R, cy + 1.5 * R]},
        "conics": [gen.conic_board(C, label=f"C: ${C['eq_latex']}$")],
        "points": {"O": pt((cx, cy), "fixed", "圆心 O", True)},
        "param": {"name": "t", "label": "动点参数角 $t$", "min": 0, "max": 360, "step": 1,
                  "value": 50, "unit": "°", "standard": 50, "ticks": ["0°", "180°", "360°"]},
        "derived": [
            {"type": "point_on_conic", "name": "P", "conic": "C", "t": "@param",
             "color": "ptA", "label": "P", "emphasis": True},
            {"type": "segment", "name": "s1", "a": "O", "b": "P", "color": "vecA", "label": "半径"},
            {"type": "tangent_at", "name": "l", "conic": "C", "point": "P",
             "color": "line", "label": "切线"},
        ],
        "readouts": [
            {"id": "P", "label": "动点 P 坐标", "type": "coord", "of": "P", "color": "ptA"},
            {"id": "rad", "label": "$|OP|$", "type": "distance", "a": "O", "b": "P", "highlight": True},
        ],
        "constant": {"of": "rad", "label": f"$r={K.tex(C['r'])}$"},
        "legend": [{"color": "fixed", "text": "圆心 O"}, {"color": "vecA", "text": "半径 OP"},
                   {"color": "line", "text": "P 处的切线"}],
    }
    lesson = {
        "language": "zh-CN",
        "title": "圆的方程与切线",
        "problem": ("<p class='font-medium text-slate-800'>【探究】</p>"
                    f"<p>圆 $C:{C['eq_latex']}$。拖动滑块让点 $P$ 绕圆运动，"
                    "观察半径 $OP$ 的长度和 $P$ 处的切线。</p>"),
        "answerLabel": "半径长度",
        "answer": f"${K.tex(C['r'])}$",
    }
    steps = [
        {"title": "圆的标准方程",
         "content": (f"<p>圆心 $O({K.tex(C['center'][0])},{K.tex(C['center'][1])})$、"
                     f"半径 $r={K.tex(C['r'])}$ 的圆：</p>$${C['eq_latex']}$$")},
        {"title": "定义：到圆心的距离是定值",
         "content": ("<p>拖动滑块，$P$ 的坐标一直在变，但控制台里的 $|OP|$ 纹丝不动：</p>"
                     f"$$|OP|=r={K.tex(C['r'])}$$"
                     "<p>圆就是平面内到定点距离等于定长的点的集合。</p>")},
        {"title": "切线：与半径垂直",
         "content": ("<p>青色直线是 $P$ 处的切线。转一圈会发现它始终与半径 $OP$ 垂直——"
                     "这条性质是求圆的切线方程、算点到圆距离的出发点。</p>")},
    ]
    return {"lesson": lesson, "steps": steps, "board": board}


def build(spec: dict) -> dict:
    gen = _load_generate()
    ptype = spec.get("problem_type")
    if ptype == "curve_explore":
        return _build_curve_explore(gen, spec)
    if ptype in gen.REGISTRY:
        return gen.REGISTRY[ptype]()
    raise ValueError(f"不支持的 problem_type: {ptype}")


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: analytic_geometry_runner.py <spec_json> <out_html>", file=sys.stderr)
        return 2
    try:
        spec = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"spec JSON 解析失败: {e}", file=sys.stderr)
        return 2
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)

    gen = _load_generate()
    gen.render_html(build(spec), out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
