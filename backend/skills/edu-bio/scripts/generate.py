#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生物知识点探究页：把场景数据注入 template/explore.html。

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


def _inline_js(src: str) -> str:
    return src.replace("</script>", "<\\/script>").replace("</SCRIPT>", "<\\/SCRIPT>")


def render_html(data: dict, out_path: Path) -> Path:
    template = TEMPLATE.read_text(encoding="utf-8")
    if "__BIO_DATA__" not in template or "__BIO_JS__" not in template:
        raise RuntimeError("模板缺少 __BIO_DATA__ / __BIO_JS__")
    payload = json.dumps(data, ensure_ascii=False)
    html = template.replace("__BIO_JS__", _inline_js(JS.read_text(encoding="utf-8")))
    html = html.replace("__BIO_DATA__", payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _svg(inner: str, vb="0 0 720 520") -> str:
    return (
        f'<svg viewBox="{vb}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="生物示意图">'
        f"<rect width='100%' height='100%' fill='transparent'/>{inner}</svg>"
    )


def build_animal_cell() -> dict:
    svg = _svg("""
      <g data-part="cytoplasm">
        <ellipse cx="360" cy="265" rx="250" ry="188" fill="#fde4e4"/>
      </g>
      <g data-part="membrane" data-breathe>
        <ellipse cx="360" cy="265" rx="258" ry="196" fill="none" stroke="#c2416b" stroke-width="10"/>
        <text x="360" y="42" text-anchor="middle" font-size="13" fill="#9f1239">细胞膜</text>
      </g>
      <g data-part="er">
        <path d="M430 160 C500 150 520 190 500 220 C480 250 510 270 470 285" fill="none" stroke="#fb923c" stroke-width="8"/>
        <path d="M445 175 C505 168 518 200 500 225" fill="none" stroke="#fdba74" stroke-width="4"/>
        <text x="530" y="175" font-size="12" fill="#c2410c">内质网</text>
      </g>
      <g data-part="ribosome">
        <circle cx="455" cy="188" r="5" fill="#b45309"/>
        <circle cx="478" cy="205" r="5" fill="#b45309"/>
        <circle cx="250" cy="210" r="5" fill="#b45309"/>
        <circle cx="270" cy="320" r="5" fill="#b45309"/>
        <circle cx="310" cy="150" r="5" fill="#b45309"/>
        <text x="220" y="200" font-size="12" fill="#92400e">核糖体</text>
      </g>
      <g data-part="golgi">
        <ellipse cx="230" cy="300" rx="38" ry="8" fill="#a78bfa"/>
        <ellipse cx="232" cy="312" rx="34" ry="7" fill="#8b5cf6"/>
        <ellipse cx="234" cy="323" rx="30" ry="6" fill="#7c3aed"/>
        <text x="155" y="345" font-size="12" fill="#5b21b6">高尔基体</text>
      </g>
      <g data-part="mito" data-pulse>
        <ellipse cx="250" cy="190" rx="34" ry="16" fill="#fb7185" stroke="#be123c" stroke-width="2"/>
        <path d="M230 190 C240 180 250 200 260 186 C268 196 275 184 280 190" fill="none" stroke="#9f1239" stroke-width="2"/>
        <ellipse cx="470" cy="330" rx="32" ry="15" fill="#fb7185" stroke="#be123c" stroke-width="2"/>
        <path d="M452 330 C462 320 470 338 480 326 C488 336 494 324 498 330" fill="none" stroke="#9f1239" stroke-width="2"/>
        <text x="200" y="168" font-size="12" fill="#9f1239">线粒体</text>
      </g>
      <g data-part="lysosome">
        <circle cx="300" cy="350" r="16" fill="#facc15" stroke="#ca8a04" stroke-width="2"/>
        <circle cx="295" cy="347" r="3" fill="#854d0e"/>
        <circle cx="306" cy="354" r="2.5" fill="#854d0e"/>
        <text x="318" y="372" font-size="12" fill="#854d0e">溶酶体</text>
      </g>
      <g data-part="centrosome" data-spin>
        <rect x="320" y="120" width="10" height="22" rx="3" fill="#38bdf8" transform="rotate(-18 325 131)"/>
        <rect x="332" y="124" width="10" height="22" rx="3" fill="#0ea5e9" transform="rotate(12 337 135)"/>
        <text x="348" y="118" font-size="12" fill="#0369a1">中心体</text>
      </g>
      <g data-part="nucleus">
        <circle cx="390" cy="250" r="62" fill="#e0f2fe" stroke="#0369a1" stroke-width="5"/>
        <text x="390" y="318" text-anchor="middle" font-size="13" fill="#075985">细胞核</text>
      </g>
      <g data-part="nucleolus">
        <circle cx="400" cy="246" r="16" fill="#1d4ed8"/>
        <text x="418" y="232" font-size="12" fill="#1e3a8a">核仁</text>
      </g>
    """)
    return {
        "id": "animal_cell",
        "title": "动物细胞结构",
        "subtitle": "点击细胞膜、细胞核和细胞器，对照功能",
        "badge": "初中生物 · 细胞",
        "hint": "细胞膜在呼吸，线粒体在脉动。先点外层细胞膜，再点细胞核。",
        "goal": "能指认动物细胞主要结构，并说出细胞核、线粒体的功能。",
        "intro": "动物细胞像一个柔软的“袋子”：外层是细胞膜，里面是细胞质，中央有细胞核。没有细胞壁，也没有叶绿体。",
        "svg": svg,
        "parts": [
            {"id": "membrane", "name": "细胞膜", "hint": "控制物质进出",
             "detail": "磷脂双分子层构成的薄膜，把细胞与外界分开，还能选择性地让物质进出。",
             "mistake": "不要把细胞膜当成细胞壁。动物细胞没有细胞壁。"},
            {"id": "cytoplasm", "name": "细胞质", "hint": "细胞器生活的场所",
             "detail": "细胞膜以内、细胞核以外的部分。细胞器悬浮其中，许多化学反应在这里进行。"},
            {"id": "nucleus", "name": "细胞核", "hint": "遗传信息中心",
             "detail": "含有 DNA（染色质），控制细胞的代谢和遗传。没有细胞核的细胞（如哺乳动物成熟红细胞）不能分裂。",
             "mistake": "细胞核不是“脑子”，而是储存和运用遗传信息的场所。"},
            {"id": "nucleolus", "name": "核仁", "hint": "装配核糖体",
             "detail": "细胞核里颜色更深的小球，与核糖体 RNA 的合成有关。"},
            {"id": "mito", "name": "线粒体", "hint": "能量工厂",
             "detail": "进行有氧呼吸的主要场所，把有机物中的化学能转化成 ATP。内膜向内折叠成嵴，增大反应面积。",
             "mistake": "线粒体不是“只在动物细胞里”——植物细胞也有线粒体。"},
            {"id": "ribosome", "name": "核糖体", "hint": "合成蛋白质",
             "detail": "有的游离在细胞质，有的附着在内质网上。把氨基酸连成肽链。"},
            {"id": "er", "name": "内质网", "hint": "加工与运输管道",
             "detail": " rough 内质网（附着核糖体）参与蛋白质加工；滑面内质网与脂质合成等有关。"},
            {"id": "golgi", "name": "高尔基体", "hint": "包装与发送",
             "detail": "对来自内质网的蛋白质进行分类、包装，再运出细胞或送到溶酶体。植物细胞里还与细胞壁形成有关。"},
            {"id": "lysosome", "name": "溶酶体", "hint": "消化与回收",
             "detail": "含水解酶，能分解衰老的细胞器和侵入的病原体。"},
            {"id": "centrosome", "name": "中心体", "hint": "与纺锤体有关",
             "detail": "由两个互相垂直的中心粒组成，动物细胞有丝分裂时发出星射线，形成纺锤体。高等植物一般没有中心体。"},
        ],
        "quiz": {
            "q": "动物细胞有、而植物细胞通常没有的结构是？",
            "options": [
                {"t": "中心体", "ok": True},
                {"t": "线粒体", "ok": False, "why": "植物细胞也有线粒体。"},
                {"t": "细胞壁", "ok": False, "why": "细胞壁是植物细胞才有的。"},
                {"t": "叶绿体", "ok": False, "why": "叶绿体是植物绿色部分才有的。"},
            ],
            "ok": "对，高等动物细胞有中心体，高等植物细胞一般没有。",
            "explain": "对比记忆：植物特有细胞壁、叶绿体、大液泡；动物常见中心体。线粒体两边都有。",
        },
    }


def build_plant_cell() -> dict:
    svg = _svg("""
      <g data-part="wall">
        <rect x="88" y="58" width="544" height="404" rx="18" fill="#d9f99d" stroke="#3f6212" stroke-width="16"/>
        <text x="360" y="42" text-anchor="middle" font-size="13" fill="#3f6212">细胞壁</text>
      </g>
      <g data-part="membrane">
        <rect x="112" y="80" width="496" height="360" rx="12" fill="#ecfccb" stroke="#65a30d" stroke-width="5"/>
      </g>
      <g data-part="vacuole" data-breathe>
        <ellipse cx="390" cy="270" rx="175" ry="130" fill="#bae6fd" stroke="#0284c7" stroke-width="3" opacity=".92"/>
        <text x="390" y="275" text-anchor="middle" font-size="16" fill="#075985">液泡</text>
      </g>
      <g data-part="chloro" data-pulse>
        <ellipse cx="175" cy="160" rx="42" ry="22" fill="#22c55e" stroke="#166534" stroke-width="2"/>
        <ellipse cx="175" cy="160" rx="28" ry="8" fill="#86efac"/>
        <ellipse cx="190" cy="360" rx="40" ry="20" fill="#16a34a" stroke="#166534" stroke-width="2"/>
        <ellipse cx="520" cy="150" rx="38" ry="20" fill="#22c55e" stroke="#166534" stroke-width="2"/>
        <text x="130" y="132" font-size="12" fill="#14532d">叶绿体</text>
      </g>
      <g data-part="mito">
        <ellipse cx="165" cy="250" rx="28" ry="13" fill="#fb7185" stroke="#be123c" stroke-width="2"/>
        <path d="M150 250 C158 242 165 258 174 248" fill="none" stroke="#9f1239" stroke-width="2"/>
        <text x="118" y="278" font-size="12" fill="#9f1239">线粒体</text>
      </g>
      <g data-part="nucleus">
        <circle cx="210" cy="310" r="48" fill="#e0f2fe" stroke="#0369a1" stroke-width="4"/>
        <circle cx="218" cy="308" r="12" fill="#1d4ed8"/>
        <text x="210" y="372" text-anchor="middle" font-size="12" fill="#075985">细胞核</text>
      </g>
      <g data-part="cytoplasm">
        <text x="300" y="150" font-size="12" fill="#3f6212">细胞质（贴壁的一薄层）</text>
      </g>
    """)
    return {
        "id": "plant_cell",
        "title": "植物细胞结构",
        "subtitle": "细胞壁、叶绿体、大液泡是辨认植物细胞的关键",
        "badge": "初中生物 · 细胞",
        "hint": "外层最厚的是细胞壁。中央蓝色大囊是液泡。绿色椭圆是叶绿体。",
        "goal": "能区分动植物细胞，并说明细胞壁、叶绿体、液泡的功能。",
        "intro": "成熟植物细胞中央常有一个大液泡，把细胞核挤到边上。叶肉细胞还有叶绿体，能进行光合作用。",
        "svg": svg,
        "parts": [
            {"id": "wall", "name": "细胞壁", "hint": "支持与保护",
             "detail": "主要成分是纤维素，全透性，给植物细胞提供硬度和形状。不是选择透过性膜。",
             "mistake": "细胞壁不能控制物质进出；控制进出的是里面那层细胞膜。"},
            {"id": "membrane", "name": "细胞膜", "hint": "紧贴细胞壁内侧",
             "detail": "紧贴细胞壁，具有选择透过性。质壁分离时，细胞膜带着细胞质和液泡一起收缩。"},
            {"id": "cytoplasm", "name": "细胞质", "hint": "往往只剩贴壁薄层",
             "detail": "被大液泡挤成一薄层，紧贴细胞膜。胞质环流可运输物质。"},
            {"id": "vacuole", "name": "液泡", "hint": "储存与维持胀压",
             "detail": "内有细胞液（糖、无机盐、色素等）。成熟植物细胞的大液泡使细胞保持膨胀。花青素在液泡里，不在叶绿体。",
             "mistake": "液泡不是“空的”，里面是细胞液。"},
            {"id": "chloro", "name": "叶绿体", "hint": "光合作用的场所",
             "detail": "含叶绿素，把光能转变成化学能，合成有机物并释放氧气。根尖细胞没有叶绿体。",
             "mistake": "不是所有植物细胞都有叶绿体；绿色部分才有。"},
            {"id": "nucleus", "name": "细胞核", "hint": "常被挤到一侧",
             "detail": "功能与动物细胞相同，含遗传物质。大液泡会把它挤到细胞边缘。"},
            {"id": "mito", "name": "线粒体", "hint": "植物也要呼吸",
             "detail": "植物细胞同样有线粒体，进行有氧呼吸。白天叶肉细胞光合作用和呼吸作用同时进行。"},
        ],
        "quiz": {
            "q": "把植物细胞放在清水里会膨胀但一般不会涨破，主要因为有？",
            "options": [
                {"t": "细胞壁", "ok": True},
                {"t": "叶绿体", "ok": False, "why": "叶绿体负责光合作用，不提供机械强度。"},
                {"t": "液泡膜", "ok": False, "why": "液泡维持胀压，但限制膨胀的是坚韧的细胞壁。"},
                {"t": "细胞核", "ok": False, "why": "细胞核不管形状支撑。"},
            ],
            "ok": "细胞壁像硬壳，限制细胞无限膨胀。",
            "explain": "动物细胞没有细胞壁，吸水过多可能涨破。",
        },
    }


def build_mitosis() -> dict:
    svg = _svg("""
      <g data-phase="interphase" class="phase">
        <ellipse cx="360" cy="260" rx="150" ry="120" fill="#fef3c7" stroke="#b45309" stroke-width="6"/>
        <circle cx="360" cy="255" r="48" fill="#e0f2fe" stroke="#0369a1" stroke-width="3"/>
        <path d="M340 240 C350 230 360 250 370 235 C380 250 390 230 400 248" fill="none" stroke="#1d4ed8" stroke-width="3"/>
        <text x="360" y="420" text-anchor="middle" font-size="16" fill="#92400e">间期 · 复制 DNA</text>
      </g>
      <g data-phase="prophase" class="phase is-off">
        <ellipse cx="360" cy="260" rx="150" ry="120" fill="#ffedd5" stroke="#c2410c" stroke-width="6"/>
        <g stroke="#7c3aed" stroke-width="6" fill="none">
          <path d="M300 210 C320 190 340 230 330 250"/>
          <path d="M390 200 C410 180 430 220 410 250"/>
          <path d="M310 290 C330 310 350 270 340 250"/>
          <path d="M400 300 C420 320 430 270 410 260"/>
        </g>
        <line x1="220" y1="260" x2="500" y2="260" stroke="#94a3b8" stroke-dasharray="6 6"/>
        <text x="360" y="420" text-anchor="middle" font-size="16" fill="#9a3412">前期 · 核膜解体，染色体出现</text>
      </g>
      <g data-phase="metaphase" class="phase is-off">
        <ellipse cx="360" cy="260" rx="150" ry="120" fill="#dbeafe" stroke="#1d4ed8" stroke-width="6"/>
        <line x1="210" y1="260" x2="510" y2="260" stroke="#64748b" stroke-width="2" stroke-dasharray="8 6"/>
        <g fill="#7c3aed">
          <rect x="300" y="236" width="18" height="48" rx="4"/>
          <rect x="328" y="236" width="18" height="48" rx="4"/>
          <rect x="374" y="236" width="18" height="48" rx="4"/>
          <rect x="402" y="236" width="18" height="48" rx="4"/>
        </g>
        <line x1="230" y1="180" x2="309" y2="250" stroke="#94a3b8"/>
        <line x1="490" y1="180" x2="411" y2="250" stroke="#94a3b8"/>
        <line x1="230" y1="340" x2="309" y2="270" stroke="#94a3b8"/>
        <line x1="490" y1="340" x2="411" y2="270" stroke="#94a3b8"/>
        <text x="360" y="420" text-anchor="middle" font-size="16" fill="#1e3a8a">中期 · 着丝粒排在赤道板</text>
      </g>
      <g data-phase="anaphase" class="phase is-off">
        <ellipse cx="360" cy="260" rx="150" ry="120" fill="#dcfce7" stroke="#15803d" stroke-width="6"/>
        <g fill="#7c3aed">
          <rect x="250" y="220" width="14" height="36" rx="3"/>
          <rect x="275" y="255" width="14" height="36" rx="3"/>
          <rect x="455" y="220" width="14" height="36" rx="3"/>
          <rect x="430" y="255" width="14" height="36" rx="3"/>
        </g>
        <line x1="220" y1="260" x2="264" y2="238" stroke="#64748b"/>
        <line x1="500" y1="260" x2="455" y2="238" stroke="#64748b"/>
        <text x="360" y="420" text-anchor="middle" font-size="16" fill="#14532d">后期 · 姐妹染色单体分开</text>
      </g>
      <g data-phase="telophase" class="phase is-off">
        <ellipse cx="360" cy="260" rx="160" ry="120" fill="#fce7f3" stroke="#be185d" stroke-width="6"/>
        <ellipse cx="300" cy="260" rx="70" ry="80" fill="#fbcfe8" stroke="#9d174d" stroke-width="4"/>
        <ellipse cx="430" cy="260" rx="70" ry="80" fill="#fbcfe8" stroke="#9d174d" stroke-width="4"/>
        <circle cx="300" cy="255" r="28" fill="#e0f2fe" stroke="#0369a1" stroke-width="2"/>
        <circle cx="430" cy="255" r="28" fill="#e0f2fe" stroke="#0369a1" stroke-width="2"/>
        <text x="360" y="420" text-anchor="middle" font-size="16" fill="#9d174d">末期 · 两个子核形成</text>
      </g>
    """)
    return {
        "id": "mitosis",
        "title": "有丝分裂",
        "subtitle": "按阶段播放：间期 → 前 → 中 → 后 → 末",
        "badge": "高中生物 · 细胞增殖",
        "mode": "phases",
        "period": 10000,
        "hint": "仿真自动循环：间期 → 前 → 中 → 后 → 末。中期染色体排在中央。",
        "goal": "能按顺序说出有丝分裂各时期的标志性变化。",
        "svg": svg,
        "phases": [
            {"id": "interphase", "name": "间期",
             "hint": "看起来“没什么”，其实在复制 DNA 和中心体。",
             "detail": "分裂间期占细胞周期的大部分。完成 DNA 复制和有关蛋白质合成，细胞适度生长。染色质仍是细丝，还看不到染色体。"},
            {"id": "prophase", "name": "前期",
             "hint": "核膜核仁消失，染色体出现，纺锤体形成。",
             "detail": "染色质螺旋化成为染色体（每条含两条姐妹染色单体）。核膜、核仁逐渐解体。动物细胞中心体发出星射线形成纺锤体。"},
            {"id": "metaphase", "name": "中期",
             "hint": "着丝粒排列在赤道板上，形态最清晰，适合计数。",
             "detail": "每条染色体的着丝粒两侧都有纺锤丝牵引，整齐排在细胞中央的赤道板。这是观察染色体形态和数目的最佳时期。"},
            {"id": "anaphase", "name": "后期",
             "hint": "着丝粒分裂，姐妹染色单体成为两条子染色体，被拉向两极。",
             "detail": "染色体数目暂时加倍。纺锤丝缩短，两套染色体分别移向细胞两极。"},
            {"id": "telophase", "name": "末期",
             "hint": "核膜核仁重现，细胞质分裂，形成两个子细胞。",
             "detail": "染色体解旋为染色质，核膜核仁重新出现。动物细胞中部向内凹陷缢裂；植物细胞在赤道板位置形成细胞板，扩展为新细胞壁。"},
        ],
        "quiz": {
            "q": "观察染色体形态和数目，最好选有丝分裂的哪一时期？",
            "options": [
                {"t": "中期", "ok": True},
                {"t": "间期", "ok": False, "why": "间期是染色质，看不到染色体。"},
                {"t": "后期", "ok": False, "why": "后期染色体正在移向两极，数目看起来加倍，不适合计数。"},
                {"t": "末期", "ok": False, "why": "末期染色体已经解旋。"},
            ],
            "ok": "中期着丝粒排在赤道板，染色体形态最固定、最清晰。",
            "explain": "口诀：前隐中齐后分末重建。",
        },
    }


def build_digestive() -> dict:
    svg = _svg("""
      <ellipse cx="360" cy="70" rx="42" ry="48" fill="#fed7aa" stroke="#c2410c" stroke-width="3"/>
      <g data-part="mouth">
        <ellipse cx="360" cy="78" rx="22" ry="10" fill="#fb7185"/>
        <text x="410" y="60" font-size="13" fill="#9a3412">口腔</text>
      </g>
      <g data-part="esophagus">
        <rect x="350" y="118" width="20" height="70" rx="8" fill="#fdba74" stroke="#c2410c"/>
        <text x="378" y="155" font-size="13" fill="#9a3412">食道</text>
      </g>
      <g data-flow fill="none">
        <path d="M360 78 L360 155 C350 190 300 210 320 230 C300 275 250 300 330 330 C380 320 360 380 310 390"
              stroke="#fb923c" stroke-width="3" opacity=".55"/>
      </g>
      <circle data-sim="bolus" r="9" fill="#ea580c" cx="0" cy="0" opacity=".9"/>
      <g data-part="stomach">
        <ellipse cx="320" cy="230" rx="55" ry="40" fill="#fb923c" stroke="#c2410c" stroke-width="3"/>
        <text x="250" y="225" font-size="13" fill="#9a3412">胃</text>
      </g>
      <g data-part="liver">
        <path d="M250 175 C210 175 190 210 230 230 C280 215 300 180 250 175Z" fill="#b45309"/>
        <text x="175" y="168" font-size="13" fill="#7c2d12">肝脏</text>
      </g>
      <g data-part="pancreas">
        <ellipse cx="390" cy="250" rx="48" ry="14" fill="#fde68a" stroke="#ca8a04"/>
        <text x="445" y="245" font-size="13" fill="#854d0e">胰腺</text>
      </g>
      <g data-part="small" data-flow>
        <path d="M300 275 C250 300 280 340 330 330 C380 320 360 380 310 390 C270 400 250 360 290 350 C340 335 400 370 380 410"
              fill="none" stroke="#f97316" stroke-width="16" stroke-linecap="round"/>
        <text x="430" y="360" font-size="13" fill="#c2410c">小肠</text>
      </g>
      <g data-part="large" data-flow>
        <path d="M250 410 C240 450 280 470 360 468 C460 465 490 430 480 390 C470 360 500 340 510 300"
              fill="none" stroke="#d97706" stroke-width="22" stroke-linecap="round"/>
        <text x="530" y="330" font-size="13" fill="#92400e">大肠</text>
      </g>
    """)
    return {
        "id": "digestive_system",
        "title": "人体消化系统",
        "subtitle": "食物走过的路：口腔 → 食道 → 胃 → 小肠 → 大肠",
        "badge": "初中生物 · 人体",
        "period": 7000,
        "tracks": [
            {"id": "bolus", "path": "M360 78 L360 155 C350 190 300 210 320 230 C300 275 250 300 330 330 C380 320 360 380 310 390"},
        ],
        "hint": "橙色食团沿消化道移动。营养吸收的主要场所是小肠，不是胃。",
        "intro": "消化系统包括消化道和消化腺。消化道是通道，消化腺分泌消化液，把大分子水解成可吸收的小分子。",
        "svg": svg,
        "parts": [
            {"id": "mouth", "name": "口腔", "hint": "物理消化 + 淀粉初步消化",
             "detail": "牙齿切断磨碎，舌搅拌。唾液淀粉酶把部分淀粉分解成麦芽糖。"},
            {"id": "esophagus", "name": "食道", "hint": "只负责运送",
             "detail": "靠蠕动把食团送入胃，几乎不消化、不吸收。"},
            {"id": "stomach", "name": "胃", "hint": "暂存 + 初步消化蛋白质",
             "detail": "胃液含胃蛋白酶和盐酸。蛋白质在此开始消化。吸收很少（少量水、酒精）。",
             "mistake": "胃不是吸收营养的主要场所。"},
            {"id": "liver", "name": "肝脏", "hint": "分泌胆汁，不含消化酶",
             "detail": "胆汁乳化脂肪，增大脂肪与酶的接触面积。肝脏还储存糖原、解毒。",
             "mistake": "胆汁不含消化酶，但能促进脂肪消化。"},
            {"id": "pancreas", "name": "胰腺", "hint": "胰液能消化三类有机物",
             "detail": "胰液经导管进入十二指肠，含胰淀粉酶、胰蛋白酶、胰脂肪酶。"},
            {"id": "small", "name": "小肠", "hint": "消化和吸收的主要场所",
             "detail": "最长，内表面有皱襞和绒毛。淀粉、蛋白质、脂肪在此彻底消化，葡萄糖、氨基酸、脂肪酸等在此吸收。",
             "mistake": "不要说“胃吸收大部分营养”。"},
            {"id": "large", "name": "大肠", "hint": "吸收水和无机盐，形成粪便",
             "detail": "几乎不再消化食物残渣。大肠杆菌能合成维生素 B、K。"},
        ],
        "quiz": {
            "q": "消化和吸收的主要场所是？",
            "options": [
                {"t": "小肠", "ok": True},
                {"t": "胃", "ok": False, "why": "胃主要初步消化蛋白质，吸收很少。"},
                {"t": "大肠", "ok": False, "why": "大肠主要吸收水和无机盐。"},
                {"t": "肝脏", "ok": False, "why": "肝脏是消化腺，食物并不从肝脏穿过。"},
            ],
            "ok": "小肠又长、绒毛又多，是消化吸收的主战场。",
            "explain": "消化道口诀：口食胃、小大；消化腺：唾液腺、肝脏、胰腺、肠腺。",
        },
    }


def build_circulatory() -> dict:
    svg = _svg("""
      <g data-part="systemic" data-flow>
        <path d="M360 70 C210 90 160 200 180 300 C200 400 300 460 360 470" fill="none" stroke="#ef4444" stroke-width="10"/>
        <path d="M360 70 C510 90 560 200 540 300 C520 400 420 460 360 470" fill="none" stroke="#ef4444" stroke-width="10"/>
        <text x="120" y="90" font-size="13" fill="#b91c1c">体循环（红）</text>
      </g>
      <g data-part="pulmonary" data-flow>
        <path d="M300 210 C240 150 240 110 300 100 C330 95 340 130 330 160" fill="none" stroke="#3b82f6" stroke-width="8"/>
        <path d="M420 210 C480 150 480 110 420 100 C390 95 380 130 390 160" fill="none" stroke="#3b82f6" stroke-width="8"/>
        <text x="500" y="90" font-size="13" fill="#1d4ed8">肺循环（蓝）</text>
      </g>
      <g data-part="heart" data-beat>
        <path d="M360 250 C330 210 270 220 270 280 C270 340 360 390 360 390 C360 390 450 340 450 280 C450 220 390 210 360 250Z"
              fill="#fda4af" stroke="#be123c" stroke-width="4"/>
        <line x1="360" y1="250" x2="360" y2="380" stroke="#9f1239" stroke-width="2"/>
        <line x1="300" y1="300" x2="420" y2="300" stroke="#9f1239" stroke-width="2"/>
        <text x="318" y="285" font-size="11" fill="#9f1239">右</text>
        <text x="382" y="285" font-size="11" fill="#9f1239">左</text>
        <text x="360" y="430" text-anchor="middle" font-size="14" fill="#9f1239">心脏</text>
      </g>
      <g data-part="artery">
        <text x="200" y="200" font-size="13" fill="#b91c1c">动脉 · 离心</text>
      </g>
      <g data-part="vein">
        <text x="455" y="330" font-size="13" fill="#1d4ed8">静脉 · 回心</text>
      </g>
      <g data-part="capillary">
        <circle cx="180" cy="300" r="8" fill="#fca5a5"/>
        <circle cx="540" cy="300" r="8" fill="#fca5a5"/>
        <text x="70" y="330" font-size="13" fill="#be123c">毛细血管</text>
      </g>
    """)
    return {
        "id": "circulatory_system",
        "title": "人体循环系统",
        "subtitle": "体循环送氧，肺循环换气；心脏是泵",
        "badge": "初中生物 · 人体",
        "equation": "左心室 → 全身 → 右心房　|　右心室 → 肺 → 左心房",
        "hint": "心脏在跳动，血流沿体循环和肺循环流动。图的右是人体的左。",
        "intro": "血液循环分体循环和肺循环，同时进行。动脉离心，静脉回心，毛细血管是物质交换场所。",
        "svg": svg,
        "parts": [
            {"id": "heart", "name": "心脏", "hint": "四腔，左右不互通",
             "detail": "左心房、左心室走动脉血；右心房、右心室走静脉血。左右之间有房间隔、室间隔，正常情况下不相通。左心室壁最厚，因为要泵向全身。",
             "mistake": "图上的左是人体的左，看图时左右是反的。"},
            {"id": "systemic", "name": "体循环", "hint": "左心室出发，右心房回来",
             "detail": "左心室 → 主动脉 → 各级动脉 → 身体各部毛细血管（供氧、收二氧化碳）→ 各级静脉 → 上、下腔静脉 → 右心房。"},
            {"id": "pulmonary", "name": "肺循环", "hint": "右心室出发，左心房回来",
             "detail": "右心室 → 肺动脉（静脉血）→ 肺部毛细血管（换气）→ 肺静脉（动脉血）→ 左心房。肺动脉是少见的“动脉里流静脉血”。"},
            {"id": "artery", "name": "动脉", "hint": "把血送出心脏",
             "detail": "管壁厚、弹性大。除肺动脉外，动脉中一般是动脉血。"},
            {"id": "vein", "name": "静脉", "hint": "把血送回心脏",
             "detail": "管壁较薄，有的有静脉瓣防止倒流。除肺静脉外，静脉中一般是静脉血。"},
            {"id": "capillary", "name": "毛细血管", "hint": "物质交换",
             "detail": "管壁只由一层上皮细胞构成，血流最慢，利于氧气、营养和废物交换。"},
        ],
        "quiz": {
            "q": "肺动脉里流的是？",
            "options": [
                {"t": "静脉血", "ok": True},
                {"t": "动脉血", "ok": False, "why": "肺动脉从右心室出发，还没经过肺泡换气。"},
                {"t": "淋巴", "ok": False, "why": "淋巴不在动脉里。"},
            ],
            "ok": "动脉/静脉按方向命名（离/回心脏），不按颜色。",
            "explain": "肺动脉：静脉血；肺静脉：动脉血。这是最常考的例外。",
        },
    }


def build_respiratory() -> dict:
    svg = _svg("""
      <g data-part="nasal">
        <ellipse cx="360" cy="70" rx="36" ry="28" fill="#fecaca" stroke="#b91c1c"/>
        <text x="410" y="75" font-size="13" fill="#9f1239">鼻腔</text>
      </g>
      <g data-part="pharynx">
        <rect x="348" y="98" width="24" height="28" rx="8" fill="#fda4af"/>
        <text x="380" y="118" font-size="13" fill="#9f1239">咽</text>
      </g>
      <g data-part="larynx">
        <rect x="346" y="126" width="28" height="22" rx="6" fill="#fb7185"/>
        <text x="384" y="142" font-size="13" fill="#9f1239">喉</text>
      </g>
      <g data-part="trachea">
        <rect x="348" y="148" width="24" height="70" rx="8" fill="#fdba74" stroke="#c2410c"/>
        <g stroke="#ea580c" stroke-width="2">
          <line x1="350" y1="162" x2="370" y2="162"/><line x1="350" y1="176" x2="370" y2="176"/>
          <line x1="350" y1="190" x2="370" y2="190"/>
        </g>
        <text x="384" y="185" font-size="13" fill="#9a3412">气管</text>
      </g>
      <g data-part="bronchus">
        <path d="M360 218 L300 270" stroke="#f97316" stroke-width="10" fill="none"/>
        <path d="M360 218 L420 270" stroke="#f97316" stroke-width="10" fill="none"/>
        <text x="430" y="250" font-size="13" fill="#c2410c">支气管</text>
      </g>
      <g data-part="lung" data-breathe>
        <ellipse cx="285" cy="330" rx="90" ry="120" fill="#fecaca" stroke="#e11d48" stroke-width="3"/>
        <ellipse cx="435" cy="330" rx="90" ry="120" fill="#fecaca" stroke="#e11d48" stroke-width="3"/>
        <text x="285" y="330" text-anchor="middle" font-size="16" fill="#9f1239">肺</text>
        <text x="435" y="330" text-anchor="middle" font-size="16" fill="#9f1239">肺</text>
      </g>
      <g data-part="alveolus" data-pulse>
        <circle cx="250" cy="300" r="12" fill="#fecdd3" stroke="#be123c"/>
        <circle cx="268" cy="318" r="10" fill="#fecdd3" stroke="#be123c"/>
        <circle cx="240" cy="322" r="9" fill="#fecdd3" stroke="#be123c"/>
        <text x="175" y="290" font-size="13" fill="#9f1239">肺泡</text>
      </g>
      <g data-part="diaphragm" data-bob>
        <path d="M180 455 Q360 500 540 455" fill="none" stroke="#64748b" stroke-width="10"/>
        <text x="360" y="510" text-anchor="middle" font-size="13" fill="#334155">膈肌</text>
      </g>
    """)
    return {
        "id": "respiratory_system",
        "title": "人体呼吸系统",
        "subtitle": "呼吸道清洁空气，肺泡完成气体交换",
        "badge": "初中生物 · 人体",
        "hint": "肺在呼吸、膈肌在起伏。气体交换发生在肺泡，不在气管。",
        "intro": "呼吸系统 = 呼吸道 + 肺。呼吸道是通道，肺是交换器官。",
        "svg": svg,
        "parts": [
            {"id": "nasal", "name": "鼻腔", "hint": "温暖、湿润、清洁空气",
             "detail": "黏膜分泌黏液，纤毛扫灰尘。用鼻呼吸比用口呼吸更能保护呼吸道。"},
            {"id": "pharynx", "name": "咽", "hint": "消化和呼吸的交叉路口",
             "detail": "空气和食物都经过咽。吞咽时会厌软骨盖住喉口，防止食物进入气管。"},
            {"id": "larynx", "name": "喉", "hint": "有声带",
             "detail": "空气振动声带发声。异物刺激喉会引起咳嗽反射。"},
            {"id": "trachea", "name": "气管", "hint": "C 形软骨保持开放",
             "detail": "管壁有 C 形软骨，后壁柔软，方便食道扩张。黏膜纤毛向上摆动，把痰送到咽部。"},
            {"id": "bronchus", "name": "支气管", "hint": "入肺再分支",
             "detail": "左右支气管进入左右肺，再分支成细支气管，末端连肺泡。"},
            {"id": "lung", "name": "肺", "hint": "气体交换的器官",
             "detail": "左肺两叶、右肺三叶。肺由大量肺泡构成，血流丰富。"},
            {"id": "alveolus", "name": "肺泡", "hint": "一层细胞，外包毛细血管",
             "detail": "氧气进入血液，二氧化碳排出。肺泡数量极多，总面积大。"},
            {"id": "diaphragm", "name": "膈肌", "hint": "呼吸运动的主力",
             "detail": "吸气：膈肌收缩变平，胸腔上下径增大，肺扩张，气压下降，气体入肺。呼气则相反（平静呼吸时膈肌舒张）。"},
        ],
        "quiz": {
            "q": "氧气进入血液发生在？",
            "options": [
                {"t": "肺泡", "ok": True},
                {"t": "气管", "ok": False, "why": "气管只是通道。"},
                {"t": "鼻腔", "ok": False, "why": "鼻腔清洁空气，不交换气体。"},
                {"t": "咽", "ok": False, "why": "咽是交叉路口，不是交换场所。"},
            ],
            "ok": "肺泡壁和毛细血管壁都极薄，适合扩散。",
            "explain": "组织细胞处还有一次气体交换：动脉血变成静脉血。",
        },
    }


def build_neuron() -> dict:
    svg = _svg("""
      <g data-part="dendrite">
        <path d="M80 120 L180 210" stroke="#4d7c0f" stroke-width="6"/>
        <path d="M60 200 L180 220" stroke="#4d7c0f" stroke-width="6"/>
        <path d="M90 280 L180 230" stroke="#4d7c0f" stroke-width="6"/>
        <path d="M70 90 L100 140" stroke="#65a30d" stroke-width="3"/>
        <path d="M40 190 L90 205" stroke="#65a30d" stroke-width="3"/>
        <text x="50" y="80" font-size="14" fill="#3f6212">树突</text>
      </g>
      <g data-part="soma">
        <circle cx="220" cy="220" r="48" fill="#86efac" stroke="#166534" stroke-width="4"/>
        <circle cx="232" cy="210" r="12" fill="#166534"/>
        <text x="220" y="290" text-anchor="middle" font-size="14" fill="#14532d">细胞体</text>
      </g>
      <g data-part="axon" data-flow>
        <line x1="268" y1="220" x2="560" y2="220" stroke="#15803d" stroke-width="10"/>
        <text x="390" y="180" font-size="14" fill="#14532d">轴突</text>
      </g>
      <circle data-sim="impulse" r="8" fill="#22c55e" cx="0" cy="0"/>
      <g data-part="myelin">
        <ellipse cx="340" cy="220" rx="28" ry="18" fill="#fef9c3" stroke="#ca8a04" stroke-width="2"/>
        <ellipse cx="420" cy="220" rx="28" ry="18" fill="#fef9c3" stroke="#ca8a04" stroke-width="2"/>
        <ellipse cx="500" cy="220" rx="28" ry="18" fill="#fef9c3" stroke="#ca8a04" stroke-width="2"/>
        <text x="390" y="260" font-size="14" fill="#854d0e">髓鞘</text>
      </g>
      <g data-part="terminal">
        <path d="M560 220 L620 180" stroke="#166534" stroke-width="5"/>
        <path d="M560 220 L630 220" stroke="#166534" stroke-width="5"/>
        <path d="M560 220 L620 260" stroke="#166534" stroke-width="5"/>
        <circle cx="620" cy="180" r="6" fill="#166534"/>
        <circle cx="630" cy="220" r="6" fill="#166534"/>
        <circle cx="620" cy="260" r="6" fill="#166534"/>
        <text x="580" y="150" font-size="14" fill="#14532d">神经末梢</text>
      </g>
      <polygon points="200,140 268,212 190,160" fill="#22c55e" opacity=".35"/>
      <text x="250" y="120" font-size="12" fill="#166534">冲动方向：树突 → 细胞体 → 轴突</text>
    """)
    return {
        "id": "neuron",
        "title": "神经元",
        "subtitle": "结构决定方向：树突接收，轴突传出",
        "badge": "初中 / 高中生物 · 神经",
        "period": 2800,
        "tracks": [
            {"id": "impulse", "path": "M100 180 L220 220 L560 220 L630 220"},
        ],
        "hint": "绿色脉冲沿树突→细胞体→轴突单向传导。",
        "intro": "神经元是神经系统的基本结构和功能单位，能接受刺激、产生并传导兴奋。",
        "svg": svg,
        "parts": [
            {"id": "dendrite", "name": "树突", "hint": "接收信息，短而分支多",
             "detail": "把其他神经元传来的信号送到细胞体。树突越多，能整合的信息越多。"},
            {"id": "soma", "name": "细胞体", "hint": "代谢中心，含细胞核",
             "detail": "维持神经元生命活动。灰质、神经节主要由细胞体构成。"},
            {"id": "axon", "name": "轴突", "hint": "把冲动传出去，通常一根且较长",
             "detail": "一根轴突可很长（如坐骨神经）。神经纤维主要指轴突（及外包的髓鞘）。"},
            {"id": "myelin", "name": "髓鞘", "hint": "绝缘，让传导更快",
             "detail": "有髓纤维呈跳跃传导，速度快。白质主要是有髓神经纤维。"},
            {"id": "terminal", "name": "神经末梢", "hint": "与下一个细胞形成突触",
             "detail": "轴突末端分支，通过突触把信号传给肌肉、腺体或另一个神经元。突触处是化学传递，单向。"},
        ],
        "quiz": {
            "q": "兴奋在一个神经元上的传导方向是？",
            "options": [
                {"t": "树突 → 细胞体 → 轴突", "ok": True},
                {"t": "轴突 → 细胞体 → 树突", "ok": False, "why": "方向反了。"},
                {"t": "两边同时向细胞体", "ok": False, "why": "胞体整合后再经轴突传出。"},
            ],
            "ok": "结构决定了单向：树突收、轴突出。",
            "explain": "在反射弧里还要加上感受器、神经中枢、效应器。",
        },
    }


def build_nervous_system() -> dict:
    svg = _svg("""
      <g data-part="brain">
        <ellipse cx="360" cy="90" rx="70" ry="55" fill="#fda4af" stroke="#be123c" stroke-width="3"/>
        <ellipse cx="360" cy="125" rx="28" ry="16" fill="#fb7185"/>
        <text x="360" y="40" text-anchor="middle" font-size="14" fill="#9f1239">脑</text>
      </g>
      <g data-part="spinal">
        <rect x="348" y="150" width="24" height="230" rx="10" fill="#f9a8d4" stroke="#be185d" stroke-width="3"/>
        <text x="380" y="270" font-size="14" fill="#9d174d">脊髓</text>
      </g>
      <g data-part="nerve" data-flow>
        <path d="M360 180 L250 210 L180 250" stroke="#e11d48" stroke-width="5" fill="none"/>
        <path d="M360 180 L470 210 L540 250" stroke="#e11d48" stroke-width="5" fill="none"/>
        <path d="M360 250 L240 300 L170 360" stroke="#e11d48" stroke-width="5" fill="none"/>
        <path d="M360 250 L480 300 L550 360" stroke="#e11d48" stroke-width="5" fill="none"/>
        <path d="M360 330 L260 400 L230 460" stroke="#e11d48" stroke-width="5" fill="none"/>
        <path d="M360 330 L460 400 L490 460" stroke="#e11d48" stroke-width="5" fill="none"/>
        <text x="120" y="250" font-size="14" fill="#9f1239">周围神经</text>
      </g>
      <g data-part="cns">
        <text x="360" y="500" text-anchor="middle" font-size="13" fill="#334155">中枢神经系统 = 脑 + 脊髓</text>
      </g>
    """)
    return {
        "id": "nervous_system",
        "title": "人体神经系统",
        "subtitle": "中枢发令，周围传递",
        "badge": "初中生物 · 人体",
        "hint": "脑和脊髓是中枢；遍布全身的是周围神经。",
        "intro": "神经系统分为中枢神经系统（脑、脊髓）和周围神经系统（脑神经、脊神经等）。",
        "svg": svg,
        "parts": [
            {"id": "brain", "name": "脑", "hint": "大脑、小脑、脑干",
             "detail": "大脑：感觉、运动、语言、思维。小脑：维持平衡、协调运动。脑干：呼吸、心跳等基本生命活动，有“活的化石”之称的生命中枢。"},
            {"id": "spinal", "name": "脊髓", "hint": "传导 + 低级反射中枢",
             "detail": "能完成膝跳等简单反射；也把身体信号上传到脑、把脑的指令下传到身体。脊髓横断会导致断面以下感觉和运动障碍。"},
            {"id": "nerve", "name": "周围神经", "hint": "连接中枢与全身",
             "detail": "传入神经把感受器信号送入中枢，传出神经把指令送到效应器。12 对脑神经、31 对脊神经。"},
            {"id": "cns", "name": "中枢神经系统", "hint": "脑 + 脊髓",
             "detail": "反射弧：感受器 → 传入神经 → 神经中枢 → 传出神经 → 效应器。缺任何一环，反射都不能完成。"},
        ],
        "quiz": {
            "q": "膝跳反射的神经中枢位于？",
            "options": [
                {"t": "脊髓", "ok": True},
                {"t": "大脑皮层", "ok": False, "why": "膝跳是简单反射，中枢在脊髓；大脑可以感知，但不是完成反射所必需。"},
                {"t": "小脑", "ok": False, "why": "小脑管平衡与协调。"},
                {"t": "脑干", "ok": False, "why": "脑干管呼吸心跳等。"},
            ],
            "ok": "简单反射的中枢在脊髓或脑干。",
            "explain": "缩手反射也一样：先缩手（脊髓），后感到疼（大脑）。",
        },
    }


def build_photosynthesis() -> dict:
    svg = _svg("""
      <g data-part="leaf">
        <ellipse cx="360" cy="260" rx="220" ry="140" fill="#86efac" stroke="#166534" stroke-width="6"/>
        <line x1="140" y1="260" x2="80" y2="280" stroke="#166534" stroke-width="10"/>
      </g>
      <g data-part="chloro">
        <ellipse cx="360" cy="250" rx="120" ry="70" fill="#22c55e" stroke="#14532d" stroke-width="4"/>
        <ellipse cx="330" cy="245" rx="28" ry="16" fill="#bbf7d0"/>
        <ellipse cx="375" cy="260" rx="26" ry="14" fill="#bbf7d0"/>
        <ellipse cx="390" cy="230" rx="22" ry="12" fill="#bbf7d0"/>
        <text x="360" y="255" text-anchor="middle" font-size="13" fill="#14532d">叶绿体</text>
      </g>
      <g data-part="light" data-pulse>
        <polygon points="360,40 372,80 400,80 378,100 388,140 360,118 332,140 342,100 320,80 348,80" fill="#facc15"/>
        <text x="410" y="70" font-size="14" fill="#a16207">光</text>
      </g>
      <g data-part="water" data-flow>
        <path d="M80 280 C90 250 70 250 80 220" fill="none" stroke="#0ea5e9" stroke-width="4"/>
        <circle cx="80" cy="210" r="6" fill="#38bdf8"/>
        <text x="40" y="200" font-size="13" fill="#0369a1">H₂O</text>
      </g>
      <g data-part="co2" data-flow>
        <text x="560" y="200" font-size="16" fill="#334155">CO₂</text>
        <path d="M555 210 L480 240" stroke="#64748b" stroke-width="3"/>
      </g>
      <g data-part="o2" data-flow>
        <text x="560" y="320" font-size="16" fill="#0369a1">O₂</text>
        <path d="M470 280 L545 310" stroke="#0ea5e9" stroke-width="3"/>
      </g>
      <g data-part="sugar">
        <rect x="300" y="360" width="120" height="36" rx="8" fill="#fef9c3" stroke="#ca8a04"/>
        <text x="360" y="384" text-anchor="middle" font-size="14" fill="#854d0e">有机物 (CH₂O)</text>
      </g>
    """)
    return {
        "id": "photosynthesis",
        "title": "光合作用",
        "subtitle": "叶绿体：光能 → 化学能，CO₂ + H₂O → 有机物 + O₂",
        "badge": "初中 / 高中生物 · 代谢",
        "equation": "CO₂ + H₂O  →(光、叶绿体)  (CH₂O) + O₂",
        "hint": "氧气来自水的光解，不是来自二氧化碳。",
        "intro": "绿色植物在光下，在叶绿体中把二氧化碳和水合成储存能量的有机物，并释放氧气。",
        "svg": svg,
        "parts": [
            {"id": "leaf", "name": "叶", "hint": "光合作用的主要器官",
             "detail": "叶肉细胞含大量叶绿体。气孔进二氧化碳、出氧气和水蒸气。"},
            {"id": "chloro", "name": "叶绿体", "hint": "光合作用的场所",
             "detail": "类囊体薄膜上进行光反应；基质中进行暗反应（卡尔文循环）。含光合色素。"},
            {"id": "light", "name": "光反应", "hint": "必须要光",
             "detail": "水分解产生氧气、[H]（NADPH）和 ATP。场所：类囊体薄膜。",
             "mistake": "释放的氧气来自水，不是 CO₂。"},
            {"id": "water", "name": "水", "hint": "光解的原料",
             "detail": "根吸收的水，一部分用于光解。同位素实验证明 O₂ 中的氧来自水。"},
            {"id": "co2", "name": "二氧化碳", "hint": "碳的来源",
             "detail": "经气孔进入，在叶绿体基质中被固定，最终进入有机物。"},
            {"id": "o2", "name": "氧气", "hint": "光反应的产物",
             "detail": "供植物自己呼吸，也释放到大气中，是地球氧气的主要来源。"},
            {"id": "sugar", "name": "有机物", "hint": "暗反应的产物",
             "detail": "葡萄糖等有机物，供呼吸消耗或转化成淀粉、蛋白质、脂肪储存。暗反应不直接需要光，但需要光反应提供的 ATP 和 [H]。"},
        ],
        "quiz": {
            "q": "光合作用释放的氧气来自？",
            "options": [
                {"t": "水", "ok": True},
                {"t": "二氧化碳", "ok": False, "why": "CO₂ 中的氧进入有机物和水，不进入释放的 O₂。"},
                {"t": "叶绿素", "ok": False, "why": "叶绿素吸收光，本身不是氧的来源。"},
                {"t": "葡萄糖", "ok": False, "why": "葡萄糖是产物不是原料。"},
            ],
            "ok": "鲁宾和卡门的同位素实验：H₂¹⁸O 产生 ¹⁸O₂。",
            "explain": "原料是 CO₂ 和 H₂O，条件是光和叶绿体，产物是有机物和 O₂。",
        },
    }


def build_dna() -> dict:
    svg = _svg("""
      <text x="360" y="36" text-anchor="middle" font-size="14" fill="#1e3a8a">DNA 双螺旋 · 碱基互补配对</text>
      <g data-part="backbone" data-flow>
        <path d="M160 80 C200 140 200 200 160 260 C120 320 120 380 160 440 C200 500 200 520 180 500"
              fill="none" stroke="#0369a1" stroke-width="10"/>
        <path d="M560 80 C520 140 520 200 560 260 C600 320 600 380 560 440 C520 500 520 520 540 500"
              fill="none" stroke="#0f766e" stroke-width="10"/>
        <text x="90" y="180" font-size="13" fill="#075985">磷酸-脱氧核糖骨架</text>
      </g>
      <g data-part="at">
        <line x1="200" y1="140" x2="520" y2="140" stroke="#ef4444" stroke-width="8"/>
        <circle cx="230" cy="140" r="16" fill="#fecaca"/><text x="230" y="145" text-anchor="middle" font-size="12">A</text>
        <circle cx="490" cy="140" r="16" fill="#bbf7d0"/><text x="490" y="145" text-anchor="middle" font-size="12">T</text>
        <text x="360" y="128" text-anchor="middle" font-size="12" fill="#b91c1c">A—T（2 个氢键）</text>
      </g>
      <g data-part="gc">
        <line x1="185" y1="220" x2="535" y2="220" stroke="#3b82f6" stroke-width="8"/>
        <circle cx="220" cy="220" r="16" fill="#bfdbfe"/><text x="220" y="225" text-anchor="middle" font-size="12">G</text>
        <circle cx="500" cy="220" r="16" fill="#fde68a"/><text x="500" y="225" text-anchor="middle" font-size="12">C</text>
        <text x="360" y="208" text-anchor="middle" font-size="12" fill="#1d4ed8">G—C（3 个氢键）</text>
      </g>
      <g data-part="at2">
        <line x1="200" y1="300" x2="520" y2="300" stroke="#ef4444" stroke-width="8"/>
        <circle cx="230" cy="300" r="16" fill="#bbf7d0"/><text x="230" y="305" text-anchor="middle" font-size="12">T</text>
        <circle cx="490" cy="300" r="16" fill="#fecaca"/><text x="490" y="305" text-anchor="middle" font-size="12">A</text>
      </g>
      <g data-part="gc2">
        <line x1="185" y1="380" x2="535" y2="380" stroke="#3b82f6" stroke-width="8"/>
        <circle cx="220" cy="380" r="16" fill="#fde68a"/><text x="220" y="385" text-anchor="middle" font-size="12">C</text>
        <circle cx="500" cy="380" r="16" fill="#bfdbfe"/><text x="500" y="385" text-anchor="middle" font-size="12">G</text>
      </g>
      <g data-part="helix">
        <text x="360" y="500" text-anchor="middle" font-size="13" fill="#334155">两条链反向平行 · 右手螺旋</text>
      </g>
    """)
    return {
        "id": "dna_structure",
        "title": "DNA 双螺旋",
        "subtitle": "外侧骨架，内侧碱基配对：A-T、G-C",
        "badge": "高中生物 · 遗传",
        "equation": "A = T　　G ≡ C",
        "hint": "点红色横档看 A-T，点蓝色横档看 G-C。外侧是磷酸和脱氧核糖。",
        "intro": "DNA 是规则的双螺旋。两条链靠碱基互补配对连在一起，这是复制和转录的结构基础。",
        "svg": svg,
        "parts": [
            {"id": "backbone", "name": "外侧骨架", "hint": "磷酸 + 脱氧核糖交替连接",
             "detail": "脱氧核糖核苷酸：磷酸、脱氧核糖、碱基。骨架在外侧，碱基在内侧。"},
            {"id": "at", "name": "A-T 配对", "hint": "腺嘌呤 — 胸腺嘧啶，2 个氢键",
             "detail": "嘌呤配嘧啶，使双螺旋直径保持 2 nm。A 的数量等于 T。"},
            {"id": "gc", "name": "G-C 配对", "hint": "鸟嘌呤 — 胞嘧啶，3 个氢键",
             "detail": "G-C 比 A-T 更稳定。G+C 比例高的 DNA 更耐热。G 的数量等于 C。"},
            {"id": "at2", "name": "互补链", "hint": "一条链能决定另一条",
             "detail": "已知一条链序列，就能写出互补链。这是半保留复制的基础。"},
            {"id": "gc2", "name": "碱基种类", "hint": "DNA 有 A、T、G、C，没有 U",
             "detail": "尿嘧啶 U 出现在 RNA 里，替换胸腺嘧啶 T。"},
            {"id": "helix", "name": "双螺旋", "hint": "反向平行，右手螺旋",
             "detail": "一条链 5'→3'，另一条 3'→5'。沃森和克里克提出该模型。"},
        ],
        "quiz": {
            "q": "DNA 中腺嘌呤 A 一定等于？",
            "options": [
                {"t": "胸腺嘧啶 T", "ok": True},
                {"t": "鸟嘌呤 G", "ok": False, "why": "A 不等于 G。Chargaff 规则是 A=T、G=C。"},
                {"t": "尿嘧啶 U", "ok": False, "why": "U 在 RNA 中。"},
                {"t": "磷酸数的一半", "ok": False, "why": "每个核苷酸都有磷酸，和 A 的数量没有这层关系。"},
            ],
            "ok": "碱基互补配对：A=T，G=C。",
            "explain": "双链 DNA 中嘌呤总数等于嘧啶总数。",
        },
    }


REGISTRY = {
    "animal_cell": build_animal_cell,
    "plant_cell": build_plant_cell,
    "mitosis": build_mitosis,
    "digestive_system": build_digestive,
    "circulatory_system": build_circulatory,
    "respiratory_system": build_respiratory,
    "neuron": build_neuron,
    "nervous_system": build_nervous_system,
    "photosynthesis": build_photosynthesis,
    "dna_structure": build_dna,
}


def main(argv: list[str]) -> None:
    if not argv or argv[0] == "list":
        print("已注册生物场景:")
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
