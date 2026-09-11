#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宏观化学实验台：把实验剧本注入 template/lab.html，产出自包含的 2D 写实器材单页 HTML。

用法：
    python3 scripts/generate.py <实验key> [输出.html]
    python3 scripts/generate.py list
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_DIR / "template" / "lab.html"
LAB2D_JS = SKILL_DIR / "template" / "lab2d.js"
PLACEHOLDER = "__LAB_DATA__"


def with_slots(data: dict) -> dict:
    """给器材/药品打上拖放工位：所需器材 slot=自身 id，所需药品 slot=reagent，干扰项无工位。"""
    req_a = set(data.get("required_apparatus") or [])
    req_r = set(data.get("required_reagents") or [])
    for item in (data.get("inventory") or {}).get("apparatus") or []:
        item["slot"] = item["id"] if item.get("id") in req_a else ""
    for item in (data.get("inventory") or {}).get("reagents") or []:
        item["slot"] = "reagent" if item.get("id") in req_r else ""
    for step in data.get("steps") or []:
        if step.get("need") == "select":
            step["hint"] = (
                "从左上角把器材拖到形状相同的虚线工位；药品拖到「药品」虚线。"
                "放对会卡住，放错会弹回。不需要的仪器没有工位。"
            )
    return data


def _inline_js(src: str) -> str:
    return src.replace("</script>", "<\\/script>").replace("</SCRIPT>", "<\\/SCRIPT>")


