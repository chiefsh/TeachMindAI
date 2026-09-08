"""把课件页画成 ppt-master 合规 SVG，再交给 svg_to_pptx 导出 PPTX。

约束（ppt-master 会拒收）：禁止 foreignObject / <style> / class / iframe / script；
顶层可见 <g> 必须带根坐标系 data-pptx-bounds 且互不重叠；颜色 #RRGGBB；
font-size 无单位。公式走行内 OMML 标记；互动用 skill 静态图 + 点击揭示。
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from app.services.courseware_theme import get_theme, page_kind, page_label

log = logging.getLogger(__name__)

W, H = 1280, 720
FONT = "Microsoft YaHei, PingFang SC, Arial, sans-serif"
VENDOR = Path(__file__).resolve().parents[2] / "vendor" / "ppt-master"
PAD = 64
HEADER_Y, HEADER_H = 28, 118
BODY_Y = 160
BODY_BOTTOM = 688
# 16:9 课堂投影：正文字号对齐 ppt169 presentation 量级，少放条目避免挤。
SZ_KICKER = 18
SZ_CAPTION = 20
SZ_BODY = 24
SZ_SUB = 28
SZ_TITLE = 36
SZ_DISPLAY = 48
LEAD = 1.75

_HEX = set("0123456789abcdefABCDEF")


def _plain(text: str) -> str:
    from app.services.export_service import _clean_text
    return _clean_text(text or "")


def _src(text: str) -> str:
    from app.services.export_service import _strip_markdown
    return _strip_markdown(text or "")


_COMPILE = None
_COMPILE_ERR = None


def _formula_ok(latex: str) -> bool:
    """ppt-master 编译不过的 LaTeX 退回预览字，避免质量检查整页失败。"""
    global _COMPILE, _COMPILE_ERR
    src = (latex or "").strip()
    if not src:
        return False
    if _COMPILE is None:
        scripts = str(VENDOR / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        try:
            from svg_to_pptx.native_objects.formula_compiler import (
                FormulaCompileError, compile_latex_to_inline_omml,
            )
            _COMPILE = compile_latex_to_inline_omml
            _COMPILE_ERR = FormulaCompileError
        except Exception:
            _COMPILE = False
            return False
    if _COMPILE is False:
        return False
    try:
        _COMPILE(src)
        return True
    except Exception:
        return False


def _rich_segs(text: str) -> list[tuple[str, str, str]]:
    from app.services.export_service import iter_rich_segments
    out: list[tuple[str, str, str]] = []
    for kind, payload, preview in iter_rich_segments(text):
        if kind == "math" and _formula_ok(payload):
            out.append(("math", payload, preview))
        else:
            out.append(("text", preview if kind == "math" else payload, preview if kind == "math" else payload))
    return out


def wrap_rich(
    text: str, max_w: float, size: float, max_lines: int = 8,
) -> list[list[tuple[str, str, str]]]:
    segs = _rich_segs(text)
    budget = max(size, float(max_w) * 0.90)
    lines: list[list[tuple[str, str, str]]] = []
    cur: list[tuple[str, str, str]] = []
    width = 0.0

    def push(kind: str, raw: str, preview: str, w: float) -> None:
        nonlocal cur, width
        if cur and cur[-1][0] == "text" and kind == "text":
            prev = cur[-1]
            cur[-1] = ("text", prev[1] + raw, prev[2] + preview)
        else:
            cur.append((kind, raw, preview))
        width += w

    for kind, raw, preview in segs:
        if kind == "math":
            w = _measure(preview, size)
            if cur and width + w > budget:
                lines.append(cur)
                cur, width = [], 0.0
            push(kind, raw, preview, w)
            continue
        for ch in raw.replace("\r", ""):
            if ch == "\n":
                if cur:
                    lines.append(cur)
                cur, width = [], 0.0
                continue
            w = _cw(ch, size)
            if cur and width + w > budget:
                lines.append(cur)
                cur, width = [], 0.0
            push("text", ch, ch, w)
    if cur:
        lines.append(cur)
    if not lines:
        return []
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        if last and last[-1][0] == "text":
            last[-1] = ("text", last[-1][1] + "…", last[-1][2] + "…")
        else:
            last.append(("text", "…", "…"))
    return lines


def _hex(c: str, fallback: str = "#334155") -> str:
    h = (c or "").strip()
    if h.startswith("#") and len(h) == 7 and all(ch in _HEX for ch in h[1:]):
        return h.upper()
    return fallback


def _esc(s: str) -> str:
    return escape(s or "", {"\"": "&quot;"})


def _cw(ch: str, size: float) -> float:
    """ppt-master 检查器按约 0.99em/字估宽；ASCII 估窄会导致整页 overflow。"""
    if ch == " ":
        return size * 0.5
    return size


def _measure(text: str, size: float) -> float:
    return sum(_cw(ch, size) for ch in text)


def wrap_text(text: str, max_w: float, size: float, max_lines: int = 8) -> list[str]:
    raw = _plain(text).replace("\r", "")
    budget = max(size, float(max_w) * 0.90)
    lines: list[str] = []
    for para in raw.split("\n"):
        para = para.strip()
        if not para:
            continue
        cur, width = "", 0.0
        for ch in para:
            w = _cw(ch, size)
            if cur and width + w > budget:
                lines.append(cur)
                cur, width = ch, w
            else:
                cur += ch
                width += w
        if cur:
            lines.append(cur)
    if not lines:
        return []
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        lines[-1] = (last[:-1] if last else "") + "…"
    return lines


def _bounds(x: float, y: float, w: float, h: float) -> str:
    return f'{_r(x)} {_r(y)} {_r(w)} {_r(h)}'


def _r(n: float) -> str:
    v = round(float(n), 2)
    if abs(v - int(v)) < 1e-9:
        return str(int(v))
    return f"{v:.2f}".rstrip("0").rstrip(".")


class Page:
    def __init__(self, theme: dict[str, str], page_role: str = "content"):
        self.th = {k: _hex(v, v) if isinstance(v, str) and str(v).startswith("#") else v
                   for k, v in theme.items()}
        self.page_role = page_role
        self.defs: list[str] = []
        self.loose: list[str] = []
        self.groups: list[str] = []
        self._n = 0

    def nid(self, prefix: str = "n") -> str:
        self._n += 1
        return f"{prefix}-{self._n}"

    def add_def(self, xml: str) -> None:
        self.defs.append(xml)

    def rect(
        self, x: float, y: float, w: float, h: float, fill: str,
        rx: float = 0, extra: str = "", oid: str | None = None,
        role: str | None = None,
    ) -> str:
        rid = oid or self.nid("r")
        rx_a = f' rx="{_r(rx)}" ry="{_r(rx)}"' if rx else ""
        role_a = f' data-pptx-role="{role}"' if role else ""
        return (
            f'<rect id="{rid}" x="{_r(x)}" y="{_r(y)}" width="{_r(w)}" height="{_r(h)}"'
            f' fill="{fill}"{rx_a}{role_a}{extra}/>'
        )

    def circle(self, cx: float, cy: float, r: float, fill: str, fo: float) -> str:
        return (
            f'<circle id="{self.nid("c")}" cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(r)}"'
            f' fill="{fill}" fill-opacity="{fo}"/>'
        )

    def text(
        self, x: float, y: float, s: str, size: float, fill: str,
        weight: str = "400", anchor: str = "start",
    ) -> str:
        t = _esc(s)
        if not t.strip():
            return ""
        anc = f' text-anchor="{anchor}"' if anchor != "start" else ""
        wt = f' font-weight="{weight}"' if weight != "400" else ""
        return (
            f'<text id="{self.nid("t")}" x="{_r(x)}" y="{_r(y)}" fill="{fill}"'
            f' font-size="{_r(size)}"{wt}{anc}>{t}</text>'
        )

    def lines(
        self, x: float, y0: float, items: list[str], size: float, fill: str,
        leading: float = 1.75, weight: str = "400", anchor: str = "start",
    ) -> str:
        rows = [s for s in items if str(s).strip()]
        if not rows:
            return ""
        y = y0 + size * 0.82
        dy = size * leading
        anc = f' text-anchor="{anchor}"' if anchor != "start" else ""
        wt = f' font-weight="{weight}"' if weight != "400" else ""
        body = _esc(rows[0]) + "".join(
            f'<tspan x="{_r(x)}" dy="{_r(dy)}">{_esc(s)}</tspan>' for s in rows[1:]
        )
        return (
            f'<text id="{self.nid("t")}" x="{_r(x)}" y="{_r(y)}" fill="{fill}"'
            f' font-size="{_r(size)}"{wt}{anc}>{body}</text>'
        )

    def rich_lines(
        self, x: float, y0: float, rows: list[list[tuple[str, str, str]]],
        size: float, fill: str, leading: float = 1.75, weight: str = "400",
        anchor: str = "start",
    ) -> str:
        clean = [r for r in rows if r]
        if not clean:
            return ""
        y = y0 + size * 0.82
        dy = size * leading
        anc = f' text-anchor="{anchor}"' if anchor != "start" else ""
        wt = f' font-weight="{weight}"' if weight != "400" else ""

        def segs_xml(segs: list[tuple[str, str, str]]) -> str:
            bits = []
            for kind, raw, preview in segs:
                if kind == "math":
                    bits.append(
                        f'<tspan data-pptx-inline-formula="{_esc(raw)}">{_esc(preview)}</tspan>'
                    )
                else:
                    bits.append(_esc(raw))
            return "".join(bits)

        body = segs_xml(clean[0]) + "".join(
            f'<tspan x="{_r(x)}" dy="{_r(dy)}">{segs_xml(row)}</tspan>'
            for row in clean[1:]
        )
        return (
            f'<text id="{self.nid("t")}" x="{_r(x)}" y="{_r(y)}" fill="{fill}"'
            f' font-size="{_r(size)}"{wt}{anc}>{body}</text>'
        )

    def group(self, gid: str, x: float, y: float, w: float, h: float, inner: str) -> None:
        if not inner.strip():
            return
        self.groups.append(
            f'<g id="{gid}" data-pptx-bounds="{_bounds(x, y, w, h)}">{inner}</g>'
        )

    def gradient(self, gid: str, c0: str, c1: str, diagonal: bool = True) -> str:
        if diagonal:
            axis = 'x1="0" y1="0" x2="1" y2="1"'
        else:
            axis = 'x1="0" y1="0" x2="1" y2="0"'
        self.add_def(
            f'<linearGradient id="{gid}" {axis} gradientUnits="objectBoundingBox">'
            f'<stop offset="0" stop-color="{c0}"/>'
            f'<stop offset="1" stop-color="{c1}"/>'
            f'</linearGradient>'
        )
        return f"url(#{gid})"

    def finish(self) -> str:
        defs = f'<defs>{"".join(self.defs)}</defs>' if self.defs else ""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"'
            f' viewBox="0 0 {W} {H}" font-family="{FONT}"'
            f' data-pptx-page-role="{self.page_role}">'
            f'{defs}{"".join(self.loose)}{"".join(self.groups)}</svg>\n'
        )


def _bullets(slide: dict) -> list[str]:
    out = []
    for b in slide.get("bullets") or []:
        t = _src(str(b))
        if t:
            out.append(t)
    return out


def _steps(slide: dict) -> list[tuple[str, str]]:
    raw = slide.get("steps")
    if isinstance(raw, list) and raw:
        steps = []
        for s in raw:
            if isinstance(s, dict):
                title = _src(str(s.get("title") or s.get("name") or ""))
                detail = _src(str(s.get("detail") or s.get("content") or ""))
            else:
                title, detail = _src(str(s)), ""
            if title or detail:
                steps.append((title, detail))
        if steps:
            return steps
    return [(b, "") for b in _bullets(slide)]


def _columns(slide: dict) -> list[tuple[str, list[str]]]:
    raw = slide.get("columns")
    if isinstance(raw, list) and len(raw) >= 2:
        cols = []
        for c in raw[:2]:
            if not isinstance(c, dict):
                continue
            title = _src(str(c.get("title") or "")) or "对照"
            items = []
            for x in c.get("items") or c.get("bullets") or []:
                t = _src(str(x))
                if t:
                    items.append(t)
            cols.append((title, items))
        if len(cols) >= 2:
            return cols
    bs = _bullets(slide)
    mid = max(1, (len(bs) + 1) // 2)
    return [
        (_src(str(slide.get("left_title") or "对照 A")) or "对照 A", bs[:mid]),
        (_src(str(slide.get("right_title") or "对照 B")) or "对照 B", bs[mid:]),
    ]


def _link_text(p: Page, x: float, y: float, label: str, url: str, size: float, fill: str) -> str:
    t = (wrap_text(label, 520, size, 1) or [label])[0]
    if url:
        return (
            f'<text id="{p.nid("t")}" x="{_r(x)}" y="{_r(y)}" fill="{fill}"'
            f' font-size="{_r(size)}" font-weight="700">'
            f'<a href="{_esc(url)}"><tspan>{_esc(t)}</tspan></a></text>'
        )
    return p.text(x, y, t, size, fill, "700")


def _deco(p: Page) -> None:
    th = p.th
    style = th.get("deco_style") or "circles"
    prim, acc = th["primary"], th["accent"]
    bits: list[str] = []
    if style in ("circles", "grid"):
        bits += [
            p.circle(1180, 70, 180, prim, 0.10),
            p.circle(80, 680, 140, acc, 0.12),
            p.circle(1080, 620, 64, prim, 0.14),
        ]
    elif style == "leaves":
        bits += [
            f'<ellipse id="{p.nid("e")}" cx="1220" cy="80" rx="180" ry="90"'
            f' fill="{prim}" fill-opacity="0.10"/>',
            f'<ellipse id="{p.nid("e")}" cx="60" cy="640" rx="160" ry="70"'
            f' fill="{acc}" fill-opacity="0.12"/>',
        ]
    elif style == "waves":
        bits += [
            f'<path id="{p.nid("p")}" d="M0 560 Q160 500 320 560 T640 560 T960 560 T1280 560 V720 H0z"'
            f' fill="{prim}" fill-opacity="0.10"/>',
            f'<path id="{p.nid("p")}" d="M0 600 Q160 660 320 600 T640 600 T960 600 T1280 600 V720 H0z"'
            f' fill="{acc}" fill-opacity="0.10"/>',
        ]
    elif style == "dots":
        bits += [
            p.rect(1040, 0, 240, 720, prim, extra=' fill-opacity="0.06"'),
            p.circle(1200, 80, 90, acc, 0.10),
        ]
    else:
        bits.append(p.rect(0, 0, 10, 720, prim))
    p.groups.insert(
        0,
        f'<g id="deco" data-pptx-role="decoration" data-pptx-bounds="0 0 {W} {H}">'
        f'{"".join(bits)}</g>',
    )


def _fit_line(
    p: Page, x: float, y: float, text: str, size: float, fill: str,
    max_w: float, weight: str = "700", anchor: str = "start", max_lines: int = 2,
) -> str:
    rows = wrap_text(text, max_w, size, max_lines)
    if not rows:
        return ""
    return p.lines(x, y - size * 0.82, rows, size, fill, leading=1.55, weight=weight, anchor=anchor)


def _header(p: Page, label: str, index: int, slide: dict) -> None:
    th = p.th
    kicker = f"第 {index} 页 · {label}" if index else label
    title = _plain(slide.get("title") or "")
    sub = _plain(slide.get("subtitle") or "")
    inner = []
    tw = W - PAD * 2 - 16
    kw = min(480, _measure(kicker, SZ_KICKER) + 32)
    inner.append(p.rect(PAD, HEADER_Y + 6, kw, 32, th["primary"], rx=16))
    inner.append(p.text(
        PAD + 16, HEADER_Y + 28,
        (wrap_text(kicker, 440, SZ_KICKER, 1) or [kicker])[0],
        SZ_KICKER, "#FFFFFF", "700",
    ))
    title_lines = wrap_text(title, tw, SZ_TITLE, 1)
    if title_lines:
        inner.append(p.lines(PAD, HEADER_Y + 44, title_lines, SZ_TITLE, th["text"], leading=1.4, weight="700"))
    sub_lines = wrap_text(sub, tw, SZ_CAPTION, 1)
    if sub_lines:
        inner.append(p.lines(PAD, HEADER_Y + 86, sub_lines, SZ_CAPTION, th["muted"]))
    p.group("header", PAD, HEADER_Y, W - PAD * 2, HEADER_H, "".join(inner))


def _card(
    p: Page, gid: str, x: float, y: float, w: float, h: float,
    fill: str, inner: str, accent_top: str | None = None, accent_left: str | None = None,
) -> None:
    bits = [p.rect(x, y, w, h, fill, rx=16)]
    if accent_top:
        bits.append(p.rect(x, y, w, 5, accent_top, rx=0))
    if accent_left:
        bits.append(p.rect(x, y, 8, h, accent_left, rx=0))
    bits.append(inner)
    p.group(gid, x, y, w, h, "".join(bits))


def _paint_cover(p: Page, slide: dict, subject: str, chapter: str) -> None:
    th = p.th
    style = th.get("cover_style") or "diagonal"
    title = _plain(slide.get("title") or "教学课件") or "教学课件"
    sub = _plain(slide.get("subtitle") or "")
    chap = chapter or "课程封面"
    on = th.get("on_cover") or "#FFFFFF"
    g = p.gradient("coverGrad", th["cover_from"], th["cover_to"], diagonal=True)

    def chap_pill(x: float, y: float, fill: str, fg: str, extra: str = "") -> str:
        label = (wrap_text(chap, 360, SZ_KICKER, 1) or [chap])[0]
        kw = min(400, _measure(label, SZ_KICKER) + 32)
        return (
            p.rect(x, y, kw, 34, fill, rx=17, extra=extra)
            + p.text(x + 16, y + 24, label, SZ_KICKER, fg, "700")
        )

    def subj_line(x: float, y: float, fill: str, max_w: float = 360) -> str:
        label = (wrap_text(subject, max_w, SZ_CAPTION, 1) or [subject])[0] if subject else ""
        if not label:
            return ""
        return p.text(x, y, label, SZ_CAPTION, fill, "600")

    if style == "split":
        p.loose.append(p.rect(0, 0, W, H, th["bg"], role="background"))
        _deco(p)
        p.loose.append(p.rect(0, 0, 538, H, g, role="background"))
        inner = [
            chap_pill(48, 200, "#FFFFFF", on, extra=' fill-opacity="0.18"'),
            _fit_line(p, 48, 310, title, SZ_DISPLAY, on, 430),
        ]
        if sub:
            inner.append(_fit_line(p, 48, 400, sub, SZ_BODY, on, 430, weight="400", max_lines=2))
        p.group("cover-left", 48, 180, 450, 340, "".join(inner))
        right = []
        if subject:
            sl = (wrap_text(subject, 340, SZ_CAPTION, 1) or [subject])[0]
            sw = min(400, _measure(sl, SZ_CAPTION) + 40)
            right.append(p.rect(620, 300, sw, 44, th["surface"], rx=22))
            right.append(p.text(638, 328, sl, SZ_CAPTION, th["text"], "600"))
        right.append(p.text(620, 390, "智课星教学课件", SZ_BODY, th["muted"]))
        p.group("cover-right", 600, 280, 620, 180, "".join(right))
        return

    if style == "ribbon":
        p.loose.append(p.rect(0, 0, W, H, th["bg"], role="background"))
        _deco(p)
        if subject:
            sl = (wrap_text(subject, 340, SZ_CAPTION, 1) or [subject])[0]
            sw = min(400, _measure(sl, SZ_CAPTION) + 40)
            p.group(
                "cover-chip", PAD, 130, sw, 44,
                p.rect(PAD, 130, sw, 44, th["surface"], rx=22)
                + p.text(PAD + 20, 158, sl, SZ_CAPTION, th["text"], "600"),
            )
        p.loose.append(p.rect(0, 210, W, 280, g, role="background"))
        inner = [
            chap_pill(PAD, 240, "#FFFFFF", on, extra=' fill-opacity="0.18"'),
            _fit_line(p, PAD, 340, title, SZ_DISPLAY, on, W - PAD * 2 - 16),
        ]
        if sub:
            inner.append(_fit_line(p, PAD, 420, sub, SZ_BODY, on, W - PAD * 2 - 16, weight="400"))
        p.group("cover-ribbon", PAD, 230, W - PAD * 2, 240, "".join(inner))
        return

    if style == "panel":
        p.loose.append(p.rect(0, 0, W, H, th["bg"], role="background"))
        _deco(p)
        cx, cy, cw, ch = 150, 140, 980, 440
        inner = [p.rect(cx, cy, cw, ch, th["card"], rx=24), p.rect(cx, cy, cw, 8, th["primary"])]
        inner.append(chap_pill(cx + 48, cy + 36, th["primary"], on))
        inner.append(_fit_line(p, cx + 48, cy + 170, title, SZ_DISPLAY, th["text"], cw - 96))
        if sub:
            inner.append(_fit_line(p, cx + 48, cy + 250, sub, SZ_BODY, th["muted"], cw - 96, weight="400"))
        inner.append(subj_line(cx + 48, cy + 340, th["primary"]))
        p.group("cover-card", cx, cy, cw, ch, "".join(inner))
        return

    if style == "lab":
        p.loose.append(p.rect(0, 0, W, H, th["bg"], role="background"))
        _deco(p)
        inner = [
            p.rect(PAD, 400, 200, 12, th["accent"], rx=6),
            chap_pill(PAD, 430, th["primary"], on),
            _fit_line(p, PAD, 530, title, SZ_DISPLAY, th["text"], W - PAD * 2 - 16),
        ]
        if sub:
            inner.append(_fit_line(p, PAD, 610, sub, SZ_BODY, th["muted"], W - PAD * 2 - 16, weight="400"))
        inner.append(subj_line(PAD, 670, th["primary"]))
        p.group("cover-lab", PAD, 390, W - PAD * 2, 300, "".join(inner))
        return

    if style == "minimal":
        p.loose.append(p.rect(0, 0, W, H, th["bg"], role="background"))
        inner = [
            p.rect(PAD, 250, 8, 180, th["primary"]),
            _fit_line(p, PAD + 32, 320, title, SZ_DISPLAY, th["text"], W - PAD * 2 - 48),
        ]
        if sub:
            inner.append(_fit_line(p, PAD + 32, 400, sub, SZ_BODY, th["muted"], W - PAD * 2 - 48, weight="400"))
        inner.append(subj_line(PAD + 32, 460, th["primary"]))
        p.group("cover-min", PAD, 230, W - PAD * 2, 300, "".join(inner))
        return

    p.loose.append(p.rect(0, 0, W, H, g, role="background"))
    p.groups.insert(
        0,
        f'<g id="cover-deco" data-pptx-role="decoration" data-pptx-bounds="0 0 {W} {H}">'
        f'{p.circle(1180, -40, 200, th["accent"], 0.22)}'
        f'{p.rect(0, 680, W, 40, th["accent"])}'
        f'</g>',
    )
    bits = []
    if subject:
        sl = (wrap_text(subject, 340, SZ_CAPTION, 1) or [subject])[0]
        sw = min(400, _measure(sl, SZ_CAPTION) + 40)
        bits.append(p.rect(640 - sw / 2, 176, sw, 40, "#FFFFFF", rx=20, extra=' fill-opacity="0.18"'))
        bits.append(p.text(640, 202, sl, SZ_CAPTION, on, "600", anchor="middle"))
    bits.append(_fit_line(p, 640, 330, title, SZ_DISPLAY, on, 960, anchor="middle"))
    if sub:
        bits.append(_fit_line(p, 640, 410, sub, SZ_BODY, on, 960, weight="400", anchor="middle"))
    bits.append(p.text(
        640, 490, (wrap_text(chap, 400, SZ_CAPTION, 1) or [chap])[0],
        SZ_CAPTION, on, anchor="middle",
    ))
    p.group("cover-hero", 120, 150, 1040, 420, "".join(bits))


def _paint_overview(p: Page, slide: dict) -> None:
    th = p.th
    p.loose.append(p.rect(0, 0, W, H, th["bg"], role="background"))
    _deco(p)
    _header(p, "课程概览", 0, {"title": slide.get("title") or "课程概览"})
    blocks: list[tuple[str, list[str]]] = slide.get("blocks") or []
    n = max(1, min(3, len(blocks)))
    gap = 24
    cw = (W - PAD * 2 - gap * (n - 1)) / n
    colors = [th["primary"], th["accent"], th["primary"]]
    for i, (title, items) in enumerate(blocks[:n]):
        x = PAD + i * (cw + gap)
        y, h = BODY_Y, BODY_BOTTOM - BODY_Y
        body = [_fit_line(p, x + 28, y + 48, title, SZ_SUB, th["primary"], cw - 56, max_lines=1)]
        rows: list[list[tuple[str, str, str]]] = []
        for it in items[:5]:
            rows.extend(wrap_rich("• " + it, cw - 64, SZ_BODY, 2))
        body.append(p.rich_lines(x + 28, y + 72, rows[:8], SZ_BODY, th["text"]))
        _card(p, f"ov-{i}", x, y, cw, h, th["card"], "".join(body), accent_top=colors[i])


def _paint_objectives(p: Page, slide: dict) -> None:
    th = p.th
    goals = _bullets(slide) or [_plain(slide.get("content") or "完成本课学习目标")]
    goals = goals[:4]
    gap, cols = 24, 2
    cw = (W - PAD * 2 - gap) / cols
    rows = (len(goals) + 1) // 2
    ch = max(140, (BODY_BOTTOM - BODY_Y - gap * (rows - 1)) / max(1, rows))
    for i, g in enumerate(goals):
        row, col = divmod(i, 2)
        x = PAD + col * (cw + gap)
        y = BODY_Y + row * (ch + gap)
        num = f"{i + 1:02d}"
        inner = [
            p.rect(x + 20, y + 28, 44, 44, th["primary"], rx=12),
            p.text(x + 42, y + 58, num, SZ_CAPTION, "#FFFFFF", "700", anchor="middle"),
        ]
        inner.append(p.rich_lines(x + 80, y + 24, wrap_rich(g, cw - 112, SZ_BODY, 3), SZ_BODY, th["text"]))
        _card(p, f"goal-{i}", x, y, cw, ch, th["card"], "".join(inner))


def _paint_knowledge(p: Page, slide: dict, img_xml: str, img_w: float) -> None:
    th = p.th
    left = PAD
    usable = W - PAD * 2 - (img_w + 24 if img_w else 0)
    x_bar, y, h = left, BODY_Y, BODY_BOTTOM - BODY_Y
    body_x = x_bar
    bs = _bullets(slide)
    inner_w = max(160.0, usable - 80)
    items: list[list[tuple[str, str, str]]] = []
    for b in bs[:5]:
        items.extend(wrap_rich("▸ " + b, inner_w, SZ_BODY, 2))
    raw_content = _src(slide.get("content") or "")
    if raw_content and not bs:
        items.extend(wrap_rich(raw_content, inner_w, SZ_BODY, 8))
    elif raw_content:
        items.extend(wrap_rich(raw_content, inner_w, SZ_BODY, 4))
    inner = p.rich_lines(body_x + 28, y + 24, items[:10], SZ_BODY, th["text"])
    _card(p, "know-body", body_x, y, usable - 16, h, th["card"], inner, accent_left=th["primary"])
    if img_xml:
        p.groups.append(img_xml)


def _paint_example(p: Page, slide: dict) -> None:
    th = p.th
    prompt = _src(str(slide.get("prompt") or ""))
    if not prompt:
        bs = _bullets(slide)
        prompt = "；".join(bs) if bs else _src(slide.get("title") or "例题")
    solution = _src(str(slide.get("solution") or slide.get("content") or ""))
    gap, cw = 24, (W - PAD * 2 - 24) / 2
    y, h = BODY_Y, BODY_BOTTOM - BODY_Y
    q_rows = wrap_rich(prompt, cw - 56, SZ_BODY, 8)
    a_rows = wrap_rich(solution, cw - 56, SZ_BODY, 8) if solution else [[("text", "（见课堂讲解）", "（见课堂讲解）")]]
    _card(
        p, "ex-q", PAD, y, cw, h, th["surface"],
        p.text(PAD + 28, y + 48, "题干", SZ_SUB, th["primary"], "700")
        + p.rich_lines(PAD + 28, y + 64, q_rows, SZ_BODY, th["text"]),
    )
    _card(
        p, "ex-a", PAD + cw + gap, y, cw, h, th["card"],
        p.text(PAD + cw + gap + 28, y + 48, "解析", SZ_SUB, th["primary"], "700")
        + p.rich_lines(PAD + cw + gap + 28, y + 64, a_rows, SZ_BODY, th["text"]),
        accent_left=th["accent"],
    )


def _image_el(p: Page, path_rel: str, x: float, y: float, w: float, h: float) -> str:
    return (
        f'<image id="{p.nid("img")}" href="{_esc(path_rel)}" x="{_r(x)}" y="{_r(y)}"'
        f' width="{_r(w)}" height="{_r(h)}" preserveAspectRatio="xMidYMid meet"/>'
    )


def _paint_stage_images(p: Page, refs: list[tuple[int, str]], x: float, y: float, w: float, h: float) -> None:
    th = p.th
    pad = 18
    bits = [p.rect(x, y, w, h, th["card"], rx=16)]
    n = min(2, len(refs))
    if n == 1:
        bits.append(_image_el(p, refs[0][1], x + pad, y + pad, w - 2 * pad, h - 2 * pad))
    else:
        gw = (w - 2 * pad - 16) / 2
        for i, (_, href) in enumerate(refs[:2]):
            bits.append(_image_el(p, href, x + pad + i * (gw + 16), y + pad, gw, h - 2 * pad))
    p.group("ia-stage", x, y, w, h, "".join(bits))


def _paint_stage_frame(p: Page, x: float, y: float, w: float, h: float) -> None:
    """没有配图时用画面框占位，不再堆说明文字。"""
    th = p.th
    cx, cy = x + w / 2, y + h / 2
    bits = [
        p.rect(x, y, w, h, th["card"], rx=16),
        p.rect(x + 20, y + 20, w - 40, h - 40, th["surface"], rx=12),
        p.circle(cx, cy, 42, th["primary"], 0.92),
    ]
    bits.append(
        f'<path id="{p.nid("p")}" d="M {_r(cx - 12)} {_r(cy - 18)} L {_r(cx - 12)} {_r(cy + 18)}'
        f' L {_r(cx + 20)} {_r(cy)} Z" fill="{th.get("on_cover") or "#FFFFFF"}"/>'
    )
    p.group("ia-stage", x, y, w, h, "".join(bits))


def _paint_interactive(
    p: Page, slide: dict, play_url: str = "",
    image_refs: list[tuple[int, str]] | None = None,
    shot_refs: list[tuple[int, str]] | None = None,
) -> None:
    from app.services.courseware_skill_svg import paint_skill_stage, skill_payload, skill_steps

    th = p.th
    refs = shot_refs or image_refs or []
    has_shot = bool(shot_refs)
    bs = _bullets(slide)
    content = _src(slide.get("content") or "")
    y = BODY_Y
    # 有图/截图时少占要点，把舞台留给画面
    if bs or content:
        rows: list[list[tuple[str, str, str]]] = []
        limit = 2 if refs else 3
        for b in bs[:limit]:
            rows.extend(wrap_rich("▸ " + b, W - PAD * 2 - 64, SZ_BODY, 2))
        if content and not refs:
            rows.extend(wrap_rich(content, W - PAD * 2 - 64, SZ_BODY, 3))
        shown = rows[: 3 if refs else 5]
        hh = min(120 if refs else 180, 36 + len(shown) * SZ_BODY * LEAD)
        inner = p.rich_lines(PAD + 28, y + 16, shown, SZ_BODY, th["text"])
        _card(p, "ia-points", PAD, y, W - PAD * 2, hh, th["card"], inner)
        y += hh + 16

    link_h = 44
    x, w = PAD, W - PAD * 2
    payload = skill_payload(slide)
    on = th.get("on_cover") or "#FFFFFF"
    label = "打开网页课件体验互动 →" if play_url else "请在网页课件中打开体验互动"
    link_inner = (
        p.rect(x, BODY_BOTTOM - link_h, w, link_h, p.gradient("iaBar", th["primary"], th["accent"], False))
        + p.text(x + 24, BODY_BOTTOM - 14, "动手做一做", SZ_CAPTION, on, "700")
        + _link_text(p, x + 200, BODY_BOTTOM - 14, label, play_url, SZ_CAPTION, on)
    )
    p.group("ia-link", x, BODY_BOTTOM - link_h, w, link_h, link_inner)

    stage_h = BODY_BOTTOM - link_h - 12 - y
    if has_shot and stage_h > 80:
        _paint_stage_images(p, shot_refs or refs, x, y, w, stage_h)
        return
    if payload and stage_h > 140:
        viz_w = w * 0.56
        paint_skill_stage(p, payload, x, y, viz_w, stage_h)
        steps = skill_steps(payload)[:3]
        sx = x + viz_w + 16
        sw = w - viz_w - 16
        sh = (stage_h - 12 * (len(steps) - 1)) / max(1, len(steps))
        for i, (title, detail) in enumerate(steps):
            yy = y + i * (sh + 12)
            inner = (
                p.rect(sx, yy, sw, sh, th["card"], rx=14)
                + p.text(sx + 20, yy + 32, title, SZ_CAPTION, th["primary"], "700")
                + p.rich_lines(sx + 20, yy + 40, wrap_rich(detail, sw - 40, SZ_BODY, 2), SZ_BODY, th["text"])
            )
            p.group(f"ia-step-{i}", sx, yy, sw, sh, inner)
        return

    if refs and stage_h > 80:
        _paint_stage_images(p, refs, x, y, w, stage_h)
        return
    _paint_stage_frame(p, x, y, w, stage_h)


def _paint_comparison(p: Page, slide: dict) -> None:
    th = p.th
    cols = _columns(slide)
    gap, cw = 24, (W - PAD * 2 - 24) / 2
    y, h = BODY_Y, BODY_BOTTOM - BODY_Y
    tops = [th["primary"], th["accent"]]
    for i, (title, items) in enumerate(cols[:2]):
        x = PAD + i * (cw + gap)
        rows: list[list[tuple[str, str, str]]] = []
        for it in items[:5]:
            rows.extend(wrap_rich("▸ " + it, cw - 56, SZ_BODY, 2))
        inner = (
            _fit_line(p, x + 28, y + 48, title or "对照", SZ_SUB, th["text"], cw - 56, max_lines=1)
            + p.rich_lines(x + 28, y + 72, rows[:8], SZ_BODY, th["text"])
        )
        _card(p, f"cmp-{i}", x, y, cw, h, th["card"], inner, accent_top=tops[i])


def _paint_process(p: Page, slide: dict) -> None:
    th = p.th
    steps = _steps(slide)[:4] or [("开始", "")]
    n = len(steps)
    avail = BODY_BOTTOM - BODY_Y
    gap = 22
    sh = max(100, (avail - gap * (n - 1)) / n)
    for i, (title, detail) in enumerate(steps):
        y = BODY_Y + i * (sh + gap)
        rail_x = PAD
        body_x = PAD + 60
        bw = W - body_x - PAD
        inner = [
            p.rect(rail_x, y + 12, 40, 40, th["primary"], rx=20),
            p.text(rail_x + 20, y + 40, str(i + 1), SZ_CAPTION, "#FFFFFF", "700", anchor="middle"),
        ]
        if i < n - 1:
            inner.append(p.rect(rail_x + 18, y + 56, 4, max(8, sh - 64), th["primary"], extra=' fill-opacity="0.25"'))
        rows = wrap_rich(title, bw - 48, SZ_BODY, 1)
        if detail:
            rows.extend(wrap_rich(detail, bw - 48, SZ_BODY, 1))
        inner.append(p.rect(body_x, y, bw, sh, th["card"], rx=16))
        inner.append(p.rich_lines(
            body_x + 24, y + 20, rows[:2], SZ_BODY, th["text"],
            leading=LEAD, weight="700" if not detail else "400",
        ))
        p.group(f"step-{i}", PAD, y, W - PAD * 2, sh, "".join(inner))


def _paint_summary(p: Page, slide: dict) -> None:
    th = p.th
    y = BODY_Y
    hero_h = 80
    _card(
        p, "sum-hero", PAD, y, W - PAD * 2, hero_h,
        p.gradient("sumHero", th["primary"], th["accent"], False),
        p.text(PAD + 32, y + 52, "今天带走这几件事", SZ_SUB, th.get("on_cover") or "#FFFFFF", "700"),
    )
    items = _bullets(slide) or ([_src(slide.get("content") or "")] if slide.get("content") else [])
    items = [it for it in items if it][:4]
    if not items:
        return
    y2 = y + hero_h + 20
    cols = 2 if len(items) > 1 else 1
    gap = 20
    cw = (W - PAD * 2 - gap * (cols - 1)) / cols
    rows = (len(items) + cols - 1) // cols
    ch = max(140, (BODY_BOTTOM - y2 - gap * (rows - 1)) / rows)
    for i, it in enumerate(items):
        row, col = divmod(i, cols)
        x = PAD + col * (cw + gap)
        yy = y2 + row * (ch + gap)
        inner = p.rich_lines(x + 24, yy + 24, wrap_rich(it, cw - 48, SZ_BODY, 3), SZ_BODY, th["text"], weight="600")
        _card(p, f"sum-{i}", x, yy, cw, ch, th["card"], inner)


def _paint_exercise(p: Page, slide: dict) -> None:
    th = p.th
    qs = _bullets(slide) or ([_src(slide.get("content") or "")] if slide.get("content") else ["完成本页练习"])
    qs = [q for q in qs if q][:4]
    n = len(qs)
    gap = 22
    eh = max(100, (BODY_BOTTOM - BODY_Y - gap * (n - 1)) / n)
    for i, q in enumerate(qs):
        y = BODY_Y + i * (eh + gap)
        x, w = PAD, W - PAD * 2
        inner = [
            p.rect(x + 20, y + 24, 40, 40, th["card"], rx=10,
                   extra=f' stroke="{th["primary"]}" stroke-width="2"'),
            p.text(x + 40, y + 52, str(i + 1), SZ_CAPTION, th["primary"], "700", anchor="middle"),
            p.rich_lines(x + 76, y + 22, wrap_rich(q, w - 112, SZ_BODY, 2), SZ_BODY, th["text"]),
        ]
        _card(p, f"exq-{i}", x, y, w, eh, th["card"], "".join(inner))


def _paint_homework(p: Page, slide: dict) -> None:
    th = p.th
    y = BODY_Y
    hero_h = 72
    _card(
        p, "hw-hero", PAD, y, W - PAD * 2, hero_h,
        p.gradient("hwHero", th["primary"], th["accent"], False),
        p.text(PAD + 32, y + 48, "分层任务：基础巩固 + 生活迁移", SZ_SUB, th.get("on_cover") or "#FFFFFF", "700"),
    )
    tasks = _bullets(slide) or ["完成课后巩固练习"]
    tasks = tasks[:4]
    y2 = y + hero_h + 20
    n = len(tasks)
    gap = 22
    thh = max(96, (BODY_BOTTOM - y2 - gap * (n - 1)) / n)
    for i, t in enumerate(tasks):
        yy = y2 + i * (thh + gap)
        x, w = PAD, W - PAD * 2
        inner = [
            p.rect(x + 24, yy + 28, 22, 22, th["card"], extra=f' stroke="{th["primary"]}" stroke-width="2"'),
            p.rich_lines(x + 64, yy + 16, wrap_rich(t, w - 100, SZ_BODY, 2), SZ_BODY, th["text"]),
        ]
        _card(p, f"hw-{i}", x, yy, w, thh, th["card"], "".join(inner))


def _image_group(p: Page, path_rel: str, x: float, y: float, w: float, h: float, idx: int) -> str:
    inner = (
        f'<image id="{p.nid("img")}" href="{_esc(path_rel)}" x="{_r(x)}" y="{_r(y)}"'
        f' width="{_r(w)}" height="{_r(h)}" preserveAspectRatio="xMidYMid meet"/>'
    )
    return f'<g id="media-{idx}" data-pptx-bounds="{_bounds(x, y, w, h)}">{inner}</g>'


def _write_images(images: dict[int, bytes], img_dir: Path, slide: dict) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    ids = slide.get("images") or []
    try:
        from PIL import Image
    except Exception:
        Image = None  # type: ignore
    for iid in ids[:2]:
        try:
            key = int(iid)
        except (TypeError, ValueError):
            continue
        data = images.get(key)
        if not data:
            continue
        name = f"img_{key}.png"
        dest = img_dir / name
        if not dest.exists():
            try:
                if Image is not None:
                    im = Image.open(io.BytesIO(data))
                    if im.mode not in ("RGB", "RGBA"):
                        im = im.convert("RGBA")
                    im.save(dest, format="PNG")
                else:
                    dest.write_bytes(data)
            except Exception:
                log.exception("skip courseware image %s", key)
                continue
        out.append((key, f"../images/{name}"))
    return out


def _usable_shot(data: bytes) -> bool:
    """丢掉近乎纯色的空截图，避免舞台铺一张灰图。"""
    if not data or len(data) < 1200:
        return False
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im = im.resize((48, 27))
        colors = im.getcolors(48 * 27) or []
        return len(colors) >= 8
    except Exception:
        return len(data) > 4000


def _write_shot(img_dir: Path, page_i: int, data: bytes) -> list[tuple[int, str]]:
    if not _usable_shot(data):
        return []
    name = f"shot_{page_i}.jpg"
    dest = img_dir / name
    dest.write_bytes(data)
    return [(-(1000 + page_i), f"../images/{name}")]


_DATA_IMG_RE = re.compile(
    r"src=['\"]data:image/(?:png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/=\s]+)['\"]",
    re.I,
)


def _write_html_images(img_dir: Path, slide: dict, page_i: int) -> list[tuple[int, str]]:
    """从互动 HTML 里抽出已内嵌的图片，当作舞台静帧。"""
    html = slide.get("html") or ""
    if not isinstance(html, str) or "data:image/" not in html.lower():
        return []
    out: list[tuple[int, str]] = []
    for n, raw in enumerate(_DATA_IMG_RE.findall(html)[:2], start=1):
        try:
            data = base64.b64decode(re.sub(r"\s+", "", raw), validate=False)
        except Exception:
            continue
        if len(data) < 80 or len(data) > 8_000_000:
            continue
        key = -(page_i * 10 + n)
        name = f"html_{page_i}_{n}.png"
        dest = img_dir / name
        if not dest.exists():
            try:
                dest.write_bytes(data)
            except Exception:
                continue
        out.append((key, f"../images/{name}"))
    return out


def render_slide_svg(
    slide: dict,
    theme_key: str | None,
    index: int,
    subject: str = "",
    chapter: str = "",
    image_refs: list[tuple[int, str]] | None = None,
    play_url: str = "",
) -> str:
    th = get_theme(theme_key)
    kind = slide.get("type")
    if kind == "_overview":
        p = Page(th, "section")
        _paint_overview(p, slide)
        return p.finish()
    kind = page_kind(kind)
    p = Page(th, "cover" if kind == "cover" else "content")

    if kind == "cover":
        _paint_cover(p, slide, subject, chapter)
        return p.finish()

    p.loose.append(p.rect(0, 0, W, H, th["bg"], role="background"))
    _deco(p)
    _header(p, page_label(slide.get("type")), index, slide)

    img_xml = ""
    img_w = 0.0
    refs = image_refs or []
    if refs and kind == "knowledge":
        img_w = 360
        ix, iy, iw, ih = W - PAD - img_w, BODY_Y, img_w, min(280, BODY_BOTTOM - BODY_Y)
        img_xml = _image_group(p, refs[0][1], ix, iy, iw, ih, refs[0][0])

    if kind == "objectives":
        _paint_objectives(p, slide)
    elif kind == "knowledge":
        _paint_knowledge(p, slide, img_xml, img_w)
        img_xml = ""
    elif kind == "example":
        _paint_example(p, slide)
    elif kind == "interactive":
        shot_refs = [r for r in refs if str(r[1]).startswith("../images/shot_")]
        _paint_interactive(p, slide, play_url, refs, shot_refs=shot_refs or None)
    elif kind == "comparison":
        _paint_comparison(p, slide)
    elif kind == "process":
        _paint_process(p, slide)
    elif kind == "summary":
        _paint_summary(p, slide)
    elif kind == "exercise":
        _paint_exercise(p, slide)
    elif kind == "homework":
        _paint_homework(p, slide)
    else:
        _paint_knowledge(p, slide, img_xml, img_w)
        img_xml = ""

    if img_xml:
        p.groups.append(img_xml)
    return p.finish()


def collect_pages(content: dict, title: str) -> tuple[list[dict], str]:
    """与网页演示同一页序：缺封面则补一张；meta 概览插在封面后。"""
    meta = content.get("meta") or {}
    slides = []
    for i, s in enumerate(content.get("slides") or []):
        if isinstance(s, dict):
            slides.append({**s, "_src_index": i})
    subject = str(meta.get("subject") or "")
    pages: list[dict] = []
    has_cover = any(page_kind(s.get("type")) == "cover" for s in slides)
    if not has_cover:
        pages.append({
            "type": "cover",
            "title": meta.get("title") or title or "教学课件",
            "subtitle": meta.get("duration") or "",
        })
    blocks: list[tuple[str, list[str]]] = []
    if meta.get("objectives"):
        blocks.append(("教学目标", [str(x) for x in meta["objectives"]]))
    if meta.get("key_points"):
        blocks.append(("教学重点", [str(x) for x in meta["key_points"]]))
    if meta.get("difficulties"):
        blocks.append(("教学难点", [str(x) for x in meta["difficulties"]]))
    overview = {"type": "_overview", "title": "课程概览", "blocks": blocks} if blocks else None

    inserted = False
    for s in slides:
        pages.append(s)
        if overview and not inserted and page_kind(s.get("type")) == "cover":
            pages.append(overview)
            inserted = True
    if overview and not inserted:
        insert_at = 1 if pages else 0
        pages.insert(insert_at, overview)
    if not pages:
        pages.append({"type": "cover", "title": title or "教学课件"})
    return pages, subject


def _write_spec_lock(project: Path, theme_key: str | None, page_count: int, title: str) -> None:
    th = get_theme(theme_key)
    rhythm = "\n".join(
        f"- P{i:02d}: {'breathing' if i == 1 else 'dense'}"
        for i in range(1, max(1, page_count) + 1)
    )
    (project / "spec_lock.md").write_text(
        f"""<!-- ppt-master-schema: spec-lock/v1 -->
