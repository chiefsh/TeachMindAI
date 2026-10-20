#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""物理知识点仿真页：把场景数据注入 template/explore.html。

用法：
    python3 scripts/generate.py <场景key> [输出.html]
    python3 scripts/generate.py list
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_DIR / "template" / "explore.html"
JS = SKILL_DIR / "template" / "explore.js"
BENCH_TEMPLATE = SKILL_DIR / "template" / "bench.html"
BENCH_ENGINES = {
    "circuit": SKILL_DIR / "template" / "circuit.js",
    "optics": SKILL_DIR / "template" / "optics.js",
}


def _inline_js(src: str) -> str:
    return src.replace("</script>", "<\\/script>").replace("</SCRIPT>", "<\\/SCRIPT>")


def _json_for_script(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def render_bench_html(data: dict, out_path: Path) -> Path:
    """实验台（器材库自由搭建）：共用 bench.html，按 engine 内联对应引擎脚本。"""
    template = BENCH_TEMPLATE.read_text(encoding="utf-8")
    if "__BENCH_DATA__" not in template or "__BENCH_JS__" not in template:
        raise RuntimeError("模板缺少 __BENCH_DATA__ / __BENCH_JS__")
    js = BENCH_ENGINES[data["engine"]].read_text(encoding="utf-8")
    html = template.replace("__BENCH_JS__", _inline_js(js))
    html = html.replace("__BENCH_DATA__", _json_for_script(data))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def render_html(data: dict, out_path: Path) -> Path:
    if data.get("engine") in BENCH_ENGINES:
        return render_bench_html(data, out_path)
    template = TEMPLATE.read_text(encoding="utf-8")
    if "__PHY_DATA__" not in template or "__PHY_JS__" not in template:
        raise RuntimeError("模板缺少 __PHY_DATA__ / __PHY_JS__")
    html = template.replace("__PHY_JS__", _inline_js(JS.read_text(encoding="utf-8")))
    html = html.replace("__PHY_DATA__", json.dumps(data, ensure_ascii=False))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _q(q, options, ok, explain):
    return {"q": q, "options": options, "ok": ok, "explain": explain}


def build_magnetic_field() -> dict:
    return {
        "id": "magnetic_field",
        "sim": "magnet",
        "needPlay": False,
        "title": "磁场与磁感线",
        "subtitle": "磁感线外部从 N 到 S，小磁针 N 极指向磁场方向",
        "badge": "初中物理 · 电磁",
        "hint": "拖动小磁针围着磁铁转一圈，看指针怎么转。可关掉磁感线，只留下指南针。",
        "intro": "磁体周围存在磁场。为了描述它，我们画出磁感线：疏密表示强弱，切线方向表示该点的磁场方向。外部 N→S，内部 S→N，形成闭合曲线。两条磁感线永不相交。",
        "toggles": [{"id": "lines", "label": "显示磁感线", "on": True}],
        "quiz": _q(
            "条形磁铁外部，磁感线的方向是？",
            [
                {"t": "从 N 极到 S 极", "ok": True},
                {"t": "从 S 极到 N 极", "ok": False, "why": "那是磁体内部的方向。"},
                {"t": "从地理北极到南极", "ok": False, "why": "地理方向和磁极不是一回事。"},
            ],
            "外部 N→S，内部 S→N，形成闭合曲线。",
            "磁场方向用小磁针 N 极来定义。",
        ),
    }


def build_emi() -> dict:
    return {
        "id": "electromagnetic_induction",
        "sim": "faraday",
        "title": "电磁感应",
        "subtitle": "磁通量变化才产生感应电流；增反减同",
        "badge": "初中 / 高中物理 · 电磁",
        "equation": "ε = n ΔΦ / Δt",
        "hint": "把磁铁推进线圈、再抽出来。电流计只在磁通量变化时偏转；停在里面不动就没有感应电流。",
        "intro": "闭合回路中磁通量变化时产生感应电动势。楞次定律：感应电流的磁场总要阻碍引起感应电流的磁通量变化（增反减同）。切忌说「有磁就有电」。",
        "quiz": _q(
            "产生感应电流的条件是？",
            [
                {"t": "闭合回路的磁通量发生变化", "ok": True},
                {"t": "回路附近有磁铁即可", "ok": False, "why": "磁铁静止时没有感应电流。"},
                {"t": "线圈必须接电池", "ok": False, "why": "电磁感应不需要外接电源。"},
            ],
            "闭合 + 磁通量变化。两者缺一不可。",
            "发电机就是不断改变线圈的磁通量。",
        ),
    }


def build_circuit() -> dict:
    return {
        "id": "circuit_series_parallel",
        "sim": "circuit",
        "needPlay": False,
        "title": "串并联电路",
        "subtitle": "串联一条路，并联多条路",
        "badge": "初中物理 · 电学",
        "hint": "点开关看灯亮灭。勾选「并联」后，干路开关管全电路，支路开关只管一盏。",
        "intro": "识别串并联：看电流路径。只有一条路就是串联；在某处分开再汇合就是并联。串联处处电流相等、电压相加；并联各支路电压相等、干路电流为支路之和。",
        "toggles": [{"id": "parallel", "label": "并联接法", "on": False}],
        "quiz": _q(
            "家里两盏灯，一盏坏了另一盏还能亮，它们是？",
            [
                {"t": "并联", "ok": True},
                {"t": "串联", "ok": False, "why": "串联一处断路会全部熄灭。"},
                {"t": "无法判断", "ok": False, "why": "互不影响是并联的特征。"},
            ],
            "家庭电路用并联，各用电器独立工作。",
            "总开关在干路，控制全屋。",
        ),
    }


def build_ohm() -> dict:
    return {
        "id": "ohm_law",
        "sim": "ohm",
        "title": "欧姆定律",
        "subtitle": "电流与电压成正比，与电阻成反比",
        "badge": "初中物理 · 电学",
        "equation": "I = U / R",
        "hint": "拉动电压和电阻滑条，看电流怎么变。电子运动快慢表示电流大小。",
        "intro": "欧姆定律定量描述这段电路中电流、电压、电阻的关系。变形：U = IR，R = U/I。电阻是导体本身的性质，不能说「电压越大电阻越大」。金属导体、温度不变时 R 为定值。",
        "controls": [
            {"id": "U", "label": "电压", "min": 1, "max": 12, "step": 0.5, "value": 6, "unit": " V"},
            {"id": "R", "label": "电阻", "min": 1, "max": 24, "step": 0.5, "value": 6, "unit": " Ω"},
        ],
        "toggles": [{"id": "electrons", "label": "显示电荷", "on": True}],
        "quiz": _q(
            "某导体两端电压变为原来的 2 倍，电阻不变，电流变为？",
            [
                {"t": "原来的 2 倍", "ok": True},
                {"t": "原来的 1/2", "ok": False, "why": "I 与 U 成正比。"},
                {"t": "不变", "ok": False, "why": "电压变了电流就会变。"},
                {"t": "原来的 4 倍", "ok": False, "why": "没有平方关系。"},
            ],
            "R 一定时，I 与 U 成正比。",
            "R = U/I 用来计算电阻，不表示 R 随 U 变。",
        ),
    }


def build_force() -> dict:
    return {
        "id": "force_composition",
        "sim": "forces",
        "needPlay": False,
        "title": "力的合成",
        "subtitle": "合力用平行四边形定则；不是简单相加",
        "badge": "初中 / 高中物理 · 力学",
        "hint": "拖动两个箭头的末端改方向，滑条改大小。绿色对角线就是合力。",
        "intro": "一个力如果产生的效果和几个力共同产生的效果相同，这个力就叫那几个力的合力。以两个分力为邻边作平行四边形，对角线表示合力。夹角越大合力越小；夹角大于 120° 时合力可以小于每一个分力。",
        "controls": [
            {"id": "F1", "label": "F₁", "min": 2, "max": 14, "step": 0.5, "value": 8, "unit": " N"},
            {"id": "F2", "label": "F₂", "min": 2, "max": 14, "step": 0.5, "value": 6, "unit": " N"},
        ],
        "quiz": _q(
            "两个大小相等的力，夹角从 0° 增大到 180°，合力怎么变？",
            [
                {"t": "一直变小", "ok": True},
                {"t": "一直变大", "ok": False, "why": "夹角越大合力越小。"},
                {"t": "先变大后变小", "ok": False, "why": "合力从 2F 减到 0。"},
            ],
            "夹角 0° 时合力最大（2F），180° 时最小（0）。",
            "同一直线上同向相加、反向相减，是平行四边形的特例。",
        ),
    }


def build_newton() -> dict:
    return {
        "id": "newton_laws",
        "sim": "newton",
        "title": "牛顿运动定律",
        "subtitle": "惯性 · F=ma · 有摩擦力时更接近真实",
        "badge": "初中 / 高中物理 · 力学",
        "equation": "F = ma",
        "hint": "拉「推力」滑条给木块加速。打开摩擦后，松手会停下；关掉摩擦则匀速滑下去。",
        "intro": "力不是维持运动的原因，而是改变运动状态的原因。F 必须是合力。匀速时合力为零，但仍可以有速度。质量是惯性大小的量度。",
        "controls": [
            {"id": "F", "label": "推力", "min": -12, "max": 12, "step": 0.5, "value": 0, "unit": " N"},
            {"id": "m", "label": "质量", "min": 0.5, "max": 8, "step": 0.5, "value": 2, "unit": " kg"},
        ],
        "toggles": [{"id": "friction", "label": "有摩擦", "on": False}],
        "quiz": _q(
            "汽车匀速直线行驶，关于牵引力和阻力，正确的是？",
            [
                {"t": "二力平衡，大小相等", "ok": True},
                {"t": "牵引力大于阻力", "ok": False, "why": "匀速说明合力为零。"},
                {"t": "不受力", "ok": False, "why": "受力但合力为零。"},
            ],
            "匀速 ⇒ a=0 ⇒ 合力为 0。",
            "力不是维持运动的原因。",
        ),
    }


def build_state() -> dict:
    return {
        "id": "state_change",
        "sim": "states",
        "title": "物态变化",
        "subtitle": "温度决定分子运动：固、液、气",
        "badge": "初中物理 · 热学",
        "hint": "拉动温度。0℃ 以下分子只在格子里振动；中间会流动；100℃ 以上飞散成气体。",
        "intro": "物质在固、液、气之间转化，同时伴随吸热或放热。熔化、汽化、升华吸热；凝固、液化、凝华放热。看到的「白气」是小水滴（液化），不是水蒸气。霜、雪是凝华。",
        "controls": [
            {"id": "T", "label": "温度", "min": -20, "max": 140, "step": 1, "value": 20, "unit": " ℃"},
        ],
        "quiz": _q(
            "冬天玻璃窗内侧出现冰花，属于？",
            [
                {"t": "凝华", "ok": True},
                {"t": "凝固", "ok": False, "why": "凝固是液体变固体；冰花是水蒸气直接变成冰晶。"},
                {"t": "液化", "ok": False, "why": "液化得到的是水，不是冰花。"},
                {"t": "升华", "ok": False, "why": "升华是固体直接变气体。"},
            ],
            "室内水蒸气遇到极冷玻璃，直接凝华为冰晶。",
            "霜也是凝华；露是液化。",
        ),
    }


def build_reflection() -> dict:
    return {
        "id": "light_reflection",
        "sim": "reflect",
        "needPlay": False,
        "title": "光的反射",
        "subtitle": "入射角等于反射角；光路可逆",
        "badge": "初中物理 · 光学",
        "equation": "i = r",
        "hint": "拖动橙色入射光线，或拉动滑条。角要从法线量起，不要从镜面量起。",
        "intro": "光射到界面上改变传播方向又回到原介质，叫反射。镜面反射和漫反射都遵守反射定律：i = r，三线共面，分居法线两侧。",
        "controls": [
            {"id": "i", "label": "入射角", "min": 5, "max": 80, "step": 1, "value": 40, "unit": "°"},
        ],
        "quiz": _q(
            "入射光线与镜面夹角 30°，反射角是？",
            [
                {"t": "60°", "ok": True},
                {"t": "30°", "ok": False, "why": "30° 是与镜面的夹角，入射角 = 90°−30° = 60°。"},
                {"t": "90°", "ok": False, "why": "反射角等于入射角 60°。"},
                {"t": "15°", "ok": False, "why": "没有折半。"},
            ],
            "入射角从法线量：90°−30°=60°，所以 r=60°。",
            "平面镜成像：等大、正立、虚像，像与物关于镜面对称。",
        ),
    }


def build_lens() -> dict:
    return {
        "id": "convex_lens",
        "sim": "lens",
        "needPlay": False,
        "title": "凸透镜成像",
        "subtitle": "一倍焦距分虚实，二倍焦距分大小",
        "badge": "初中物理 · 光学",
        "hint": "左右拖动物体，或拉动物距。观察像的虚实、倒正和大小如何随物距变化。",
        "intro": "口诀：物近像远像变大。u＞2f 倒立缩小实像（照相机）；f＜u＜2f 倒立放大实像（投影仪）；u＝f 不成像；u＜f 正立放大虚像（放大镜）。实像倒立能呈在光屏上，虚像正立只能用眼睛看。",
        "controls": [
            {"id": "u", "label": "物距", "min": 40, "max": 330, "step": 2, "value": 280, "unit": ""},
        ],
        "quiz": _q(
            "用放大镜看细字，物体应放在凸透镜的？",
            [
                {"t": "一倍焦距以内", "ok": True},
                {"t": "二倍焦距以外", "ok": False, "why": "那是照相机，成倒立缩小实像。"},
                {"t": "焦点上", "ok": False, "why": "不成像。"},
                {"t": "一倍和二倍焦距之间", "ok": False, "why": "那是投影仪，成倒立放大实像。"},
            ],
            "u＜f 才成正立放大虚像。",
            "口诀：一倍焦距分虚实，二倍焦距分大小。",
        ),
    }


def build_buoyancy() -> dict:
    return {
        "id": "buoyancy",
        "sim": "buoyancy",
        "title": "浮力",
        "subtitle": "浸在液体中的物体受到向上的浮力，大小等于排开液体的重力",
        "badge": "初中物理 · 力学",
        "equation": "F浮 = ρ液 g V排",
        "hint": "改物体密度和液体密度，看木块上浮、悬浮还是沉底。浮力只看排开了多少液体。",
        "intro": "阿基米德原理：浸在液体里的物体受到向上的浮力，大小等于它排开的那部分液体的重力。F浮＞G 上浮，F浮＝G 漂浮或悬浮，F浮＜G 下沉。浸没时同体积的铁块和木块浮力一样大。",
        "controls": [
            {"id": "rho", "label": "物体密度", "min": 0.2, "max": 2.0, "step": 0.1, "value": 0.6, "unit": ""},
            {"id": "liquid", "label": "液体密度", "min": 0.6, "max": 1.4, "step": 0.1, "value": 1.0, "unit": ""},
        ],
        "quiz": _q(
            "同样浸没在水中的铁块和木块（体积相同），浮力？",
            [
                {"t": "一样大", "ok": True},
                {"t": "铁块更大", "ok": False, "why": "浸没时 V排 相同，ρ液 相同，浮力相同。"},
                {"t": "木块更大", "ok": False, "why": "浮力不看物体密度。木块会再上浮，那是因为 F浮＞G。"},
            ],
            "浸没且 V 相同 ⇒ V排 相同 ⇒ 浮力相同。",
            "木块之所以浮起来，是因为重力比这份浮力小。",
        ),
    }


def build_projectile() -> dict:
    return {
        "id": "projectile_motion",
        "sim": "projectile",
        "title": "抛体运动",
        "subtitle": "水平匀速、竖直自由落体，合运动是抛物线",
        "badge": "高中物理 · 力学",
        "equation": "x = v₀t cosθ    y = v₀t sinθ − ½gt²",
        "hint": "改初速度和抛射角，点击画面发射。勾选「显示轨迹」留下抛物线。射程在 45° 最大。",
        "intro": "平抛是 θ=0 的特例。水平方向不受力，做匀速直线运动；竖直方向只受重力，做自由落体（或竖直上抛）。落地时间只由竖直方向决定，与水平速度无关。",
        "controls": [
            {"id": "v0", "label": "初速度", "min": 4, "max": 28, "step": 1, "value": 16, "unit": " m/s"},
            {"id": "ang", "label": "抛射角", "min": 5, "max": 85, "step": 1, "value": 45, "unit": "°"},
        ],
        "toggles": [{"id": "trail", "label": "显示轨迹", "on": True}],
        "quiz": _q(
            "同一高度平抛，只把水平初速度加倍，落地时间？",
            [
                {"t": "不变", "ok": True},
                {"t": "变为 1/2", "ok": False, "why": "落地时间由高度和 g 决定，与水平速度无关。"},
                {"t": "变为 2 倍", "ok": False, "why": "水平速度不参与竖直方向。"},
            ],
            "t = √(2h/g)，只看竖直。",
            "水平位移才会加倍。",
        ),
    }


def build_pendulum() -> dict:
    return {
        "id": "simple_pendulum",
        "sim": "pendulum",
        "title": "单摆",
        "subtitle": "小角度时 T = 2π√(L/g)，与振幅、质量无关",
        "badge": "高中物理 · 振动",
        "equation": "T = 2π √(L/g)",
        "hint": "拖动摆球拉开角度，看周期。改摆长，周期明显变；改质量，周期几乎不变。",
        "intro": "单摆在摆角很小（约 <10°）时近似简谐运动。周期只与摆长和重力加速度有关。摆角太大时周期会略变长，不再严格等于公式。",
        "controls": [
            {"id": "L", "label": "摆长", "min": 0.4, "max": 2.0, "step": 0.1, "value": 1.0, "unit": " m"},
            {"id": "m", "label": "摆球质量", "min": 0.1, "max": 2.0, "step": 0.1, "value": 0.5, "unit": " kg"},
        ],
        "quiz": _q(
            "把摆球质量加倍、摆长不变，小角度周期？",
            [
                {"t": "不变", "ok": True},
                {"t": "变为 √2 倍", "ok": False, "why": "公式里没有质量。"},
                {"t": "变为 2 倍", "ok": False, "why": "质量不进入周期。"},
            ],
            "T 只看 L 和 g。",
            "要改变周期，去改摆长。",
        ),
    }


def build_collision() -> dict:
    return {
        "id": "collision_momentum",
        "sim": "collision",
        "title": "碰撞与动量",
        "subtitle": "动量守恒；弹性碰撞动能也守恒",
        "badge": "高中物理 · 力学",
        "equation": "m₁v₁ + m₂v₂ = m₁v₁′ + m₂v₂′",
        "hint": "改两车质量和初速度，点播放看碰撞。关掉「弹性」就是完全非弹性，碰后粘在一起。",
        "intro": "水平光滑面上碰撞，系统动量守恒。弹性碰撞：动能也守恒，相对速度交换。完全非弹性：碰后共速，动能损失最大。",
        "controls": [
            {"id": "m1", "label": "m₁", "min": 0.5, "max": 8, "step": 0.5, "value": 2, "unit": " kg"},
            {"id": "m2", "label": "m₂", "min": 0.5, "max": 8, "step": 0.5, "value": 2, "unit": " kg"},
            {"id": "u1", "label": "v₁", "min": 0, "max": 12, "step": 0.5, "value": 6, "unit": " m/s"},
        ],
        "toggles": [{"id": "elastic", "label": "弹性碰撞", "on": True}],
        "quiz": _q(
            "光滑面上质量相等的两球，一动一静正碰（弹性），碰后？",
            [
                {"t": "速度交换：入射球停下，原静止球以原速度离开", "ok": True},
                {"t": "两球都停下", "ok": False, "why": "动量不能凭空消失。"},
                {"t": "入射球原速穿过", "ok": False, "why": "那不是宏观碰撞。"},
            ],
            "等质量弹性正碰速度交换。",
            "非弹性则会粘在一起，共同速度为原来的一半。",
        ),
    }


def build_circular() -> dict:
    return {
        "id": "circular_motion",
        "sim": "circular",
        "title": "匀速圆周运动",
        "subtitle": "速度沿切线，合力指向圆心，F = mv²/r",
        "badge": "高中物理 · 力学",
        "equation": "F = mv² / r    a = v² / r",
        "hint": "改半径和线速度。向心力箭头始终指向圆心；速度越大、半径越小，需要的向心力越大。",
        "intro": "匀速圆周运动速率不变，但速度方向一直在变，所以有向心加速度。提供向心力的可以是拉力、重力分力、库仑力等，不是一种新的力。",
        "controls": [
            {"id": "r", "label": "半径", "min": 0.4, "max": 2.2, "step": 0.1, "value": 1.2, "unit": " m"},
            {"id": "v", "label": "线速度", "min": 1, "max": 12, "step": 0.5, "value": 4, "unit": " m/s"},
            {"id": "m", "label": "质量", "min": 0.2, "max": 4, "step": 0.2, "value": 1, "unit": " kg"},
        ],
        "quiz": _q(
            "线速度不变，半径减半，所需向心力？",
            [
                {"t": "变为 2 倍", "ok": True},
                {"t": "变为 1/2", "ok": False, "why": "F = mv²/r，r 减半 F 加倍。"},
                {"t": "不变", "ok": False, "why": "分母变了。"},
            ],
            "F 与 r 成反比（v 一定）。",
            "急弯要减速，就是在减小所需向心力。",
        ),
    }


def build_incline() -> dict:
    return {
        "id": "incline_friction",
        "sim": "incline",
        "title": "斜面与摩擦",
        "subtitle": "下滑分力 mg sinθ，摩擦力 μN；θ 大于摩擦角才滑",
        "badge": "初中 / 高中物理 · 力学",
        "equation": "a = g (sinθ − μ cosθ)",
        "hint": "拉斜面倾角和动摩擦因数。木块会停在斜面上还是加速滑下，看 tanθ 和 μ 谁大。",
        "intro": "把重力沿斜面和垂直斜面分解。垂直方向平衡 N = mg cosθ。沿斜面：下滑力 mg sinθ，摩擦力 μN。刚要滑动时 tanθ = μ，这个角叫摩擦角。",
        "controls": [
            {"id": "th", "label": "倾角", "min": 5, "max": 55, "step": 1, "value": 30, "unit": "°"},
            {"id": "mu", "label": "动摩擦因数 μ", "min": 0, "max": 0.9, "step": 0.05, "value": 0.3, "unit": ""},
        ],
        "quiz": _q(
            "粗糙斜面上物体静止，增大倾角后开始下滑，是因为？",
            [
                {"t": "mg sinθ 增大到超过最大静摩擦", "ok": True},
                {"t": "重力变大了", "ok": False, "why": "重力没变，是分力变了。"},
                {"t": "支持力消失", "ok": False, "why": "支持力是 mg cosθ，还在。"},
            ],
            "临界条件 tanθ = μ。",
            "θ 越大，下滑分力越大、正压力越小，越容易滑。",
        ),
    }


def build_refraction() -> dict:
    return {
        "id": "light_refraction",
        "sim": "refract",
        "needPlay": False,
        "title": "光的折射",
        "subtitle": "n₁ sin i = n₂ sin r；光密到光疏可能全反射",
        "badge": "初中 / 高中物理 · 光学",
        "equation": "n₁ sin i = n₂ sin r",
        "hint": "拖动或拉动入射角。从水射向空气时，入射角大到临界角就会全反射，折射光线消失。",
        "intro": "光从一种介质进入另一种介质，传播方向改变叫折射。相对折射率 n = c/v。光从光密到光疏，折射角大于入射角；入射角 ≥ 临界角时发生全反射。",
        "controls": [
            {"id": "i", "label": "入射角", "min": 0, "max": 85, "step": 1, "value": 35, "unit": "°"},
            {"id": "n2", "label": "下方折射率 n", "min": 1.0, "max": 1.8, "step": 0.05, "value": 1.33, "unit": ""},
        ],
        "toggles": [{"id": "fromWater", "label": "从水中射向空气", "on": False}],
        "quiz": _q(
            "光从空气斜射入水，折射角与入射角相比？",
            [
                {"t": "折射角更小，光线靠近法线", "ok": True},
                {"t": "折射角更大", "ok": False, "why": "进入光密介质，折射角小于入射角。"},
                {"t": "一定相等", "ok": False, "why": "那是反射。"},
            ],
            "空气 n≈1，水 n≈1.33，sin r = sin i / 1.33。",
            "垂直入射时不偏折。",
        ),
    }


def build_coulomb() -> dict:
    return {
        "id": "coulomb_law",
        "sim": "coulomb",
        "needPlay": False,
        "title": "库仑定律",
        "subtitle": "同种电荷相斥，异种相吸；F 与距离平方成反比",
        "badge": "高中物理 · 电磁",
        "equation": "F = k |q₁ q₂| / r²",
        "hint": "拖动右侧电荷。改电量正负看引力还是斥力。距离加倍，力变为 1/4。",
        "intro": "真空中两点电荷之间的静电力沿连线，大小与电荷量乘积成正比、与距离平方成反比。k = 9.0×10⁹ N·m²/C²。这是电场概念的起点。",
        "controls": [
            {"id": "q1", "label": "q₁", "min": -5, "max": 5, "step": 0.5, "value": 2, "unit": " μC"},
            {"id": "q2", "label": "q₂", "min": -5, "max": 5, "step": 0.5, "value": -2, "unit": " μC"},
        ],
        "quiz": _q(
            "两电荷距离变为原来的 2 倍，库仑力变为？",
            [
                {"t": "原来的 1/4", "ok": True},
                {"t": "原来的 1/2", "ok": False, "why": "平方反比，不是一次反比。"},
                {"t": "原来的 2 倍", "ok": False, "why": "距离增大力减小。"},
            ],
            "F ∝ 1/r²。",
            "电荷变号只改变方向，不改变大小。",
        ),
    }


def build_lever() -> dict:
    return {
        "id": "lever_balance",
        "sim": "lever",
        "needPlay": False,
        "title": "杠杆平衡",
        "subtitle": "动力 × 动力臂 = 阻力 × 阻力臂",
        "badge": "初中物理 · 机械",
        "equation": "F₁ L₁ = F₂ L₂",
        "hint": "拖动支点，或改两边砝码。力臂是支点到力的作用线的垂直距离。两边力矩相等就平衡。",
        "intro": "杠杆平衡条件：F₁L₁ = F₂L₂。省力杠杆动力臂更长，费距离；费力杠杆省距离。天平是等臂杠杆。",
        "controls": [
            {"id": "m1", "label": "左盘质量", "min": 1, "max": 10, "step": 0.5, "value": 3, "unit": " kg"},
            {"id": "m2", "label": "右盘质量", "min": 1, "max": 10, "step": 0.5, "value": 3, "unit": " kg"},
        ],
        "quiz": _q(
            "撬棍撬石头，手离支点更远是为了？",
            [
                {"t": "增大动力臂，用更小的力", "ok": True},
                {"t": "增大阻力", "ok": False, "why": "阻力是石头的重力，没变。"},
                {"t": "减小阻力臂就会更费力", "ok": False, "why": "减小阻力臂其实更省力。"},
            ],
            "动力臂越长越省力。",
            "同时手要移动更长的距离。",
        ),
    }


def build_pressure() -> dict:
    return {
        "id": "pressure",
        "sim": "pressure",
        "needPlay": False,
        "title": "压强",
        "subtitle": "固体 p = F/S；液体 p = ρgh，跟容器形状无关",
        "badge": "初中物理 · 力学",
        "equation": "p = F / S    p = ρ g h",
        "hint": "固体：改压力和受力面积。液体：改深度和密度，看容器底部压强。勾选「液体压强」切换。",
        "intro": "压强表示压力的作用效果。同样的力，面积越小压强越大（刀刃、滑雪板）。液体内部压强只取决于密度和深度，同一深度向各个方向都相等。",
        "controls": [
            {"id": "F", "label": "压力 F", "min": 10, "max": 200, "step": 5, "value": 50, "unit": " N"},
            {"id": "A", "label": "面积 S", "min": 10, "max": 200, "step": 5, "value": 50, "unit": " cm²"},
            {"id": "h", "label": "液体深度", "min": 0.1, "max": 2.0, "step": 0.1, "value": 0.8, "unit": " m"},
        ],
        "toggles": [{"id": "liquid", "label": "液体压强", "on": False}],
        "quiz": _q(
            "拦河坝底部比顶部修得更厚，主要是因为？",
            [
                {"t": "越深液体压强越大", "ok": True},
                {"t": "底部水的质量更大所以压力更大，与深度无关", "ok": False, "why": "液体压强公式是 ρgh，由深度决定。"},
                {"t": "大气压随高度增加", "ok": False, "why": "不是这个实验要说明的。"},
            ],
            "p = ρgh，h 越大 p 越大。",
            "同一深度，压强与容器粗细无关。",
        ),
    }


def build_energy() -> dict:
    return {
        "id": "mechanical_energy",
        "sim": "energy",
        "title": "动能与重力势能",
        "subtitle": "下落时势能减少、动能增加；只有重力做功时机械能守恒",
        "badge": "初中 / 高中物理 · 能量",
        "equation": "Eₖ = ½ mv²    Eₚ = mgh",
        "hint": "改质量和高度，点播放看小球滚下。注意动能与势能此消彼长，总和几乎不变。",
        "intro": "重力势能看高度，动能看速度。只有重力（或弹力）做功时机械能守恒。有摩擦时部分机械能转化为内能，动能会变少。",
        "controls": [
            {"id": "m", "label": "质量", "min": 0.5, "max": 5, "step": 0.5, "value": 2, "unit": " kg"},
            {"id": "H", "label": "高度", "min": 1, "max": 10, "step": 0.5, "value": 5, "unit": " m"},
        ],
        "toggles": [{"id": "friction", "label": "有摩擦（机械能不守恒）", "on": False}],
        "quiz": _q(
            "从同一斜面无摩擦滑下，质量不同的两物体到达底部时？",
            [
                {"t": "速率相同（mgh = ½mv²，m 消掉）", "ok": True},
                {"t": "质量大的更快", "ok": False, "why": "m 在等式两边约去。"},
                {"t": "质量小的更快", "ok": False, "why": "速率与质量无关。"},
            ],
            "v = √(2gh)，只看高度。",
            "动能并不相同：质量大的动能更大。",
        ),
    }


def build_spring() -> dict:
    return {
        "id": "spring_harmonic",
        "sim": "spring",
        "title": "弹簧振子",
        "subtitle": "回复力 F = −kx；小阻尼时做简谐运动，T = 2π√(m/k)",
        "badge": "高中物理 · 振动",
        "equation": "F = −kx    T = 2π √(m/k)",
        "hint": "改劲度系数和质量，看振动快慢。振幅由你拉开的距离决定，周期与振幅无关。",
        "intro": "弹簧振子是简谐运动的标准模型。平衡位置合力为零；偏离后回复力指向平衡位置且与位移成正比。动能与弹性势能相互转化，机械能守恒（忽略摩擦）。",
        "controls": [
            {"id": "k", "label": "劲度系数 k", "min": 4, "max": 40, "step": 1, "value": 16, "unit": " N/m"},
            {"id": "m", "label": "质量", "min": 0.2, "max": 3.0, "step": 0.1, "value": 1.0, "unit": " kg"},
            {"id": "A", "label": "振幅", "min": 0.1, "max": 1.2, "step": 0.1, "value": 0.8, "unit": " m"},
        ],
        "quiz": _q(
            "把振幅加倍、k 和 m 不变，周期？",
            [
                {"t": "不变", "ok": True},
                {"t": "变为 2 倍", "ok": False, "why": "简谐运动周期与振幅无关。"},
                {"t": "变为 1/2", "ok": False, "why": "公式里没有 A。"},
            ],
            "T 只看 m 和 k。",
            "振幅变大，只是能量变大、速度峰值变大。",
        ),
    }


def build_pulley() -> dict:
    return {
        "id": "pulley_block",
        "sim": "pulley",
        "needPlay": False,
        "title": "滑轮组与机械效率",
        "subtitle": "承担物重的绳子段数越多越省力；效率 η = W有 / W总",
        "badge": "初中物理 · 机械",
        "equation": "F = G / n    η = W有用 / W总 × 100%",
        "hint": "改承担段数 n 和动滑轮自重。理想情况 F=G/n；动滑轮越重，实际越费力、效率越低。",
        "intro": "定滑轮不省力只改方向；动滑轮省一半力。滑轮组用 n 段绳子承担物重。额外要提起动滑轮，所以实际拉力大于 G/n，机械效率小于 100%。",
        "controls": [
            {"id": "n", "label": "承担段数 n", "min": 1, "max": 5, "step": 1, "value": 2, "unit": ""},
            {"id": "G", "label": "物重 G", "min": 10, "max": 80, "step": 5, "value": 40, "unit": " N"},
            {"id": "Gp", "label": "动滑轮重", "min": 0, "max": 20, "step": 1, "value": 4, "unit": " N"},
        ],
        "quiz": _q(
            "用 2 段绳子的动滑轮匀速提升重物，不考虑摩擦和滑轮重，拉力约为？",
            [
                {"t": "物重的一半", "ok": True},
                {"t": "物重的两倍", "ok": False, "why": "动滑轮省力。"},
                {"t": "与物重相等", "ok": False, "why": "那是定滑轮。"},
            ],
            "理想动滑轮 F = G/2。",
            "实际还要加上动滑轮自重的一半。",
        ),
    }


def build_ampere() -> dict:
    return {
        "id": "ampere_force",
        "sim": "ampere",
        "title": "安培力",
        "subtitle": "通电导线在磁场中受力 F = BIL，方向用左手定则",
        "badge": "高中物理 · 电磁",
        "equation": "F = B I L    （B ⟂ I）",
        "hint": "改磁感应强度和电流。左手：磁感线穿掌心，四指电流，拇指受力。点播放看导线被推开。",
        "intro": "磁场对电流的作用力叫安培力。B、I、L 两两垂直时 F=BIL。电流反向或磁场反向，力就反向。电动机就是靠安培力转起来的。",
        "controls": [
            {"id": "B", "label": "磁感应强度 B", "min": 0.1, "max": 2.0, "step": 0.1, "value": 0.8, "unit": " T"},
            {"id": "I", "label": "电流 I", "min": 0.5, "max": 8, "step": 0.5, "value": 3, "unit": " A"},
            {"id": "L", "label": "导线长度", "min": 0.1, "max": 1.2, "step": 0.1, "value": 0.5, "unit": " m"},
        ],
        "toggles": [{"id": "flipB", "label": "磁场向外（点号）", "on": True}],
        "quiz": _q(
            "电流方向不变，把磁场反向，安培力？",
            [
                {"t": "方向反向，大小不变", "ok": True},
                {"t": "大小变为 0", "ok": False, "why": "B 只是换了方向。"},
                {"t": "大小和方向都不变", "ok": False, "why": "F 的方向由 B 与 I 共同决定。"},
            ],
            "F 垂直于 B 和 I 所在平面。",
            "电动机换向器就是在适时改变电流方向。",
        ),
    }


def build_capacitor() -> dict:
    return {
        "id": "parallel_capacitor",
        "sim": "capacitor",
        "needPlay": False,
        "title": "平行板电容器",
        "subtitle": "C = εS / d；电压一定时，电容越大储电荷越多",
        "badge": "高中物理 · 电磁",
        "equation": "C = ε₀ εᵣ S / d    Q = C U    E = U / d",
        "hint": "改正对面积和板间距离。电容跟面积成正比、跟距离成反比。勾选「接电源」看 Q 随 C 变。",
        "intro": "电容器用来储存电荷和电场能。平行板：正对面积越大、间距越小、电介质 εᵣ 越大，电容越大。接在电源上 U 不变，Q=CU；充电后断开则 Q 不变。",
        "controls": [
            {"id": "area", "label": "正对面积", "min": 20, "max": 200, "step": 10, "value": 100, "unit": " cm²"},
            {"id": "d", "label": "板间距 d", "min": 1, "max": 20, "step": 1, "value": 5, "unit": " mm"},
            {"id": "U", "label": "电压 U", "min": 1, "max": 24, "step": 1, "value": 12, "unit": " V"},
        ],
        "toggles": [{"id": "onBatt", "label": "接在电源上（U 一定）", "on": True}],
        "quiz": _q(
            "电容器始终接在电源上，把两板距离加倍，板间电场强度？",
            [
                {"t": "变为 1/2（E=U/d，U 不变）", "ok": True},
                {"t": "不变", "ok": False, "why": "接电源时 U 一定，d 变则 E 变。"},
                {"t": "变为 2 倍", "ok": False, "why": "d 增大 E 减小。"},
            ],
            "接电源：U 不变，C 减半，Q 减半，E=U/d 减半。",
            "若充电后断开，Q 不变，情况就不同了。",
        ),
    }


def build_transformer() -> dict:
    return {
        "id": "transformer",
        "sim": "transformer",
        "needPlay": False,
        "title": "变压器",
        "subtitle": "理想变压器 U₁/U₂ = n₁/n₂，输入功率等于输出功率",
        "badge": "高中物理 · 电磁",
        "equation": "U₁ / U₂ = n₁ / n₂    I₁ / I₂ = n₂ / n₁",
        "hint": "改原副线圈匝数。升压变压器副线圈匝数更多，电流反而更小。",
        "intro": "变压器靠互感改变交流电压。理想情况下无损耗：P₁=P₂，所以升压必降流。高压输电就是为了减小导线上的 I²R 损耗。直流电不能用变压器。",
        "controls": [
            {"id": "n1", "label": "原线圈匝数 n₁", "min": 100, "max": 800, "step": 50, "value": 400, "unit": ""},
            {"id": "n2", "label": "副线圈匝数 n₂", "min": 50, "max": 800, "step": 50, "value": 200, "unit": ""},
            {"id": "U1", "label": "原线圈电压", "min": 10, "max": 220, "step": 10, "value": 220, "unit": " V"},
        ],
        "quiz": _q(
            "理想变压器把 220 V 降到 110 V，副线圈电流若为 2 A，原线圈电流？",
            [
                {"t": "1 A（电压减半则电流加倍在副边，原边电流减半）", "ok": True},
                {"t": "2 A", "ok": False, "why": "电流与匝数成反比。"},
                {"t": "4 A", "ok": False, "why": "原边电压更高，电流应更小。"},
            ],
            "n₁:n₂ = 2:1 时 I₁:I₂ = 1:2。",
            "P = UI 两边相等。",
        ),
    }


def build_gas() -> dict:
    return {
        "id": "ideal_gas",
        "sim": "gas",
        "title": "理想气体",
        "subtitle": "pV = nRT；分子越快、撞壁越狠，宏观压强越大",
        "badge": "初中 / 高中物理 · 热学",
        "equation": "pV = nRT",
        "hint": "改温度和体积。温度升高，分子运动加快、压强增大；体积减小，压强也增大。",
        "intro": "一定质量的理想气体：等温时 p 与 V 成反比（玻意耳）；等容时 p 与 T 成正比（查理）；等压时 V 与 T 成正比（盖·吕萨克）。微观上压强来自分子对器壁的碰撞。",
        "controls": [
            {"id": "T", "label": "温度 T", "min": 200, "max": 500, "step": 10, "value": 300, "unit": " K"},
            {"id": "V", "label": "体积 V", "min": 0.4, "max": 2.0, "step": 0.1, "value": 1.0, "unit": " L"},
        ],
        "quiz": _q(
            "一定质量理想气体，温度不变，体积减半，压强？",
            [
                {"t": "变为 2 倍", "ok": True},
                {"t": "变为 1/2", "ok": False, "why": "等温过程 pV 为常量。"},
                {"t": "不变", "ok": False, "why": "分子撞壁更频繁。"},
            ],
            "玻意耳定律：p₁V₁ = p₂V₂。",
            "T 必须用热力学温度。",
        ),
    }


def build_wave() -> dict:
    return {
        "id": "mechanical_wave",
        "sim": "wave",
        "title": "横波与纵波",
        "subtitle": "波传播的是振动形式；横波质点垂直于波向，纵波沿波向疏密",
        "badge": "初中 / 高中物理 · 波动",
        "equation": "v = λ f",
        "hint": "改波长和频率，波速 = 波长 × 频率。切换「纵波」看疏密相间，质点并不随波迁移。",
        "intro": "机械波要靠介质。质点只在平衡位置附近振动，并不随波跑走。横波有波峰波谷；纵波有疏部密部。声音在空气中是纵波。",
        "controls": [
            {"id": "lam", "label": "波长 λ", "min": 40, "max": 180, "step": 10, "value": 80, "unit": " px"},
            {"id": "f", "label": "频率 f", "min": 0.3, "max": 2.0, "step": 0.1, "value": 0.8, "unit": " Hz"},
        ],
        "toggles": [{"id": "longi", "label": "纵波（疏密）", "on": False}],
        "quiz": _q(
            "绳子上有一列横波向右传，绳子上的点怎么运动？",
            [
                {"t": "在平衡位置附近上下振动，不随波向右迁移", "ok": True},
                {"t": "跟着波峰一直向右跑", "ok": False, "why": "迁移的是振动形式，不是质点。"},
                {"t": "静止不动", "ok": False, "why": "有波经过时质点在振动。"},
            ],
            "波传能量和信息，不传介质本身。",
            "v=λf，介质一定时波速一定。",
        ),
    }


def build_doppler() -> dict:
    return {
        "id": "doppler_effect",
        "sim": "doppler",
        "title": "多普勒效应",
        "subtitle": "波源靠近观察者时频率变高，远离时变低",
        "badge": "高中物理 · 波动",
        "equation": "f′ = f · v / (v − vₛ)   （源向观察者）",
        "hint": "改波源速度。波源冲向右侧观察者时，右侧波长被压短、音调升高；左侧变稀疏。",
        "intro": "多普勒效应是波源或观察者相对介质运动时，接收频率发生变化。救护车驶来鸣笛更尖、驶离更沉。光也有多普勒，天文学用它测星系退行。",
        "controls": [
            {"id": "vs", "label": "波源速度", "min": 0, "max": 8, "step": 0.5, "value": 3, "unit": ""},
            {"id": "f0", "label": "固有频率", "min": 1, "max": 6, "step": 0.5, "value": 3, "unit": " Hz"},
        ],
        "quiz": _q(
            "火车驶离站台时，站台上的人听到汽笛声？",
            [
                {"t": "频率变低，听起来更沉", "ok": True},
                {"t": "频率变高", "ok": False, "why": "远离时波长被拉长。"},
                {"t": "频率不变，只是更响", "ok": False, "why": "响度是振幅，频率是音调。"},
            ],
            "源远离：f′ = f · v/(v+vₛ) < f。",
            "观察者不动、波源动，用分母修正。",
        ),
    }


def build_gravity() -> dict:
    return {
        "id": "gravitation_orbit",
        "sim": "gravity",
        "title": "万有引力与卫星",
        "subtitle": "万有引力提供向心力；轨道越高，线速度越小、周期越长",
        "badge": "高中物理 · 力学",
        "equation": "GMm / r² = m v² / r    v = √(GM / r)",
        "hint": "改轨道半径。近地卫星转得快、周期短；同步卫星轨道更高、周期是 24 小时量级。",
        "intro": "地面上的重力和天上卫星拐弯，其实是同一种力——万有引力。圆轨道上引力等于向心力。第一宇宙速度约 7.9 km/s，是近地圆轨道速度。",
        "controls": [
            {"id": "r", "label": "轨道半径 / R地", "min": 1.05, "max": 6.6, "step": 0.05, "value": 2.0, "unit": ""},
        ],
        "quiz": _q(
            "卫星轨道半径变大，线速度和周期怎么变？",
            [
                {"t": "线速度减小，周期变长", "ok": True},
                {"t": "都变大", "ok": False, "why": "v=√(GM/r)，r 大则 v 小。"},
                {"t": "线速度增大，周期变短", "ok": False, "why": "越高转得越慢。"},
            ],
            "T = 2π√(r³/GM)，r 越大 T 越大。",
            "同步卫星必须在赤道上空特定高度。",
        ),
    }


def build_photo() -> dict:
    return {
        "id": "photoelectric",
        "sim": "photo",
        "title": "光电效应",
        "subtitle": "光电子最大初动能只跟频率有关：Eₖ = hν − W，与强度无关",
        "badge": "高中物理 · 近代",
        "equation": "hν = W + Eₖ    ν₀ = W / h",
        "hint": "先把频率拉过截止频率，才有电子飞出。再加大光强，电子数目变多，但每个电子的动能不变。",
        "intro": "经典波动说无法解释：有截止频率、瞬时发生、动能与光强无关。爱因斯坦：光是一份一份的光子，一份能量 hν，大于逸出功才能打出电子。",
        "controls": [
            {"id": "nu", "label": "入射光频率", "min": 4, "max": 16, "step": 0.5, "value": 8, "unit": "×10¹⁴ Hz"},
            {"id": "I", "label": "光强", "min": 1, "max": 8, "step": 1, "value": 3, "unit": ""},
            {"id": "W", "label": "逸出功 W", "min": 1.5, "max": 4.5, "step": 0.1, "value": 2.3, "unit": " eV"},
        ],
        "quiz": _q(
            "已经发生光电效应，只增大光强、频率不变，则？",
            [
                {"t": "单位时间逸出的电子数增多，最大初动能不变", "ok": True},
                {"t": "每个电子动能变大", "ok": False, "why": "动能由 hν−W 决定，与光强无关。"},
                {"t": "截止频率变低", "ok": False, "why": "截止频率是金属的性质。"},
            ],
            "光强 ↔ 光子数；频率 ↔ 每个光子的能量。",
            "红光再亮也打不出电子，若它低于截止频率。",
        ),
    }


# ── 电学实验台（自由搭建）：器材库 + 接线柱连线 + 节点电压法求解 ──────────
# scene.parts: {id, type, x, y, rot, props}；wires: {a: [part_id, 接线柱], b: [...]}
# steps[].check 由 circuit.js 判定：closed_loop / lit / series / parallel / ammeter /
# voltmeter_across(target) / rheostat_in / records(min) / rated

def _part(pid, type_, x, y, rot=0, **props):
    return {"id": pid, "type": type_, "x": x, "y": y, "rot": rot, "props": props}


def build_circuit_lab_diy() -> dict:
    return {
        "engine": "circuit",
        "id": "circuit_lab_diy",
        "title": "电学实验台（自由搭建）",
        "subtitle": "从器材库取用器材，自由连接电路",
        "intro": {
            "purpose": "认识电路的基本组成，会用导线连接简单电路，会正确使用电流表和电压表。",
            "apparatus": ["电池组", "开关", "小灯泡", "定值电阻", "滑动变阻器", "电流表", "电压表", "导线若干"],
            "discussion": [
                "把电流表直接接在电源两极上会怎样？",
                "电压表串联在电路中，灯泡为什么不亮？",
            ],
        },
        "library": None,
        "scene": {"parts": [], "wires": []},
        "steps": [
            {"text": "从器材库拖出电池组、开关和小灯泡，连成闭合回路并闭合开关，让灯泡发光", "check": {"type": "lit", "min": 1},
             "ok": "灯泡亮了：电路形成了闭合回路"},
            {"text": "把电流表串联进电路，读出电流", "check": {"type": "ammeter"}, "ok": "电流表读数正常"},
            {"text": "把电压表并联在小灯泡两端，读出灯泡电压", "check": {"type": "voltmeter_across", "target": "bulb"},
             "ok": "电压表测到了灯泡两端电压"},
        ],
        "record": {"columns": ["U", "I", "R"]},
    }


def build_circuit_lab_series_parallel() -> dict:
    return {
        "engine": "circuit",
        "id": "circuit_lab_series_parallel",
        "title": "连接串联电路和并联电路",
        "subtitle": "动手连线，比较两种电路的特点",
        "intro": {
            "purpose": "会连接串联电路和并联电路，观察开关在不同位置的控制作用，比较两种电路中灯泡的工作情况。",
            "apparatus": ["电池组（3 V）", "开关 2 个", "小灯泡 2 个（2.5 V）", "导线若干"],
            "discussion": [
                "串联电路中取下一盏灯，另一盏还亮吗？并联呢？",
                "并联电路中，干路开关和支路开关分别控制什么？",
            ],
        },
        "library": ["battery", "switch", "bulb"],
        "scene": {
            "parts": [
                _part("p1", "battery", 300, 600, emf=3),
                _part("p2", "switch", 600, 600),
                _part("p3", "bulb", 420, 300),
                _part("p4", "bulb", 780, 300),
                _part("p5", "switch", 900, 600),
            ],
            "wires": [],
        },
        "steps": [
            {"text": "断开开关，把电池组、开关和灯 L1、L2 依次首尾相连，闭合开关让两灯同时发光（串联）",
             "check": {"type": "series", "n": 2}, "ok": "串联成功：电流只有一条路径"},
            {"text": "在串联电路中断开开关、或取下一盏灯，观察另一盏灯"},
            {"text": "把两盏灯分别接在两条支路上，闭合开关让两灯都发光（并联）",
             "check": {"type": "parallel", "n": 2}, "ok": "并联成功：两盏灯分别在两条支路上"},
            {"text": "比较串联、并联时灯泡的亮度，并试试把开关接在干路和支路上"},
        ],
        "quiz": [
            {
                "q": "串联两盏相同的灯泡，与并联时相比，每盏灯的亮度？",
                "options": [
                    {"t": "串联时更暗", "ok": True},
                    {"t": "串联时更亮", "ok": False, "why": "串联时每盏灯只分到一部分电压，功率变小。"},
                    {"t": "一样亮", "ok": False, "why": "在实验台上分别接一次，看看灯泡亮度的差别。"},
                ],
                "explain": "串联时两灯平分电源电压，每盏灯的电压和功率都比并联时小，所以更暗。",
            },
            {
                "q": "家里的电灯、电视机之间是怎样连接的？",
                "options": [
                    {"t": "并联", "ok": True},
                    {"t": "串联", "ok": False, "why": "串联时一个用电器断开，其他都不能工作。"},
                ],
                "explain": "家庭电路中各用电器并联，互不影响，各自两端电压都是 220 V。",
            },
        ],
    }


def build_circuit_lab_ohm() -> dict:
    return {
        "engine": "circuit",
        "id": "circuit_lab_ohm",
        "title": "探究电流与电压的关系（伏安法）",
        "subtitle": "保持电阻不变，改变电压，记录电流",
        "intro": {
            "purpose": "探究电阻一定时，通过导体的电流与导体两端电压的关系；学会用伏安法测电阻。",
            "apparatus": ["电池组（4.5 V）", "开关", "定值电阻（10 Ω）", "滑动变阻器（20 Ω）", "电流表", "电压表", "导线若干"],
            "discussion": [
                "滑动变阻器在这个实验中起什么作用？",
                "闭合开关前，滑片为什么要移到阻值最大处？",
            ],
        },
        "library": ["battery", "switch", "resistor", "rheostat", "ammeter", "voltmeter"],
        "scene": {
            "parts": [
                _part("p1", "battery", 300, 620, emf=4.5),
                _part("p2", "switch", 560, 620),
                _part("p3", "rheostat", 860, 600, Rmax="20", pos=1),
                _part("p4", "resistor", 440, 340, R=10),
                _part("p5", "ammeter", 780, 320),
                _part("p6", "voltmeter", 440, 140),
            ],
            "wires": [],
        },
        "steps": [
            {"text": "断开开关，把电池组、开关、定值电阻、滑动变阻器（一上一下）串联起来",
             "check": {"type": "rheostat_in"}, "ok": "滑动变阻器接入正确"},
            {"text": "把电流表串联进电路（电流从「0.6」流入，「−」流出），闭合开关", "check": {"type": "ammeter"},
             "ok": "电流表接法正确"},
            {"text": "把电压表并联在定值电阻两端", "check": {"type": "voltmeter_across", "target": "resistor"},
             "ok": "电压表测的是定值电阻两端电压"},
            {"text": "移动滑片改变电阻两端电压，至少记录 3 组 U、I 数据", "check": {"type": "records", "min": 3},
             "ok": "数据够了，看看右下角的 I–U 图像"},
        ],
        "record": {"columns": ["U", "I", "R"], "chart": "linear"},
        "quiz": [
            {
                "q": "电阻一定时，I–U 图像是什么形状？",
                "options": [
                    {"t": "一条过原点的直线", "ok": True},
                    {"t": "一条曲线", "ok": False, "why": "看看记录的数据点，它们落在哪种线上？"},
                    {"t": "一条水平线", "ok": False, "why": "电压变大时，电流也在变大。"},
                ],
                "explain": "电阻一定时，电流与电压成正比，图像是过原点的直线，斜率的倒数就是电阻。",
            },
        ],
    }


def build_circuit_lab_bulb_power() -> dict:
    return {
        "engine": "circuit",
        "id": "circuit_lab_bulb_power",
        "title": "测量小灯泡的电功率",
        "subtitle": "调到额定电压，读出额定电流",
        "intro": {
            "purpose": "用伏安法测量小灯泡在不同电压下的电功率，测出额定功率，观察灯泡亮度与实际功率的关系。",
            "apparatus": ["电池组（4.5 V）", "开关", "小灯泡（2.5 V 0.3 A）", "滑动变阻器（20 Ω）", "电流表", "电压表", "导线若干"],
            "discussion": [
                "小灯泡的亮度由什么决定？",
                "为什么不能求几次功率的平均值作为额定功率？",
            ],
        },
        "library": ["battery", "switch", "bulb", "rheostat", "ammeter", "voltmeter"],
        "scene": {
            "parts": [
                _part("p1", "battery", 300, 620, emf=4.5),
                _part("p2", "switch", 560, 620),
                _part("p3", "rheostat", 860, 600, Rmax="20", pos=1),
                _part("p4", "bulb", 440, 320, spec="2.5|0.3"),
                _part("p5", "ammeter", 780, 320),
                _part("p6", "voltmeter", 440, 120),
            ],
            "wires": [],
        },
        "steps": [
            {"text": "断开开关，把电池组、开关、小灯泡、滑动变阻器（一上一下）串联，滑片置于阻值最大处",
             "check": {"type": "rheostat_in"}, "ok": "滑动变阻器接入正确"},
            {"text": "电流表串联、电压表并联在小灯泡两端", "check": {"type": "voltmeter_across", "target": "bulb"},
             "ok": "电压表测的是小灯泡两端电压"},
            {"text": "移动滑片使电压表示数为 2.5 V，记录数据（额定功率）", "check": {"type": "rated"},
             "ok": "测到了额定状态下的数据"},
            {"text": "再测略低于、略高于额定电压的两组数据，比较亮度", "check": {"type": "records", "min": 3},
             "ok": "三组数据齐了，看看 I–U 图像"},
        ],
        "record": {"columns": ["U", "I", "P", "R"], "chart": "curve"},
        "quiz": [
            {
                "q": "为什么小灯泡的 I–U 图像不是直线？",
                "options": [
                    {"t": "灯丝电阻随温度升高而增大", "ok": True},
                    {"t": "电流表读数不准", "ok": False, "why": "每组数据的 R = U/I 都不一样，而且有规律。"},
                    {"t": "电源电压不稳定", "ok": False, "why": "电压表测的就是灯泡两端的实际电压。"},
                ],
                "explain": "电压越高，灯丝温度越高，电阻越大，所以 U/I 逐渐变大，图像向电压轴弯曲。",
            },
        ],
    }


# ── 光学实验台：激光 / 蜡烛 / 透镜 / 平面镜 / 玻璃砖 / 光屏，二维光线追迹 ──────────
# 长度单位 10 = 1 cm；rail 为光具座（其上的蜡烛、透镜、光屏只能左右移动）。
# steps[].check：hit(target) / tir / image(kind=reduced|equal|enlarged|virtual) / records(min)

_ANGLE_COLS_R = [{"k": "i", "label": "入射角 i / °"}, {"k": "r", "label": "反射角 r / °"}]
_ANGLE_COLS_G = [{"k": "i", "label": "入射角 i / °"}, {"k": "g", "label": "折射角 γ / °"}]


def build_optics_lab_reflection() -> dict:
    return {
        "engine": "optics",
        "id": "optics_lab_reflection",
        "title": "探究光的反射定律",
        "subtitle": "改变入射角，比较反射角与入射角",
        "intro": {
            "purpose": "探究反射光线、入射光线与法线的位置关系，以及反射角与入射角的大小关系。",
            "apparatus": ["激光笔", "平面镜", "量角（显示法线与角度）"],
            "discussion": ["如果让光逆着反射光线射向镜面，会怎样？", "入射角增大时，反射角怎样变化？"],
        },
        "library": ["laser", "mirror"],
        "scene": {"parts": [
            _part("p1", "mirror", 600, 540),
            _part("p2", "laser", 330, 300, rot=40),
        ]},
        "steps": [
            {"text": "让激光射到平面镜上，打开「法线与角度」观察反射光", "check": {"type": "hit", "target": "mirror"},
             "ok": "看到了反射光线"},
            {"text": "旋转或移动激光笔改变入射角，记录至少 3 组入射角和反射角", "check": {"type": "records", "min": 3},
             "ok": "数据够了，比较两列数据"},
            {"text": "比较反射角与入射角的大小，归纳反射定律"},
        ],
        "record": {"mode": "angles", "columns": _ANGLE_COLS_R},
        "quiz": [{
            "q": "入射角为 35° 时，反射角是多少？",
            "options": [
                {"t": "35°", "ok": True},
                {"t": "55°", "ok": False, "why": "55° 是入射光线与镜面的夹角，入射角是与法线的夹角。"},
                {"t": "70°", "ok": False, "why": "70° 是入射光线与反射光线的夹角。"},
            ],
            "explain": "反射角等于入射角；入射角、反射角都是光线与法线的夹角。",
        }],
    }


def build_optics_lab_refraction() -> dict:
    return {
        "engine": "optics",
        "id": "optics_lab_refraction",
        "title": "探究光的折射与全反射",
        "subtitle": "光从空气斜射入玻璃，再从玻璃射向空气",
        "intro": {
            "purpose": "观察光从空气斜射入玻璃时的折射现象，比较折射角与入射角；用半圆形玻璃砖观察全反射。",
            "apparatus": ["激光笔", "玻璃砖", "半圆形玻璃砖"],
            "discussion": ["光垂直射入玻璃砖时传播方向改变吗？", "发生全反射需要满足哪两个条件？"],
        },
        "library": ["laser", "block", "semi"],
        "scene": {"parts": [
            _part("p1", "block", 620, 480, n=1.5),
            _part("p2", "laser", 360, 270, rot=40),
        ]},
        "steps": [
            {"text": "让激光斜射入玻璃砖，观察折射光线和微弱的反射光线", "check": {"type": "hit", "target": "block"},
             "ok": "光进入玻璃后传播方向发生了偏折"},
            {"text": "改变入射角，记录至少 3 组入射角和折射角", "check": {"type": "records", "min": 3},
             "ok": "比较一下：折射角比入射角大还是小？"},
            {"text": "从器材库取出半圆形玻璃砖，让光沿半径射向圆心，增大入射角直到折射光消失",
             "check": {"type": "tir"}, "ok": "发生了全反射！"},
        ],
        "record": {"mode": "angles", "columns": _ANGLE_COLS_G},
        "quiz": [{
            "q": "光从空气斜射入玻璃时，折射角与入射角相比？",
            "options": [
                {"t": "折射角小于入射角", "ok": True},
                {"t": "折射角大于入射角", "ok": False, "why": "看记录表：玻璃中的光线更靠近法线。"},
                {"t": "两者相等", "ok": False, "why": "只有垂直入射时方向不变。"},
            ],
            "explain": "光从空气斜射入玻璃、水等介质时，折射光线向法线偏折，折射角小于入射角。",
        }],
    }


def build_optics_lab_convex() -> dict:
    return {
        "engine": "optics",
        "id": "optics_lab_convex",
        "title": "探究凸透镜成像的规律",
        "subtitle": "改变物距，移动光屏找清晰的像",
        "intro": {
            "purpose": "探究凸透镜成像时，像的大小、正倒、虚实与物距的关系。",
            "apparatus": ["光具座", "蜡烛", "凸透镜（f = 10 cm）", "光屏"],
            "discussion": ["照相机、投影仪、放大镜分别利用了哪种成像情况？", "蜡烛燃短后，光屏上的像会向哪里移动？"],
        },
        "library": ["candle", "convex", "screen"],
        "rail": {"y": 400, "x0": 100, "len_cm": 100},
        "showNormal": False,
        "scene": {"parts": [
            _part("p1", "candle", 200, 400),
            _part("p2", "convex", 600, 400, f=10),
            _part("p3", "screen", 950, 400),
        ]},
        "steps": [
            {"text": "物距大于 2 倍焦距（u > 2f），移动光屏得到清晰的像", "check": {"type": "image", "kind": "reduced"},
             "ok": "倒立、缩小的实像——照相机"},
            {"text": "把蜡烛放在 2 倍焦距处（u = 2f），再找清晰的像", "check": {"type": "image", "kind": "equal"},
             "ok": "倒立、等大的实像"},
            {"text": "物距在 f 与 2f 之间，找清晰的像", "check": {"type": "image", "kind": "enlarged"},
             "ok": "倒立、放大的实像——投影仪"},
            {"text": "物距小于焦距（u < f），光屏上还能承接到像吗？", "check": {"type": "image", "kind": "virtual"},
             "ok": "成正立、放大的虚像——放大镜"},
            {"text": "每得到一次清晰的像就记录一次，至少 3 组", "check": {"type": "records", "min": 3}, "ok": "数据记录完成"},
        ],
        "record": {"mode": "lens", "columns": [
            {"k": "u", "label": "物距 u / cm"}, {"k": "v", "label": "像距 v / cm"}, {"k": "kind", "label": "像的性质"},
        ]},
        "quiz": [{
            "q": "用照相机拍照时，被拍物体应在镜头的？",
            "options": [
                {"t": "2 倍焦距以外", "ok": True},
                {"t": "1 倍与 2 倍焦距之间", "ok": False, "why": "这时成放大的实像，是投影仪的原理。"},
                {"t": "1 倍焦距以内", "ok": False, "why": "这时成虚像，是放大镜的原理。"},
            ],
            "explain": "u > 2f 时成倒立、缩小的实像，像距在 f 与 2f 之间，照相机就是这样工作的。",
        }],
    }


def build_optics_lab_diy() -> dict:
    return {
        "engine": "optics",
        "id": "optics_lab_diy",
        "title": "光学实验台（自由搭建）",
        "subtitle": "激光、透镜、平面镜、玻璃砖任意组合",
        "intro": {
            "purpose": "自由组合光学器材，观察光的反射、折射和透镜对光的作用。",
            "apparatus": ["激光笔", "蜡烛", "凸透镜", "凹透镜", "平面镜", "玻璃砖", "半圆形玻璃砖", "光屏"],
            "discussion": ["用两块平面镜能做一个潜望镜吗？", "几束平行光经过凸透镜和凹透镜分别会怎样？"],
        },
        "library": None,
        "scene": {"parts": []},
        "steps": [
            {"text": "用激光照射平面镜，观察反射", "check": {"type": "hit", "target": "mirror"}, "ok": "观察到了反射"},
            {"text": "让激光穿过玻璃砖，观察折射", "check": {"type": "hit", "target": "block"}, "ok": "观察到了折射"},
            {"text": "让激光通过凸透镜，看光线怎样偏折", "check": {"type": "hit", "target": "convex"}, "ok": "凸透镜对光有会聚作用"},
        ],
        "record": {"mode": "angles", "columns": _ANGLE_COLS_R},
    }


REGISTRY = {
    "optics_lab_reflection": build_optics_lab_reflection,
    "optics_lab_refraction": build_optics_lab_refraction,
    "optics_lab_convex": build_optics_lab_convex,
    "optics_lab_diy": build_optics_lab_diy,
    "circuit_lab_diy": build_circuit_lab_diy,
    "circuit_lab_series_parallel": build_circuit_lab_series_parallel,
    "circuit_lab_ohm": build_circuit_lab_ohm,
    "circuit_lab_bulb_power": build_circuit_lab_bulb_power,
    "magnetic_field": build_magnetic_field,
    "electromagnetic_induction": build_emi,
    "circuit_series_parallel": build_circuit,
    "ohm_law": build_ohm,
    "force_composition": build_force,
    "newton_laws": build_newton,
    "state_change": build_state,
    "light_reflection": build_reflection,
    "convex_lens": build_lens,
    "buoyancy": build_buoyancy,
    "projectile_motion": build_projectile,
    "simple_pendulum": build_pendulum,
    "collision_momentum": build_collision,
    "circular_motion": build_circular,
    "incline_friction": build_incline,
    "light_refraction": build_refraction,
    "coulomb_law": build_coulomb,
    "lever_balance": build_lever,
    "pressure": build_pressure,
    "mechanical_energy": build_energy,
    "spring_harmonic": build_spring,
    "pulley_block": build_pulley,
    "ampere_force": build_ampere,
    "parallel_capacitor": build_capacitor,
    "transformer": build_transformer,
    "ideal_gas": build_gas,
    "mechanical_wave": build_wave,
    "doppler_effect": build_doppler,
    "gravitation_orbit": build_gravity,
    "photoelectric": build_photo,
}


def main(argv: list[str]) -> None:
    if not argv or argv[0] == "list":
        print("已注册物理场景:")
        for k, fn in REGISTRY.items():
            print(f"  - {k}\t{fn()['title']}")
        return
    key = argv[0]
    if key not in REGISTRY:
        print(f"未知场景 {key}；可用: {', '.join(REGISTRY)}")
        sys.exit(1)
    out = Path(argv[1]) if len(argv) > 1 else (SKILL_DIR / "output" / f"{key}.html")
    render_html(REGISTRY[key](), out)
    print("written:", out)


if __name__ == "__main__":
    main(sys.argv[1:])