def render_html(data: dict, out_path: Path) -> Path:
    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template or "__LAB2D_JS__" not in template:
        raise RuntimeError("模板缺少 __LAB_DATA__ / __LAB2D_JS__")
    lab2d = _inline_js(LAB2D_JS.read_text(encoding="utf-8"))
    payload = json.dumps(with_slots(data), ensure_ascii=False)
    html = template.replace("__LAB2D_JS__", lab2d).replace(PLACEHOLDER, payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def build_prep_oxygen_kmno4() -> dict:
    return {
        "id": "prep_oxygen_kmno4",
        "scene": "oxygen",
        "title": "高锰酸钾制取氧气",
        "subtitle": "固体加热 · 排水法集气 · 防止倒吸",
        "equation": "2KMnO₄ △→ K₂MnO₄ + MnO₂ + O₂↑",
        "goal": "正确组装发生装置，用排水法收集氧气，并用带火星木条检验。",
        "badge": "初中化学 · 制取气体",
        "inventory": {
            "apparatus": [
                {"id": "stand", "name": "铁架台", "icon": "支架"},
                {"id": "tube", "name": "试管", "icon": "试管"},
                {"id": "lamp", "name": "酒精灯", "icon": "灯"},
                {"id": "delivery", "name": "导管", "icon": "管"},
                {"id": "trough", "name": "水槽", "icon": "槽"},
                {"id": "bottle", "name": "集气瓶", "icon": "瓶"},
                {"id": "splint", "name": "带火星木条", "icon": "木条"},
                {"id": "beaker", "name": "烧杯", "icon": "杯"},
            ],
            "reagents": [
                {"id": "kmno4", "name": "高锰酸钾", "color": "#6b21a8"},
                {"id": "hcl", "name": "稀盐酸", "color": "#38bdf8"},
                {"id": "naoh", "name": "氢氧化钠", "color": "#a3e635"},
            ],
        },
        "required_apparatus": ["stand", "tube", "lamp", "delivery", "trough", "bottle", "splint"],
        "required_reagents": ["kmno4"],
        "steps": [
            {
                "id": "pick",
                "need": "select",
                "title": "选取仪器与药品",
                "hint": "点选制氧气需要的仪器：铁架台、试管、酒精灯、导管、水槽、集气瓶、带火星木条；药品选高锰酸钾。",
            },
            {
                "id": "assemble",
                "need": "choice",
                "title": "组装发生装置",
                "hint": "固体加热制气时，试管口方向关系到冷凝水会不会倒流。",
                "choices": [
                    {"id": "tilt_down", "label": "试管口略向下倾斜", "correct": True,
                     "ok": "冷凝水能流向管口，热试管不会因倒流而炸裂。"},
                    {"id": "tilt_up", "label": "试管口向上倾斜", "correct": False,
                     "hazard": "冷凝水倒流到灼热试管底部，试管炸裂。"},
                ],
            },
            {
                "id": "add",
                "need": "action",
                "title": "加入药品",
                "action_label": "把高锰酸钾装入试管",
                "hint": "药品平铺在试管底部，方便均匀受热。",
                "phenomenon": "试管底部铺上一层紫黑色固体。",
                "scene": {"powder": True},
            },
            {
                "id": "heat",
                "need": "action",
                "title": "加热",
                "action_label": "点燃酒精灯加热",
                "hint": "先预热试管，再集中加热药品部位。",
                "phenomenon": "紫黑色固体逐渐变化，导管口有气泡冒出。",
                "scene": {"flame": True, "bubbles": True},
            },
            {
                "id": "collect",
                "need": "action",
                "title": "排水法收集",
                "action_label": "用集气瓶排水收集氧气",
                "hint": "氧气不易溶于水，适合排水法。气泡连续均匀后再开始收集。",
                "phenomenon": "集气瓶中水面下降，收集到无色气体。",
                "scene": {"collected": True},
            },
            {
                "id": "test",
                "need": "choice",
                "title": "检验氧气",
                "hint": "氧气能使带火星的木条复燃。",
                "choices": [
                    {"id": "glowing", "label": "伸入带火星的木条", "correct": True,
                     "ok": "木条复燃，说明收集到的是氧气。", "scene": {"splint_on": True}},
                    {"id": "burning", "label": "伸入燃着的木条看是否熄灭", "correct": False,
                     "hazard": "那是检验二氧化碳的思路。氧气应用带火星木条。"},
                ],
            },
            {
                "id": "safety",
                "need": "choice",
                "title": "结束实验（防倒吸）",
                "hint": "导管还插在水里时熄灯，水会倒吸入热试管。",
                "choices": [
                    {"id": "tube_first", "label": "先把导管移出水面，再熄灭酒精灯", "correct": True,
                     "ok": "装置内气压下降时导管已离开水面，不会倒吸。"},
                    {"id": "lamp_first", "label": "先熄灭酒精灯，再撤导管", "correct": False,
                     "hazard": "水槽中的水倒吸入热试管，试管炸裂。"},
                ],
            },
        ],
        "complete": {
            "title": "实验完成",
            "summary": "你完成了高锰酸钾制氧气：装置正确、排水集气、木条复燃，并落实了「先撤导管再熄灯」。",
        },
    }


def build_neutralization() -> dict:
    return {
        "id": "neutralization",
        "scene": "neutralization",
        "title": "酸碱中和（酚酞指示剂）",
        "subtitle": "滴加 · 搅拌 · 观察褪色终点",
        "equation": "HCl + NaOH → NaCl + H₂O",
        "goal": "向氢氧化钠溶液中滴加稀盐酸，用酚酞指示中和终点。",
        "badge": "初中化学 · 酸碱盐",
        "inventory": {
            "apparatus": [
                {"id": "beaker", "name": "烧杯", "icon": "杯"},
                {"id": "dropper", "name": "胶头滴管", "icon": "滴管"},
                {"id": "rod", "name": "玻璃棒", "icon": "棒"},
                {"id": "goggles", "name": "护目镜", "icon": "镜"},
                {"id": "tube", "name": "试管", "icon": "试管"},
                {"id": "lamp", "name": "酒精灯", "icon": "灯"},
            ],
            "reagents": [
                {"id": "naoh", "name": "氢氧化钠溶液", "color": "#a3e635"},
                {"id": "hcl", "name": "稀盐酸", "color": "#38bdf8"},
                {"id": "phth", "name": "酚酞试液", "color": "#ec4899"},
                {"id": "kmno4", "name": "高锰酸钾", "color": "#6b21a8"},
            ],
        },
        "required_apparatus": ["beaker", "dropper", "rod", "goggles"],
        "required_reagents": ["naoh", "hcl", "phth"],
        "steps": [
            {
                "id": "pick",
                "need": "select",
                "title": "选取仪器与药品",
                "hint": "需要烧杯、胶头滴管、玻璃棒、护目镜；药品为氢氧化钠溶液、稀盐酸和酚酞试液。",
            },
            {
                "id": "goggles",
                "need": "action",
                "title": "安全准备",
                "action_label": "戴上护目镜",
                "hint": "酸、碱都有腐蚀性，操作前先做好护目。",
                "phenomenon": "已佩戴护目镜，可以开始取用溶液。",
                "scene": {"goggles": True},
            },
            {
                "id": "base",
                "need": "action",
                "title": "取氢氧化钠溶液",
                "action_label": "向烧杯中倒入氢氧化钠溶液",
                "hint": "碱液无色，还看不出是否过量，下一步要加指示剂。",
                "phenomenon": "烧杯中是无色氢氧化钠溶液。",
                "scene": {"liquid": "clear"},
            },
            {
                "id": "indicator",
                "need": "choice",
                "title": "滴加指示剂",
                "hint": "酚酞遇碱变红，遇酸无色，适合指示中和终点。",
                "choices": [
                    {"id": "phth", "label": "滴入几滴酚酞试液", "correct": True,
                     "ok": "溶液变为浅红色，说明烧杯中呈碱性。",
                     "scene": {"liquid": "pink"}},
                    {"id": "heat", "label": "用酒精灯加热溶液使反应加快", "correct": False,
                     "hazard": "中和反应在常温下即可进行，加热碱液易溅出伤人。"},
                ],
            },
            {
                "id": "drip",
                "need": "action",
                "title": "边搅边滴加稀盐酸",
                "action_label": "用胶头滴管滴加稀盐酸并搅拌",
                "hint": "边滴边搅拌，观察红色是否变浅。不要俯视去闻酸雾。",
                "phenomenon": "红色逐渐变浅。继续滴加，接近终点。",
                "scene": {"dripping": True, "liquid": "pale"},
            },
            {
                "id": "end",
                "need": "choice",
                "title": "判断终点",
                "hint": "酚酞红色刚好褪去，说明酸碱恰好完全反应。",
                "choices": [
                    {"id": "colorless", "label": "溶液由红刚好变为无色，停止滴加", "correct": True,
                     "ok": "到达中和终点，生成氯化钠和水。",
                     "scene": {"liquid": "clear", "done": True}},
                    {"id": "keep", "label": "继续大量加入盐酸，让反应更彻底", "correct": False,
                     "hazard": "盐酸过量后溶液呈酸性，已经不是恰好中和。"},
                    {"id": "taste", "label": "用玻璃棒蘸取溶液尝尝是否还有碱性", "correct": False,
                     "hazard": "实验室药品严禁口尝，碱和酸都会灼伤黏膜。"},
                ],
            },
            {
                "id": "safety",
                "need": "choice",
                "title": "溅到皮肤怎么办",
                "hint": "酸碱溅到皮肤，立即大量清水冲洗并报告老师。",
                "choices": [
                    {"id": "rinse", "label": "立即用大量清水冲洗，并告知老师", "correct": True,
                     "ok": "正确处理意外，实验可以安全收尾。"},
                    {"id": "wipe", "label": "用抹布擦干再继续做", "correct": False,
                     "hazard": "残留酸碱会继续腐蚀皮肤，不能只擦不冲。"},
                ],
            },
        ],
        "complete": {
            "title": "实验完成",
            "summary": "你完成了酸碱中和：酚酞变红→滴加盐酸褪色，并掌握了护目与冲洗的安全操作。",
        },
    }


def build_prep_hydrogen() -> dict:
    return {
        "id": "prep_hydrogen",
        "scene": "oxygen",
        "scene_init": {"no_lamp": True, "upright": True},
        "title": "锌和稀盐酸制取氢气",
        "subtitle": "固液不加热 · 排水集气 · 验纯后点燃",
        "equation": "Zn + 2HCl → ZnCl₂ + H₂↑",
        "goal": "用锌粒和稀盐酸制氢气，排水法收集，点燃前先验纯。",
        "badge": "初中化学 · 制取气体",
        "inventory": {
            "apparatus": [
                {"id": "tube", "name": "试管", "icon": "试管"},
                {"id": "delivery", "name": "导管", "icon": "管"},
                {"id": "trough", "name": "水槽", "icon": "槽"},
                {"id": "bottle", "name": "集气瓶", "icon": "瓶"},
                {"id": "splint", "name": "燃着的木条", "icon": "木条"},
                {"id": "lamp", "name": "酒精灯", "icon": "灯"},
                {"id": "stand", "name": "铁架台", "icon": "支架"},
            ],
            "reagents": [
                {"id": "zn", "name": "锌粒", "color": "#94a3b8"},
                {"id": "hcl", "name": "稀盐酸", "color": "#38bdf8"},
                {"id": "kmno4", "name": "高锰酸钾", "color": "#6b21a8"},
            ],
        },
        "required_apparatus": ["tube", "delivery", "trough", "bottle", "splint"],
        "required_reagents": ["zn", "hcl"],
        "steps": [
            {
                "id": "pick",
                "need": "select",
                "title": "选取仪器与药品",
                "hint": "固液不加热制氢气：试管、导管、水槽、集气瓶、燃着的木条；药品为锌粒和稀盐酸。不要选酒精灯。",
            },
            {
                "id": "add_zn",
                "need": "action",
                "title": "加入锌粒",
                "action_label": "把锌粒放入试管",
                "hint": "先放固体，再沿管壁倒入液体。",
                "phenomenon": "试管底部有银白色锌粒。",
                "scene": {"zinc": True, "upright": True, "no_lamp": True},
            },
            {
                "id": "add_acid",
                "need": "action",
                "title": "加入稀盐酸",
                "action_label": "沿管壁倒入稀盐酸",
                "hint": "反应立即开始，不要用拇指堵住管口。",
                "phenomenon": "锌粒表面冒出气泡，有无色气体放出。",
                "scene": {"acid": True, "bubbles": True},
            },
            {
                "id": "collect",
                "need": "choice",
                "title": "收集氢气",
                "hint": "氢气难溶于水，密度比空气小。",
                "choices": [
                    {"id": "water", "label": "用排水法收集", "correct": True,
                     "ok": "氢气难溶于水，排水法收集较纯。",
                     "scene": {"collected": True}},
                    {"id": "up", "label": "用向上排空气法收集", "correct": False,
                     "hazard": "氢气比空气轻，向上排空气法收集不到。应排水法或向下排空气法。"},
                ],
            },
            {
                "id": "purity",
                "need": "choice",
                "title": "点燃前验纯",
                "hint": "不纯氢气点燃会爆炸，必须先验纯。",
                "choices": [
                    {"id": "test", "label": "用拇指堵住管口，移近火焰听是否有尖锐爆鸣", "correct": True,
                     "ok": "声音很小说明已较纯，可以在导管口点燃。安静的「噗」声为纯氢。",
                     "scene": {"pop": True}},
                    {"id": "direct", "label": "气体一产生就在发生装置口点燃", "correct": False,
                     "hazard": "装置内是氢空气混合物，直接点燃可能爆炸。"},
                ],
            },
            {
                "id": "ignite",
                "need": "action",
                "title": "导管口点燃",
                "action_label": "在导管口点燃验纯后的氢气",
                "hint": "纯净氢气安静燃烧，火焰呈淡蓝色。",
                "phenomenon": "导管口出现淡蓝色火焰，杯壁上有水雾。",
                "scene": {"pop": False, "jet_flame": True},
            },
            {
                "id": "safety",
                "need": "choice",
                "title": "安全注意",
                "hint": "氢气是可燃气体，实验室要远离明火。",
                "choices": [
                    {"id": "away", "label": "发生装置远离明火，点燃只在验纯后的导管口进行", "correct": True,
                     "ok": "把制取和点燃分开，避免回火。"},
                    {"id": "heat", "label": "用酒精灯加热试管让反应更快", "correct": False,
                     "hazard": "此反应不需要加热；加热可燃气体混合物十分危险。"},
                ],
            },
        ],
        "complete": {
            "title": "实验完成",
            "summary": "你完成了制氢气：锌与稀盐酸反应、排水收集、验纯后在导管口点燃，见到淡蓝色火焰。",
        },
    }


def build_prep_co2() -> dict:
    return {
        "id": "prep_co2",
        "scene": "oxygen",
        "scene_init": {"no_lamp": True, "upright": True, "air_collect": True},
        "title": "大理石和稀盐酸制取二氧化碳",
        "subtitle": "固液不加热 · 向上排空气 · 石灰水检验",
        "equation": "CaCO₃ + 2HCl → CaCl₂ + H₂O + CO₂↑",
        "goal": "用大理石和稀盐酸制二氧化碳，向上排空气法收集，并用澄清石灰水检验。",
        "badge": "初中化学 · 制取气体",
        "inventory": {
            "apparatus": [
                {"id": "tube", "name": "试管 / 锥形瓶", "icon": "瓶"},
                {"id": "delivery", "name": "导管", "icon": "管"},
                {"id": "bottle", "name": "集气瓶", "icon": "瓶"},
                {"id": "lime_beaker", "name": "盛石灰水的烧杯", "icon": "杯"},
                {"id": "splint", "name": "燃着的木条", "icon": "木条"},
                {"id": "trough", "name": "水槽", "icon": "槽"},
                {"id": "lamp", "name": "酒精灯", "icon": "灯"},
            ],
            "reagents": [
                {"id": "caco3", "name": "大理石 / 石灰石", "color": "#e7e5e4"},
                {"id": "hcl", "name": "稀盐酸", "color": "#38bdf8"},
                {"id": "lime", "name": "澄清石灰水", "color": "#e0f2fe"},
                {"id": "h2so4", "name": "稀硫酸", "color": "#facc15"},
            ],
        },
        "required_apparatus": ["tube", "delivery", "bottle", "lime_beaker", "splint"],
        "required_reagents": ["caco3", "hcl", "lime"],
        "steps": [
            {
                "id": "pick",
                "need": "select",
                "title": "选取仪器与药品",
                "hint": "大理石、稀盐酸、导管、集气瓶、澄清石灰水、燃着的木条。不要用水槽（二氧化碳能溶于水）。不要用稀硫酸（与大理石生成微溶硫酸钙覆盖表面）。",
            },
            {
                "id": "add",
                "need": "action",
                "title": "加入药品",
                "action_label": "放入大理石并加入稀盐酸",
                "hint": "块状大理石，便于控制反应。",
                "phenomenon": "固体表面剧烈冒泡，有无色气体放出。",
                "scene": {"marble": True, "acid": True, "bubbles": True, "upright": True, "no_lamp": True, "air_collect": True},
            },
            {
                "id": "collect",
                "need": "choice",
                "title": "收集二氧化碳",
                "hint": "二氧化碳密度比空气大，能溶于水。",
                "choices": [
                    {"id": "up_air", "label": "用向上排空气法（瓶口向上）收集", "correct": True,
                     "ok": "二氧化碳比空气重，瓶口向上可把空气向上排出。",
                     "scene": {"air_collect": True}},
                    {"id": "water", "label": "用排水法收集", "correct": False,
                     "hazard": "二氧化碳能溶于水，排水法收集量少、气体不纯。"},
                ],
            },
            {
                "id": "test",
                "need": "choice",
                "title": "检验二氧化碳",
                "hint": "最常用澄清石灰水变浑浊；燃着的木条会熄灭。",
                "choices": [
                    {"id": "lime", "label": "通入澄清石灰水，观察是否变浑浊", "correct": True,
                     "ok": "石灰水变浑浊，证明是二氧化碳。",
                     "scene": {"lime": True, "lime_milky": True}},
                    {"id": "glow", "label": "伸入带火星的木条看是否复燃", "correct": False,
                     "hazard": "那是检验氧气。二氧化碳应使燃着的木条熄灭，或使石灰水变浑浊。"},
                ],
            },
            {
                "id": "safety",
                "need": "choice",
                "title": "酸的使用",
                "hint": "不能用浓盐酸：挥发的 HCl 会混入气体。",
                "choices": [
                    {"id": "dilute", "label": "使用稀盐酸，不要用浓盐酸", "correct": True,
                     "ok": "稀盐酸反应平稳，气体较纯。"},
                    {"id": "conc", "label": "改用浓盐酸让反应更快", "correct": False,
                     "hazard": "浓盐酸挥发出的氯化氢会混在二氧化碳里，气体不纯，还刺激呼吸道。"},
                ],
            },
        ],
        "complete": {
            "title": "实验完成",
            "summary": "你完成了制二氧化碳：大理石与稀盐酸、向上排空气收集，并用石灰水检验。",
        },
    }


def build_electrolysis_water() -> dict:
    return {
        "id": "electrolysis",
        "scene": "electrolysis",
        "title": "电解水",
        "subtitle": "通电分解 · 正氧负氢 · 体积比 1:2",
        "equation": "2H₂O 通电→ 2H₂↑ + O₂↑",
        "goal": "观察电解水，根据电极和体积比判断氢气、氧气，并检验。",
        "badge": "初中化学 · 分解反应",
        "inventory": {
            "apparatus": [
                {"id": "cell", "name": "电解器 / 水槽", "icon": "槽"},
                {"id": "power", "name": "直流电源", "icon": "电"},
                {"id": "tubes", "name": "两支集气管", "icon": "管"},
                {"id": "splint", "name": "木条（点燃 / 带火星）", "icon": "木条"},
                {"id": "lamp", "name": "酒精灯", "icon": "灯"},
            ],
            "reagents": [
                {"id": "water", "name": "水（可加少量硫酸或氢氧化钠）", "color": "#38bdf8"},
                {"id": "hcl", "name": "浓盐酸", "color": "#22c55e"},
            ],
        },
        "required_apparatus": ["cell", "power", "tubes", "splint"],
        "required_reagents": ["water"],
        "steps": [
            {
                "id": "pick",
                "need": "select",
                "title": "选取仪器与药品",
                "hint": "电解器、直流电源、两支集气管、检验用木条；液体是水。可加少量硫酸或氢氧化钠增强导电，不要加浓盐酸当「电解质」主药品。",
            },
            {
                "id": "power",
                "need": "action",
                "title": "通电",
                "action_label": "接通直流电源",
                "hint": "两极都有气泡，负极气泡更多。",
                "phenomenon": "两极冒出气泡，负极一侧气体体积约为正极的两倍。",
                "scene": {"gases": True, "ratio": True},
            },
            {
                "id": "which",
                "need": "choice",
                "title": "判断气体",
                "hint": "正氧负氢：正极连电源正极，产生氧气；负极产生氢气。",
                "choices": [
                    {"id": "ok", "label": "负极是氢气（体积多），正极是氧气（体积少）", "correct": True,
                     "ok": "体积比约为 2:1，正好对应 2H₂ : O₂。"},
                    {"id": "swap", "label": "正极是氢气，负极是氧气", "correct": False,
                     "hazard": "记反了。口诀：正氧负氢。"},
                ],
            },
            {
                "id": "test",
                "need": "choice",
                "title": "检验两极气体",
                "hint": "氢气能点燃，氧气使带火星木条复燃。",
                "choices": [
                    {"id": "both", "label": "负极气体点燃；正极气体用带火星木条检验", "correct": True,
                     "ok": "负极氢气安静燃烧或轻微爆鸣；正极氧气使木条复燃。"},
                    {"id": "same", "label": "两支管子都伸入带火星木条", "correct": False,
                     "hazard": "氢气不能使带火星木条复燃，应用点燃的方法检验。"},
                ],
            },
            {
                "id": "safety",
                "need": "choice",
                "title": "用电安全",
                "hint": "用低电压直流电，手和装置保持干燥。",
                "choices": [
                    {"id": "dc", "label": "使用低压直流电源，不要用湿手触摸电极", "correct": True,
                     "ok": "电解水是用电实验，先保证绝缘和干燥。"},
                    {"id": "ac", "label": "直接接家庭交流电 220V，反应更快", "correct": False,
                     "hazard": "高压交流电有触电危险，实验室只用低压直流电源。"},
                ],
            },
        ],
        "complete": {
            "title": "实验完成",
            "summary": "你完成了电解水：正氧负氢、体积比约 1:2，并正确检验了两种气体。",
        },
    }


def build_metal_acid() -> dict:
    return {
        "id": "metal_acid",
        "scene": "neutralization",
        "title": "金属与稀盐酸反应",
        "subtitle": "观察气泡 · 比较活动性 · 护目防溅",
        "equation": "Zn + 2HCl → ZnCl₂ + H₂↑",
        "goal": "观察锌（或铁）与稀盐酸反应产生氢气，体会金属活动性，注意护目。",
        "badge": "初中化学 · 金属活动性",
        "inventory": {
            "apparatus": [
                {"id": "beaker", "name": "烧杯 / 试管", "icon": "杯"},
                {"id": "goggles", "name": "护目镜", "icon": "镜"},
                {"id": "rod", "name": "玻璃棒", "icon": "棒"},
                {"id": "lamp", "name": "酒精灯", "icon": "灯"},
            ],
            "reagents": [
                {"id": "zn", "name": "锌粒", "color": "#94a3b8"},
                {"id": "hcl", "name": "稀盐酸", "color": "#38bdf8"},
                {"id": "cu", "name": "铜片", "color": "#d97706"},
            ],
        },
        "required_apparatus": ["beaker", "goggles", "rod"],
        "required_reagents": ["zn", "hcl"],
        "steps": [
            {
                "id": "pick",
                "need": "select",
                "title": "选取仪器与药品",
                "hint": "烧杯（或试管）、护目镜、玻璃棒；锌粒和稀盐酸。铜片可作对比，但本实验主反应是锌。不要选酒精灯。",
            },
            {
                "id": "goggles",
                "need": "action",
                "title": "戴护目镜",
                "action_label": "戴上护目镜",
                "hint": "酸有腐蚀性，气泡可能带出液滴。",
                "phenomenon": "已做好护目，可以取用盐酸。",
                "scene": {"goggles": True},
            },
            {
                "id": "mix",
                "need": "action",
                "title": "加入锌粒和稀盐酸",
                "action_label": "放入锌粒并倒入稀盐酸",
                "hint": "观察是否立即有气泡，手不要堵住容器口。",
                "phenomenon": "锌粒表面迅速冒出气泡，溶液仍接近无色。",
                "scene": {"metal": True, "acid_bubbles": True, "liquid": "clear"},
            },
            {
                "id": "compare",
                "need": "choice",
                "title": "活动性比较",
                "hint": "锌能置换出盐酸中的氢，铜在常温下几乎不与稀盐酸反应。",
                "choices": [
                    {"id": "zn", "label": "锌能反应放出氢气，铜与稀盐酸几乎不反应", "correct": True,
                     "ok": "金属活动性：锌在氢前，铜在氢后。"},
                    {"id": "cu", "label": "铜比锌更活泼，气泡应该更多", "correct": False,
                     "hazard": "铜不能从稀盐酸中置换出氢气。"},
                ],
            },
            {
                "id": "safety",
                "need": "choice",
                "title": "能否密封加热",
                "hint": "有气体放出的反应不能密闭加热。",
                "choices": [
                    {"id": "open", "label": "容器开口，不加热，让氢气自行逸出后再处理残液", "correct": True,
                     "ok": "防止压强过大，也避免氢气遇明火。"},
                    {"id": "seal", "label": "塞紧橡皮塞再用酒精灯加热，让反应更快", "correct": False,
                     "hazard": "密闭加热会使气体压强骤增，容器可能爆裂。"},
                ],
            },
        ],
        "complete": {
            "title": "实验完成",
            "summary": "你观察了锌与稀盐酸放氢，并比较了锌、铜的活动性，同时落实了护目与开口操作。",
        },
    }


def build_filtration() -> dict:
    return {
        "id": "filtration",
        "scene": "filtration",
        "title": "过滤",
        "subtitle": "一贴二低三靠 · 分离不溶固体",
        "equation": "（物理操作，无化学方程式）",
        "goal": "用漏斗和滤纸把不溶固体从液体中分离，得到澄清滤液。",
        "badge": "初中化学 · 基本操作",
        "inventory": {
            "apparatus": [
                {"id": "funnel", "name": "漏斗", "icon": "斗"},
                {"id": "paper", "name": "滤纸", "icon": "纸"},
                {"id": "rod", "name": "玻璃棒", "icon": "棒"},
                {"id": "beaker", "name": "烧杯", "icon": "杯"},
                {"id": "stand", "name": "铁架台", "icon": "支架"},
                {"id": "lamp", "name": "酒精灯", "icon": "灯"},
            ],
            "reagents": [
                {"id": "mix", "name": "泥沙浊液", "color": "#a8a29e"},
                {"id": "hcl", "name": "稀盐酸", "color": "#38bdf8"},
            ],
        },
        "required_apparatus": ["funnel", "paper", "rod", "beaker", "stand"],
        "required_reagents": ["mix"],
        "steps": [
            {
                "id": "pick",
                "need": "select",
                "title": "选取仪器与药品",
                "hint": "漏斗、滤纸、玻璃棒、烧杯、铁架台；样品是浊液。过滤不需要酒精灯，也不要加盐酸。",
            },
            {
                "id": "paper",
                "need": "choice",
                "title": "安放滤纸",
                "hint": "滤纸紧贴漏斗内壁，中间不要留气泡。",
                "choices": [
                    {"id": "wet", "label": "滤纸对折后放入漏斗，用水润湿使它紧贴内壁", "correct": True,
                     "ok": "「一贴」：滤纸紧贴漏斗内壁。",
                     "scene": {"paper": True}},
                    {"id": "hole", "label": "在滤纸上戳一个洞，让液体流得更快", "correct": False,
                     "hazard": "戳洞会使固体漏下去，过滤失败。"},
                ],
            },
            {
                "id": "pour",
                "need": "choice",
                "title": "倾倒液体",
                "hint": "玻璃棒引流，液面低于滤纸边缘。",
                "choices": [
                    {"id": "drain", "label": "用玻璃棒引流，液面低于滤纸边缘", "correct": True,
                     "ok": "「二低三靠」：液面低、烧杯口靠棒、棒靠三层滤纸、漏斗下端靠烧杯壁。",
                     "scene": {"drain": True, "residue": True, "filtrate": True}},
                    {"id": "dump", "label": "把浊液直接倒进漏斗，倒满到漏斗口", "correct": False,
                     "hazard": "液体漫过滤纸边缘，固体会从缝隙流下。"},
                ],
            },
            {
                "id": "result",
                "need": "choice",
                "title": "判断滤液",
                "hint": "滤液应澄清；若仍浑浊，要换滤纸重滤。",
                "choices": [
                    {"id": "clear", "label": "烧杯中得到澄清滤液，残渣留在滤纸上", "correct": True,
                     "ok": "过滤完成：固体和液体分开了。"},
                    {"id": "stir", "label": "用玻璃棒把滤纸捅破，把残渣也冲下去", "correct": False,
                     "hazard": "过滤的目的就是留下不溶固体，不能弄破滤纸。"},
                ],
            },
        ],
        "complete": {
            "title": "实验完成",
            "summary": "你按「一贴二低三靠」完成了过滤，得到澄清滤液，残渣留在滤纸上。",
        },
    }


def build_evaporation() -> dict:
    return {
        "id": "evaporation",
        "scene": "evaporation",
        "title": "蒸发结晶",
        "subtitle": "加热蒸发 · 玻璃棒搅拌 · 余热蒸干",
        "equation": "（物理操作，无化学方程式）",
        "goal": "把滤液加热蒸发，得到固体晶体，并防止液滴飞溅。",
        "badge": "初中化学 · 基本操作",
        "inventory": {
            "apparatus": [
                {"id": "dish", "name": "蒸发皿", "icon": "皿"},
                {"id": "lamp", "name": "酒精灯", "icon": "灯"},
                {"id": "rod", "name": "玻璃棒", "icon": "棒"},
                {"id": "stand", "name": "铁架台 / 三脚架", "icon": "架"},
                {"id": "gauze", "name": "陶土网", "icon": "网"},
                {"id": "funnel", "name": "漏斗", "icon": "斗"},
            ],
            "reagents": [
                {"id": "sol", "name": "食盐溶液 / 滤液", "color": "#38bdf8"},
                {"id": "kmno4", "name": "高锰酸钾固体", "color": "#6b21a8"},
            ],
        },
        "required_apparatus": ["dish", "lamp", "rod", "stand", "gauze"],
        "required_reagents": ["sol"],
        "steps": [
            {
                "id": "pick",
                "need": "select",
                "title": "选取仪器与药品",
                "hint": "蒸发皿、酒精灯、玻璃棒、铁架台（或三脚架）、陶土网；液体是滤液或食盐溶液。不要用漏斗蒸发。",
            },
            {
                "id": "pour",
                "need": "action",
                "title": "倒入溶液",
                "action_label": "把溶液倒入蒸发皿，液面不超过容积的三分之二",
                "hint": "蒸发皿能耐高温，烧杯一般不直接用来蒸干。",
                "phenomenon": "蒸发皿中有一层溶液。",
                "scene": {"stir": True},
            },
            {
                "id": "heat",
                "need": "action",
                "title": "加热并搅拌",
                "action_label": "点燃酒精灯，用玻璃棒不断搅拌",
                "hint": "搅拌是为了防止局部过热，液滴飞溅伤人。",
                "phenomenon": "溶液逐渐减少，有水蒸气逸出。",
                "scene": {"heat": True, "stir": True},
            },
            {
                "id": "stop",
                "need": "choice",
                "title": "何时停止加热",
                "hint": "大量固体析出时改用余热蒸干，避免晶体飞溅或烧焦。",
                "choices": [
                    {"id": "left", "label": "出现较多固体时停止加热，利用余热蒸干", "correct": True,
                     "ok": "余热足够把剩余水分蒸干，晶体不易飞溅。",
                     "scene": {"crystals": True, "heat": False}},
                    {"id": "dry", "label": "一直加热到皿底完全烧干、固体发黄", "correct": False,
                     "hazard": "过热会使晶体飞溅，也可能使固体分解变色。"},
                ],
            },
        ],
        "complete": {
            "title": "实验完成",
            "summary": "你完成了蒸发结晶：加热搅拌、见固体后改用余热蒸干。",
        },
    }


def build_nh4hco3_decomp() -> dict:
    return {
        "id": "nh4hco3_decomp",
        "scene": "oxygen",
        "title": "碳酸氢铵受热分解",
        "subtitle": "固体加热 · 检验氨气与二氧化碳 · 管口向下",
        "equation": "NH₄HCO₃ △→ NH₃↑ + CO₂↑ + H₂O",
        "goal": "加热碳酸氢铵，用湿润红色石蕊试纸和澄清石灰水检验产物。",
        "badge": "初中化学 · 分解反应",
        "inventory": {
            "apparatus": [
                {"id": "stand", "name": "铁架台", "icon": "支架"},
                {"id": "tube", "name": "试管", "icon": "试管"},
                {"id": "lamp", "name": "酒精灯", "icon": "灯"},
                {"id": "paper", "name": "湿润红色石蕊试纸", "icon": "纸"},
                {"id": "lime_beaker", "name": "盛石灰水的烧杯", "icon": "杯"},
                {"id": "trough", "name": "水槽", "icon": "槽"},
            ],
            "reagents": [
                {"id": "nh4", "name": "碳酸氢铵", "color": "#f8fafc"},
                {"id": "lime", "name": "澄清石灰水", "color": "#e0f2fe"},
                {"id": "hcl", "name": "稀盐酸", "color": "#38bdf8"},
            ],
        },
        "required_apparatus": ["stand", "tube", "lamp", "paper", "lime_beaker"],
        "required_reagents": ["nh4", "lime"],
        "steps": [
            {
                "id": "pick",
                "need": "select",
                "title": "选取仪器与药品",
                "hint": "铁架台、试管、酒精灯、湿润红色石蕊试纸、澄清石灰水；药品是碳酸氢铵。不要用水槽收集。",
            },
            {
                "id": "assemble",
                "need": "choice",
                "title": "试管口方向",
                "hint": "固体加热时试管口应略向下，防止冷凝水倒流。",
                "choices": [
                    {"id": "tilt_down", "label": "试管口略向下倾斜", "correct": True,
                     "ok": "生成的水蒸气冷凝后流向管口，热试管不会炸裂。"},
                    {"id": "tilt_up", "label": "试管口对着自己向上倾斜", "correct": False,
                     "hazard": "管口不能对着人；向上倾斜时冷凝水倒流会炸裂试管。"},
                ],
            },
            {
                "id": "add",
                "need": "action",
                "title": "加入药品并加热",
                "action_label": "放入碳酸氢铵，用酒精灯加热",
                "hint": "固体逐渐消失，有刺激性气味气体放出。",
                "phenomenon": "白色固体减少，管口有水雾，能闻到氨的气味。",
                "scene": {"powder": True, "flame": True, "wet_paper": True},
            },
            {
                "id": "test",
                "need": "choice",
                "title": "检验产物",
                "hint": "氨气使湿润红色石蕊试纸变蓝；二氧化碳使石灰水变浑浊。",
                "choices": [
                    {"id": "both", "label": "试纸变蓝说明有氨气，石灰水变浑浊说明有二氧化碳", "correct": True,
                     "ok": "同时还生成水。碳酸氢铵分解成三种物质。",
                     "scene": {"lime": True, "lime_milky": True, "wet_paper": True}},
                    {"id": "o2", "label": "用带火星木条伸入试管，复燃说明有氧气", "correct": False,
                     "hazard": "碳酸氢铵分解不产生氧气，这是制氧气的检验方法。"},
                ],
            },
            {
                "id": "safety",
                "need": "choice",
                "title": "气味与加热",
                "hint": "氨有刺激性，不能凑近去闻；加热后先把导管移开再熄灯（若接了导管）。",
                "choices": [
                    {"id": "fan", "label": "用手轻轻扇闻，试管口不对着人", "correct": True,
                     "ok": "实验室闻气体一律扇闻，不要把鼻子凑到管口。"},
                    {"id": "sniff", "label": "把鼻子凑到试管口深吸一口确认是氨", "correct": False,
                     "hazard": "氨气刺激眼鼻，浓氨还会灼伤黏膜。"},
                ],
            },
        ],
        "complete": {
            "title": "实验完成",
            "summary": "你完成了碳酸氢铵受热分解：管口向下、检验出氨气和二氧化碳，并做到扇闻、不对着人。",
        },
    }


def build_iron_in_oxygen() -> dict:
    return {
        "id": "iron_in_oxygen",
        "scene": "oxygen",
        "scene_init": {"air_collect": True},
        "title": "铁丝在氧气中燃烧",
        "subtitle": "集气瓶底留水 · 预热铁丝 · 火星四射",
        "equation": "3Fe + 2O₂ 点燃→ Fe₃O₄",
        "goal": "观察铁丝在氧气中剧烈燃烧，并保护集气瓶不被溅落熔融物炸裂。",
        "badge": "初中化学 · 氧气的性质",
        "inventory": {
            "apparatus": [
                {"id": "bottle", "name": "盛氧气的集气瓶", "icon": "瓶"},
                {"id": "wire", "name": "绕成螺旋状的铁丝", "icon": "丝"},
                {"id": "lamp", "name": "酒精灯", "icon": "灯"},
                {"id": "cover", "name": "玻璃片", "icon": "片"},
                {"id": "trough", "name": "水槽", "icon": "槽"},
            ],
            "reagents": [
                {"id": "o2", "name": "氧气", "color": "#38bdf8"},
                {"id": "rust", "name": "火柴或一小粒火柴头（引燃）", "color": "#b45309"},
                {"id": "hcl", "name": "稀盐酸", "color": "#22c55e"},
            ],
        },
        "required_apparatus": ["bottle", "wire", "lamp", "cover"],
        "required_reagents": ["o2", "rust"],
        "steps": [
            {
                "id": "pick",
                "need": "select",
                "title": "选取仪器与药品",
                "hint": "盛氧气的集气瓶、螺旋铁丝、酒精灯、玻璃片；用火柴头帮助引燃。不要把水槽当反应容器。",
            },
            {
                "id": "water",
                "need": "choice",
                "title": "保护集气瓶",
                "hint": "熔融物溅到底部会炸裂玻璃，要垫一层水或细沙。",
                "choices": [
                    {"id": "water", "label": "集气瓶底先留少量水（或铺一层细沙）", "correct": True,
                     "ok": "水或细沙吸收热量，瓶底不易炸裂。",
                     "scene": {"air_collect": True, "bottle_water": True}},
                    {"id": "dry", "label": "瓶底保持干燥，燃烧更旺", "correct": False,
                     "hazard": "炽热熔融物打在干燥瓶底，集气瓶会炸裂。"},
                ],
            },
            {
                "id": "heat",
                "need": "action",
                "title": "预热铁丝",
                "action_label": "在酒精灯上烧至铁丝红热，迅速伸入氧气瓶",
                "hint": "铁丝绕成螺旋可增大受热面积；瓶口用玻璃片稍作遮挡。",
                "phenomenon": "铁丝剧烈燃烧，火星四射，生成黑色固体。",
                "scene": {"flame": True, "sparks": True, "air_collect": True, "bottle_water": True},
            },
            {
                "id": "safety",
                "need": "choice",
                "title": "操作注意",
                "hint": "红热铁丝要自上而下缓慢伸入，不要碰到瓶壁。",
                "choices": [
                    {"id": "slow", "label": "自上而下缓慢伸入，避免接触瓶壁和瓶底的水", "correct": True,
                     "ok": "既看清现象，又不炸裂瓶子。"},
                    {"id": "drop", "label": "把烧红的铁丝扔进瓶里立刻盖紧", "correct": False,
                     "hazard": "铁丝会砸裂瓶底，盖紧还会使瓶内压强骤变。"},
                ],
            },
        ],
        "complete": {
            "title": "实验完成",
            "summary": "你完成了铁丝在氧气中燃烧：瓶底留水、预热后伸入，看到火星四射。",
        },
    }


def build_solution_prep() -> dict:
    return {
        "id": "solution_prep",
        "scene": "neutralization",
        "title": "配制一定溶质质量分数的溶液",
        "subtitle": "称量 · 量水 · 烧杯溶解 · 玻璃棒搅拌",
        "equation": "（配制操作，无化学方程式）",
        "goal": "按计算称取固体、量取水，在烧杯中溶解，得到指定质量分数的溶液。",
        "badge": "初中化学 · 溶液",
        "inventory": {
            "apparatus": [
                {"id": "balance", "name": "托盘天平", "icon": "秤"},
                {"id": "beaker", "name": "烧杯", "icon": "杯"},
                {"id": "cylinder", "name": "量筒", "icon": "筒"},
                {"id": "rod", "name": "玻璃棒", "icon": "棒"},
                {"id": "paper", "name": "称量纸", "icon": "纸"},
                {"id": "lamp", "name": "酒精灯", "icon": "灯"},
            ],
            "reagents": [
                {"id": "nacl", "name": "氯化钠固体", "color": "#f8fafc"},
                {"id": "water", "name": "蒸馏水", "color": "#38bdf8"},
            ],
        },
        "required_apparatus": ["balance", "beaker", "cylinder", "rod", "paper"],
        "required_reagents": ["nacl", "water"],
        "steps": [
            {
                "id": "pick",
                "need": "select",
                "title": "选取仪器与药品",
                "hint": "托盘天平、烧杯、量筒、玻璃棒、称量纸；氯化钠和水。溶解不需要酒精灯。",
            },
            {
                "id": "weigh",
                "need": "choice",
                "title": "称量固体",
                "hint": "药品不能直接放在托盘上。",
                "choices": [
                    {"id": "paper", "label": "在称量纸上称取计算量的氯化钠", "correct": True,
                     "ok": "固体放称量纸（或小烧杯）上，先放砝码再添药品，直至平衡。"},
                    {"id": "pan", "label": "把氯化钠直接倒在托盘上称", "correct": False,
                     "hazard": "药品会腐蚀托盘，称量也不准确。"},
                ],
            },
            {
                "id": "water",
                "need": "choice",
                "title": "量取水并溶解",
                "hint": "量筒只能量体积，不能当溶解容器。",
                "choices": [
                    {"id": "beaker", "label": "用量筒量水，倒入烧杯，用玻璃棒搅拌溶解", "correct": True,
                     "ok": "溶解在烧杯中进行，玻璃棒搅拌加快溶解。",
                     "scene": {"liquid": "clear"}},
                    {"id": "cyl", "label": "把氯化钠倒进量筒，直接在量筒里加水振荡", "correct": False,
                     "hazard": "量筒不能用于溶解或稀释，刻度会不准，也容易洒出。"},
                ],
            },
            {
                "id": "read",
                "need": "choice",
                "title": "读数与转移",
                "hint": "量筒读数时视线与凹液面最低处相平。",
                "choices": [
                    {"id": "eye", "label": "量水时平视凹液面最低处，再转移到烧杯", "correct": True,
                     "ok": "俯视读数偏小、仰视偏大，都会使溶质质量分数不准。"},
                    {"id": "heat", "label": "用酒精灯加热量筒，让固体溶得更快", "correct": False,
                     "hazard": "量筒不能加热。需要加速溶解应在烧杯中搅拌，必要时水浴。"},
                ],
            },
        ],
        "complete": {
            "title": "实验完成",
            "summary": "你完成了溶液配制：称量、量水、烧杯中溶解，没有在量筒里溶固体。",
        },
    }


REGISTRY = {
    "prep_oxygen_kmno4": build_prep_oxygen_kmno4,
    "prep_hydrogen": build_prep_hydrogen,
    "prep_co2": build_prep_co2,
    "electrolysis": build_electrolysis_water,
    "neutralization": build_neutralization,
    "metal_acid": build_metal_acid,
    "filtration": build_filtration,
    "evaporation": build_evaporation,
    "nh4hco3_decomp": build_nh4hco3_decomp,
    "iron_in_oxygen": build_iron_in_oxygen,
    "solution_prep": build_solution_prep,
}

TITLES = {k: fn()["title"] for k, fn in REGISTRY.items()}


def main(argv: list[str]) -> None:
    if not argv or argv[0] == "list":
        print("已注册实验:")
        for k in REGISTRY:
            print(f"  - {k}  {TITLES.get(k, '')}")
        return
    key = argv[0]
    if key not in REGISTRY:
        print(f"未知实验 {key}；可用: {', '.join(REGISTRY)}")
        sys.exit(1)
    out = Path(argv[1]) if len(argv) > 1 else (SKILL_DIR / "output" / f"{key}.html")
    render_html(REGISTRY[key](), out)
    print("written:", out)


if __name__ == "__main__":
    main(sys.argv[1:])