# Execution Lock

## canvas
- viewBox: 0 0 1280 720
- format: ppt169

## communication
- primary_language: zh-Hans
- audience: 课堂师生
- objective: {title or "教学课件"}
- core_message: 按页呈现教学内容
- consumption_mode: presentation

## mode
- mode: instructional

## visual_style
- visual_style: soft-rounded

## colors
- bg: {th["bg"]}
- primary: {th["primary"]}
- accent: {th["accent"]}
- text: {th["text"]}

## typography
- font_family: Microsoft YaHei, PingFang SC, Arial, sans-serif
- title_family: Microsoft YaHei, PingFang SC, Arial, sans-serif
- body_family: Microsoft YaHei, PingFang SC, Arial, sans-serif
- kicker: 18
- caption: 20
- body: 24
- subtitle: 28
- title: 36
- display: 48

## icons
- library: none
- inventory: none

## page_rhythm
{rhythm}

## pptx_structure
- mode: flat

## forbidden
- `mask`, `<style>`, `class`, external CSS, `<foreignObject>`, `textPath`, `@font-face`, `<animate*>`, `<set>`, `<script>` / event attributes, `<iframe>`
- HTML named entities in text; write typography as raw Unicode and escape XML reserved characters
""",
        encoding="utf-8",
    )


def _click_groups(slide: dict, kind: str) -> list[str]:
    """本页点击揭示的顶层组（第一项已可见，从第二项起 on-click）。"""
    if kind == "example":
        return ["ex-a"]
    if kind == "objectives":
        n = min(4, len(_bullets(slide) or [1]))
        return [f"goal-{i}" for i in range(1, n)]
    if kind == "process":
        n = min(4, len(_steps(slide) or [1]))
        return [f"step-{i}" for i in range(1, n)]
    if kind == "exercise":
        qs = _bullets(slide) or ([_src(slide.get("content") or "")] if slide.get("content") else ["x"])
        n = min(4, max(1, len([q for q in qs if q])))
        return [f"exq-{i}" for i in range(1, n)]
    if kind == "homework":
        n = min(4, len(_bullets(slide) or ["x"]))
        return [f"hw-{i}" for i in range(1, n)]
    if kind == "summary":
        items = _bullets(slide) or ([_src(slide.get("content") or "")] if slide.get("content") else [])
        n = min(4, len([it for it in items if it]))
        return [f"sum-{i}" for i in range(1, n)]
    if kind == "comparison":
        return ["cmp-1"]
    if kind == "interactive":
        from app.services.courseware_skill_svg import skill_payload
        if slide.get("_has_shot"):
            return []
        if skill_payload(slide):
            return [f"ia-step-{i}" for i in range(3)]
        return []
    return []


def _write_animations(project: Path, pages: list[dict]) -> None:
    slides: dict[str, dict] = {}
    for i, slide in enumerate(pages, start=1):
        kind = slide.get("type") if slide.get("type") == "_overview" else page_kind(slide.get("type"))
        stem = f"{i:02d}_{kind}"
        groups = {}
        for order, gid in enumerate(_click_groups(slide, kind), start=1):
            groups[gid] = {
                "effect": "entrance_fade",
                "trigger": "on-click",
                "order": order,
                "duration": 0.4,
            }
        if groups:
            slides[stem] = {"groups": groups}
    payload = {
        "version": 1,
        "defaults": {
            "transition": {"effect": "fade", "duration": 0.45},
            "animation": {"effect": "none", "trigger": "on-click", "duration": 0.4},
        },
        "slides": slides,
    }
    (project / "animations.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def _safe_play_url(url: str | None) -> str:
    raw = (url or "").strip()
    if not raw or any(ord(c) < 0x21 or ord(c) == 0x7F for c in raw) or "\\" in raw:
        return ""
    if not (raw.startswith("http://") or raw.startswith("https://")):
        return ""
    return raw


def write_svg_project(
    project: Path,
    content: dict,
    title: str,
    images: dict[int, bytes],
    theme: str | None,
    play_url: str | None = None,
    shots: dict[int, bytes] | None = None,
) -> None:
    svg_dir = project / "svg_output"
    img_dir = project / "images"
    notes_dir = project / "notes"
    svg_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)
    notes_dir.mkdir(parents=True, exist_ok=True)
    (project / "validation").mkdir(parents=True, exist_ok=True)

    pages, subject = collect_pages(content, title)
    chapter = ""
    meta = content.get("meta") or {}
    if meta.get("duration"):
        chapter = str(meta.get("duration") or "")

    href = _safe_play_url(play_url)
    last_refs: list[tuple[int, str]] = []
    shot_map = shots or {}
    for i, slide in enumerate(pages, start=1):
        kind = slide.get("type") if slide.get("type") == "_overview" else page_kind(slide.get("type"))
        stem = f"{i:02d}_{kind}"
        own_refs = _write_images(images, img_dir, slide)
        refs = own_refs
        if kind == "interactive":
            src_i = slide.get("_src_index")
            shot = shot_map.get(src_i) if isinstance(src_i, int) else None
            if shot:
                refs = _write_shot(img_dir, i, shot)
                if refs:
                    slide["_has_shot"] = True
                else:
                    refs = own_refs or _write_html_images(img_dir, slide, i) or last_refs[:2]
            else:
                refs = own_refs or _write_html_images(img_dir, slide, i) or last_refs[:2]
        if own_refs:
            last_refs = own_refs
        svg = render_slide_svg(slide, theme, i, subject, chapter, refs, play_url=href)
        (svg_dir / f"{stem}.svg").write_text(svg, encoding="utf-8")
        notes = (slide.get("notes") or "").strip()
        if notes:
            (notes_dir / f"{stem}.md").write_text(_plain(notes), encoding="utf-8")

    _write_spec_lock(project, theme, len(pages), title)
    _write_animations(project, pages)


def _run_vendor(script_name: str, args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
    script = VENDOR / "scripts" / script_name
    if not script.is_file():
        raise FileNotFoundError(f"ppt-master 未安装：{script}")
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, timeout=timeout, cwd=str(VENDOR),
    )


def _vendor_err(proc: subprocess.CompletedProcess[str], limit: int = 3500) -> str:
    blob = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
    hits = [ln for ln in blob.splitlines() if "[ERROR]" in ln or "overflow" in ln.lower()]
    head = "\n".join(hits[:12])
    if head:
        return (head + "\n---\n" + blob[-2000:])[:limit]
    return blob[-limit:]


def convert_project_to_pptx(project: Path, out_path: Path) -> None:
    checker = _run_vendor(
        "svg_quality_checker.py",
        [str(project), "--stage", "final", "--json", "--format", "ppt169"],
        timeout=120,
    )
    export_args = [str(project), "-o", str(out_path), "-q", "-t", "fade"]
    if checker.returncode != 0:
        log.warning("SVG 质量检查未完全通过，改用兼容导出：%s", _vendor_err(checker, 1500))
        export_args.append("--enable-dangerous-nonconforming-svg-export")

    proc = _run_vendor("svg_to_pptx.py", export_args, timeout=180)
    if proc.returncode != 0 or not out_path.is_file():
        raise RuntimeError(f"svg_to_pptx 失败 ({proc.returncode}): {_vendor_err(proc)}")


def build_pptx_via_svg(
    content: dict, title: str, images: dict[int, bytes], theme: str | None = None,
    play_url: str | None = None, shots: dict[int, bytes] | None = None,
) -> bytes:
    with tempfile.TemporaryDirectory(prefix="cw-pptx-") as tmp:
        project = Path(tmp)
        out_path = project / "deck.pptx"
        write_svg_project(
            project, content, title, images, theme, play_url=play_url, shots=shots,
        )
        convert_project_to_pptx(project, out_path)
        return out_path.read_bytes()
