"""课件导出服务：将课件内容导出为 PPTX / DOCX / PDF。"""
import io
import re
from typing import Any

from app.services.courseware_theme import get_theme, page_kind, page_label, rgb

# ---------- 通用工具 ----------


def _strip_markdown(text: str) -> str:
    """把 markdown 粗略转为纯文本，便于在 PPT/Word/PDF 中展示。"""
    if not text:
        return ""
    text = re.sub(r"`{1,3}", "", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)
    return text.strip()


# ---------- LaTeX → 可读纯文本（Word/PDF 不渲染公式，退化为 Unicode 文本） ----------

_SUP = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
        "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻", "n": "ⁿ", "i": "ⁱ"}
_SUB = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
        "6": "₆", "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋"}
_LATEX_SYMBOLS = {
    r"\pi": "π", r"\times": "×", r"\div": "÷", r"\cdot": "·", r"\pm": "±", r"\mp": "∓",
    r"\leq": "≤", r"\geq": "≥", r"\neq": "≠", r"\approx": "≈", r"\equiv": "≡",
    r"\infty": "∞", r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\theta": "θ", r"\lambda": "λ", r"\mu": "μ", r"\sigma": "σ", r"\omega": "ω",
    r"\Delta": "Δ", r"\Omega": "Ω", r"\Sigma": "Σ", r"\circ": "°", r"\degree": "°",
    r"\angle": "∠", r"\parallel": "∥", r"\perp": "⊥", r"\Rightarrow": "⇒",
    r"\rightarrow": "→", r"\to": "→", r"\ldots": "…", r"\cdots": "⋯",
    r"\in": "∈", r"\cup": "∪", r"\cap": "∩", r"\subseteq": "⊆", r"\%": "%",
}


def _convert_math(tex: str) -> str:
    s = tex
    s = re.sub(r"\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"√(\1)", s)
    s = re.sub(r"\\(?:text|mathrm|mathbf|mathit|operatorname)\s*\{([^{}]*)\}", r"\1", s)
    for k, v in _LATEX_SYMBOLS.items():
        s = s.replace(k, v)

    def _script(mapping, body, prefix, wrap):
        if body and all(c in mapping for c in body):
            return "".join(mapping[c] for c in body)
        return f"{prefix}{wrap[0]}{body}{wrap[1]}"

    s = re.sub(r"\^\{([^{}]*)\}", lambda m: _script(_SUP, m.group(1), "^", ("(", ")")), s)
    s = re.sub(r"\^(\w)", lambda m: _script(_SUP, m.group(1), "^", ("", "")), s)
    s = re.sub(r"_\{([^{}]*)\}", lambda m: _script(_SUB, m.group(1), "_", ("", "")), s)
    s = re.sub(r"_(\w)", lambda m: _script(_SUB, m.group(1), "_", ("", "")), s)
    s = re.sub(r"\\left|\\right|\\quad|\\qquad|\\,|\\;|\\!|\\:", "", s)
    s = s.replace("\\ ", " ")
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)  # 剩余未知命令去掉反斜杠
    return s.replace("{", "").replace("}", "").strip()


def _latex_to_text(text: str) -> str:
    """把含 $...$ / $$...$$ 的 LaTeX 文本退化为可读 Unicode 文本。"""
    if not text:
        return ""
    text = re.sub(r"\$\$(.+?)\$\$", lambda m: _convert_math(m.group(1)), text, flags=re.DOTALL)
    text = re.sub(r"\$(.+?)\$", lambda m: _convert_math(m.group(1)), text, flags=re.DOTALL)
    return text


def _clean_text(text: str) -> str:
    """先去 markdown 再退化 LaTeX，得到适合 Word/PDF 的纯文本。"""
    return _latex_to_text(_strip_markdown(text or ""))


def _slide_lines(slide: dict) -> list[str]:
    """汇总一页幻灯片的可读文本行。"""
    lines: list[str] = []
    for b in slide.get("bullets") or []:
        if b:
            lines.append(f"• {b}")
    content = _strip_markdown(slide.get("content") or "")
    if content:
        lines.extend([l for l in content.splitlines() if l.strip()])
    if slide.get("html"):
        lines.append("（本页含互动动画，请在在线课件中查看）")
    return lines


def _meta_blocks(meta: dict) -> list[tuple[str, list[str]]]:
    blocks = []
    if meta.get("objectives"):
        blocks.append(("教学目标", list(meta["objectives"])))
    if meta.get("key_points"):
        blocks.append(("教学重点", list(meta["key_points"])))
    if meta.get("difficulties"):
        blocks.append(("教学难点", list(meta["difficulties"])))
    return blocks


# ---------- PPTX ----------

def build_pptx(content: dict, title: str, images: dict[int, bytes], theme: str | None = None) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN

    th = get_theme(theme)
    c_primary = RGBColor(*rgb(th["primary"]))
    c_accent = RGBColor(*rgb(th["accent"]))
    c_text = RGBColor(*rgb(th["text"]))
    c_muted = RGBColor(*rgb(th["muted"]))
    c_bg = RGBColor(*rgb(th["bg"]))
    c_card = RGBColor(*rgb(th["card"]))
    c_surface = RGBColor(*rgb(th["surface"]))
    c_cover_from = RGBColor(*rgb(th["cover_from"]))
    c_white = RGBColor(0xFF, 0xFF, 0xFF)
    cover_style = th.get("cover_style") or "diagonal"

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    W, H = prs.slide_width, prs.slide_height

    meta = content.get("meta") or {}
    slides = content.get("slides") or []

    def _fill(shape, color):
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        try:
            shape.shadow.inherit = False
        except Exception:
            pass

    def _bg(slide, color):
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = color

    def _deco(slide):
        style = th.get("deco_style") or "circles"
        if style in ("circles", "leaves"):
            oval = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(11.2), Inches(-0.6), Inches(3.2), Inches(3.2))
            _fill(oval, c_accent)
            oval = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(-1.0), Inches(5.8), Inches(2.6), Inches(2.6))
            _fill(oval, c_primary)
        elif style == "lines":
            _fill(slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.12), H), c_primary)
        else:
            _fill(slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(12.6), 0, Inches(0.74), H), c_surface)

    def _textbox(slide, l, t, w, h, text, size, color, bold=False):
        tb = slide.shapes.add_textbox(l, t, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        p.font.size = Pt(size)
        p.font.bold = bold
        p.font.color.rgb = color
        return tf

    def add_cover_slide(heading: str, lines: list[str]):
        slide = prs.slides.add_slide(blank)
        dark = cover_style in ("diagonal", "split")
        title_color = c_white if dark else c_text
        if cover_style == "split":
            _bg(slide, c_bg)
            _fill(slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(5.6), H), c_cover_from)
            tf = _textbox(slide, Inches(0.6), Inches(2.3), Inches(4.4), Inches(3.2), heading, 36, c_white, True)
            for line in [x for x in lines if x]:
                sub = tf.add_paragraph()
                sub.text = line
                sub.font.size = Pt(16)
                sub.font.color.rgb = c_white
            _textbox(slide, Inches(6.2), Inches(3.0), Inches(6.4), Inches(1.2), "智课星教学课件", 18, c_muted)
        elif cover_style == "ribbon":
            _bg(slide, c_bg)
            _deco(slide)
            _fill(slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.3), W, Inches(2.8),), c_cover_from)
            tf = _textbox(slide, Inches(0.8), Inches(2.6), Inches(11.6), Inches(2.2), heading, 40, c_white, True)
            for line in [x for x in lines if x]:
                sub = tf.add_paragraph()
                sub.text = line
                sub.font.size = Pt(16)
                sub.font.color.rgb = c_white
        elif cover_style == "panel":
            _bg(slide, c_bg)
            _deco(slide)
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.6), Inches(1.8), Inches(10.1), Inches(3.8))
            _fill(card, c_card)
            _fill(slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.6), Inches(1.8), Inches(10.1), Inches(0.12)), c_primary)
            tf = _textbox(slide, Inches(2.0), Inches(2.4), Inches(9.2), Inches(2.6), heading, 36, c_text, True)
            for line in [x for x in lines if x]:
                sub = tf.add_paragraph()
                sub.text = line
                sub.font.size = Pt(16)
                sub.font.color.rgb = c_muted
        elif cover_style == "minimal":
            _bg(slide, c_bg)
            _fill(slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(2.5), Inches(0.12), Inches(2.2)), c_primary)
            tf = _textbox(slide, Inches(1.2), Inches(2.5), Inches(11), Inches(2.6), heading, 40, c_text, True)
            for line in [x for x in lines if x]:
                sub = tf.add_paragraph()
                sub.text = line
                sub.font.size = Pt(16)
                sub.font.color.rgb = c_muted
        else:
            _bg(slide, c_cover_from)
            _fill(slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(10.8), Inches(-1.0), Inches(3.6), Inches(3.6)), c_accent)
            _fill(slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(6.9), W, Inches(0.6)), c_accent)
            tf = _textbox(slide, Inches(1.0), Inches(2.4), Inches(11.3), Inches(2.6), heading, 44, title_color, True)
            tf.paragraphs[0].alignment = PP_ALIGN.CENTER
            for line in [x for x in lines if x]:
                sub = tf.add_paragraph()
                sub.text = line
                sub.font.size = Pt(18)
                sub.font.color.rgb = title_color
                sub.alignment = PP_ALIGN.CENTER

    def add_text_slide(heading: str, lines: list[str], notes: str = "", img_ids: list[int] | None = None, kind: str = "knowledge"):
        slide = prs.slides.add_slide(blank)
        _bg(slide, c_bg)
        _deco(slide)
        _fill(slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, Inches(0.14)), c_primary)

        tb = slide.shapes.add_textbox(Inches(0.55), Inches(0.32), Inches(12), Inches(0.9))
        p = tb.text_frame.paragraphs[0]
        p.text = heading
        p.font.size = Pt(26)
        p.font.bold = True
        p.font.color.rgb = c_primary

        has_img = bool(img_ids)
        if kind in ("comparison", "example") and len(lines) >= 2 and not has_img:
            mid = max(1, len(lines) // 2)
            for i, chunk in enumerate((lines[:mid], lines[mid:])):
                left = Inches(0.55 + i * 6.3)
                box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, Inches(1.4), Inches(6.0), Inches(5.4))
                _fill(box, c_card if i else c_surface)
                _fill(slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE, left, Inches(1.4), Inches(6.0), Inches(0.12)
                ), c_accent if i else c_primary)
                body = slide.shapes.add_textbox(left + Inches(0.25), Inches(1.7), Inches(5.5), Inches(4.9))
                tf = body.text_frame
                tf.word_wrap = True
                first = True
                for line in chunk:
                    para = tf.paragraphs[0] if first else tf.add_paragraph()
                    para.text = line
                    para.font.size = Pt(16)
                    para.font.color.rgb = c_text
                    first = False
        elif kind in ("objectives", "summary", "exercise", "homework") and not has_img:
            cols = 2 if kind == "objectives" else 1
            for i, line in enumerate(lines[:8]):
                if cols == 2:
                    row, col = divmod(i, 2)
                    left = Inches(0.55 + col * 6.3)
                    top = Inches(1.4 + row * 1.4)
                    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, Inches(6.0), Inches(1.25))
                    _fill(box, c_card)
                    oval = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left + Inches(0.18), top + Inches(0.35), Inches(0.5), Inches(0.5))
                    _fill(oval, c_primary)
                    _textbox(slide, left + Inches(0.8), top + Inches(0.28), Inches(5.0), Inches(0.8), line.lstrip("• "), 16, c_text)
                else:
                    top = Inches(1.4 + i * 0.7)
                    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.55), top, Inches(12.2), Inches(0.62))
                    _fill(box, c_card)
                    _textbox(slide, Inches(0.8), top + Inches(0.08), Inches(11.7), Inches(0.5), line, 16, c_text)
        else:
            body_w = Inches(7.2) if has_img else Inches(12.1)
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.5), Inches(1.3), body_w + Inches(0.2), Inches(5.6))
            _fill(card, c_card)
            if kind == "knowledge":
                _fill(slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(1.3), Inches(0.12), Inches(5.6)), c_primary)
            body = slide.shapes.add_textbox(Inches(0.75), Inches(1.5), body_w - Inches(0.2), Inches(5.3))
            tf = body.text_frame
            tf.word_wrap = True
            first = True
            for line in lines:
                para = tf.paragraphs[0] if first else tf.add_paragraph()
                para.text = line
                para.font.size = Pt(17)
                para.font.color.rgb = c_text
                first = False
            if has_img:
                top = Inches(1.5)
                for iid in (img_ids or [])[:2]:
                    data = images.get(iid)
                    if not data:
                        continue
                    try:
                        slide.shapes.add_picture(io.BytesIO(data), Inches(8.15), top, width=Inches(4.5))
                        top = Inches(top.inches + 2.7)
                    except Exception:
                        pass

        if notes:
            slide.notes_slide.notes_text_frame.text = notes

    add_cover_slide(
        meta.get("title") or title,
        [meta.get("duration", ""), "智课星教学课件"],
    )
    for h, items in _meta_blocks(meta):
        add_text_slide(h, [f"• {x}" for x in items], kind="objectives")
    for s in slides:
        if page_kind(s.get("type")) == "cover":
            continue
        label = page_label(s.get("type"))
        heading = s.get("title") or label or "幻灯片"
        if label and label not in heading:
            heading = f"【{label}】{heading}"
        add_text_slide(heading, _slide_lines(s), s.get("notes", ""), s.get("images"), page_kind(s.get("type")))

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ---------- DOCX ----------

def build_docx(content: dict, title: str, images: dict[int, bytes], theme: str | None = None) -> bytes:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor

    from app.services.courseware_theme import get_theme, rgb

    th = get_theme(theme)
    c_primary = RGBColor(*rgb(th["primary"]))

    doc = Document()
    meta = content.get("meta") or {}
    slides = content.get("slides") or []

    h = doc.add_heading(meta.get("title") or title, level=0)
    for run in h.runs:
        run.font.color.rgb = c_primary
    if meta.get("duration"):
        doc.add_paragraph(f"课时：{meta['duration']}")

    for hd, items in _meta_blocks(meta):
        doc.add_heading(hd, level=2)
        for x in items:
            doc.add_paragraph(x, style="List Bullet")

    for s in slides:
        if page_kind(s.get("type")) == "cover":
            continue
        label = page_label(s.get("type"))
        heading = s.get("title") or label or "幻灯片"
        if label and label not in heading:
            heading = f"【{label}】{heading}"
        hd = doc.add_heading(heading, level=1)
        for run in hd.runs:
            run.font.color.rgb = c_primary
        if s.get("subtitle"):
            doc.add_paragraph(s["subtitle"])
        for b in s.get("bullets") or []:
            if b:
                doc.add_paragraph(b, style="List Bullet")
        content_text = _strip_markdown(s.get("content") or "")
        if content_text:
            doc.add_paragraph(content_text)
        for iid in s.get("images") or []:
            data = images.get(iid)
            if data:
                try:
                    doc.add_picture(io.BytesIO(data), width=Inches(5))
                except Exception:
                    pass
        if s.get("html"):
            doc.add_paragraph("（本页含互动动画，请在在线课件中查看）")
        if s.get("notes"):
            p = doc.add_paragraph()
            run = p.add_run(f"教师讲稿：{s['notes']}")
            run.italic = True
            run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------- PDF ----------

def build_pdf(content: dict, title: str, images: dict[int, bytes], theme: str | None = None) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, ListFlowable, ListItem,
    )

    # 注册内置中文字体（无需外部字体文件）
    font_name = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    except Exception:
        font_name = "Helvetica"

    from app.services.courseware_theme import get_theme

    th = get_theme(theme)
    c_primary = colors.HexColor(th["primary"])

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("CnTitle", parent=styles["Title"], fontName=font_name, fontSize=22,
                                 textColor=c_primary)
    h1 = ParagraphStyle("CnH1", parent=styles["Heading1"], fontName=font_name, fontSize=15,
                        textColor=c_primary)
    h2 = ParagraphStyle("CnH2", parent=styles["Heading2"], fontName=font_name, fontSize=13,
                        textColor=colors.HexColor(th["text"]))
    body = ParagraphStyle("CnBody", parent=styles["Normal"], fontName=font_name, fontSize=11,
                          leading=18, alignment=TA_LEFT)
    note = ParagraphStyle("CnNote", parent=body, textColor=colors.grey, fontSize=10)

    def esc(t: str) -> str:
        return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    meta = content.get("meta") or {}
    slides = content.get("slides") or []
    story: list[Any] = [Paragraph(esc(meta.get("title") or title), title_style), Spacer(1, 6 * mm)]
    if meta.get("duration"):
        story.append(Paragraph(f"课时：{esc(meta['duration'])}", body))
        story.append(Spacer(1, 4 * mm))

    for hd, items in _meta_blocks(meta):
        story.append(Paragraph(esc(hd), h2))
        story.append(ListFlowable(
            [ListItem(Paragraph(esc(x), body)) for x in items], bulletType="bullet"
        ))
        story.append(Spacer(1, 3 * mm))

    for s in slides:
        if page_kind(s.get("type")) == "cover":
            continue
        label = page_label(s.get("type"))
        heading = s.get("title") or label or "幻灯片"
        if label and label not in heading:
            heading = f"【{label}】{heading}"
        story.append(Paragraph(esc(heading), h1))
        if s.get("subtitle"):
            story.append(Paragraph(esc(s["subtitle"]), body))
        bullets = [b for b in (s.get("bullets") or []) if b]
        if bullets:
            story.append(ListFlowable(
                [ListItem(Paragraph(esc(b), body)) for b in bullets], bulletType="bullet"
            ))
        ctext = _strip_markdown(s.get("content") or "")
        for line in ctext.splitlines():
            if line.strip():
                story.append(Paragraph(esc(line), body))
        for iid in s.get("images") or []:
            data = images.get(iid)
            if data:
                try:
                    img = RLImage(io.BytesIO(data))
                    max_w = 120 * mm
                    if img.drawWidth > max_w:
                        ratio = max_w / img.drawWidth
                        img.drawWidth = max_w
                        img.drawHeight *= ratio
                    story.append(Spacer(1, 2 * mm))
                    story.append(img)
                except Exception:
                    pass
        if s.get("html"):
            story.append(Paragraph("（本页含互动动画，请在在线课件中查看）", note))
        if s.get("notes"):
            story.append(Paragraph(f"教师讲稿：{esc(s['notes'])}", note))
        story.append(Spacer(1, 5 * mm))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm)

    def _paint_bg(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(th["bg"]))
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.setFillColor(c_primary)
        canvas.rect(0, A4[1] - 8, A4[0], 8, fill=1, stroke=0)
        canvas.restoreState()

    doc.build(story, onFirstPage=_paint_bg, onLaterPages=_paint_bg)
    return buf.getvalue()


# ---------- 作业 / 试卷导出 ----------

def build_homework_docx(title: str, paper_type: str, questions: list[dict]) -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    h = doc.add_heading(title, level=0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    total = sum((q.get("score") or 0) for q in questions)
    type_label = "考试试卷" if paper_type == "exam" else "课后作业"
    meta = doc.add_paragraph(f"类型：{type_label}    题量：{len(questions)} 题    满分：{total} 分")
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info = doc.add_paragraph("姓名：____________    班级：____________    得分：____________")
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("")

    for i, q in enumerate(questions, 1):
        p = doc.add_paragraph()
        p.add_run(f"{i}. {q.get('content', '')}")
        score = q.get("score")
        if score:
            r = p.add_run(f"（{score} 分）")
            r.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
            r.font.size = Pt(9)
        opts = q.get("options") or {}
        if opts:
            for k in sorted(opts.keys()):
                doc.add_paragraph(f"{k}. {opts[k]}", style="List Bullet")
        else:
            doc.add_paragraph("答：")

    doc.add_page_break()
    doc.add_heading("参考答案", level=1)
    for i, q in enumerate(questions, 1):
        doc.add_paragraph(f"{i}. {q.get('answer') or '—'}")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_homework_pdf(title: str, paper_type: str, questions: list[dict]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

    font_name = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    except Exception:
        font_name = "Helvetica"

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("HTitle", parent=styles["Title"], fontName=font_name, fontSize=20, alignment=TA_CENTER)
    meta_style = ParagraphStyle("HMeta", parent=styles["Normal"], fontName=font_name, fontSize=11, alignment=TA_CENTER)
    body = ParagraphStyle("HBody", parent=styles["Normal"], fontName=font_name, fontSize=11, leading=18)
    opt = ParagraphStyle("HOpt", parent=body, leftIndent=16)

    def esc(t: str) -> str:
        return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    total = sum((q.get("score") or 0) for q in questions)
    type_label = "考试试卷" if paper_type == "exam" else "课后作业"
    story = [
        Paragraph(esc(title), title_style),
        Spacer(1, 4 * mm),
        Paragraph(f"类型：{type_label}　题量：{len(questions)} 题　满分：{total} 分", meta_style),
        Paragraph("姓名：____________　班级：____________　得分：____________", meta_style),
        Spacer(1, 6 * mm),
    ]
    for i, q in enumerate(questions, 1):
        score = q.get("score")
        suffix = f"（{score} 分）" if score else ""
        story.append(Paragraph(f"{i}. {esc(q.get('content', ''))} {suffix}", body))
        opts = q.get("options") or {}
        if opts:
            for k in sorted(opts.keys()):
                story.append(Paragraph(f"{k}. {esc(str(opts[k]))}", opt))
        else:
            story.append(Paragraph("答：", body))
        story.append(Spacer(1, 2 * mm))

    story.append(PageBreak())
    story.append(Paragraph("参考答案", title_style))
    story.append(Spacer(1, 4 * mm))
    for i, q in enumerate(questions, 1):
        story.append(Paragraph(f"{i}. {esc(q.get('answer') or '—')}", body))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=20 * mm, rightMargin=20 * mm)
    doc.build(story)
    return buf.getvalue()


# ---------- 试题分析导出（题目在前，答案解析按序在最后；不含图） ----------

def _analysis_blocks(analysis: dict | None) -> list[tuple[str, str]]:
    """把结构化解析 dict 拉平成 (标题, 正文) 段落，标题可为空表示普通行。"""
    if not analysis:
        return []
    blocks: list[tuple[str, str]] = []
    if analysis.get("思路"):
        blocks.append(("思路", _clean_text(str(analysis["思路"]))))
    for i, s in enumerate(analysis.get("steps") or [], 1):
        title = _clean_text(str(s.get("title") or ""))
        detail = _clean_text(str(s.get("detail") or ""))
        formula = _clean_text(str(s.get("formula") or ""))
        head = f"步骤 {i}" + (f"：{title}" if title else "")
        body_parts = [p for p in (detail, (f"公式：{formula}" if formula else "")) if p]
        blocks.append((head, "\n".join(body_parts)))
    kps = analysis.get("知识点") or []
    if kps:
        blocks.append(("知识点", "、".join(_clean_text(str(k)) for k in kps)))
    if analysis.get("易错点"):
        blocks.append(("易错点", _clean_text(str(analysis["易错点"]))))
    if analysis.get("答案"):
        blocks.append(("答案", _clean_text(str(analysis["答案"]))))
    return blocks


def _analysis_lines(analysis: dict | None) -> list[str]:
    """兼容旧接口：把解析拉平成纯文本行。"""
    lines: list[str] = []
    for head, body in _analysis_blocks(analysis):
        lines.append(f"【{head}】" if head in ("思路", "知识点", "易错点", "答案") else head)
        if body:
            for ln in body.splitlines():
                lines.append(f"    {ln}")
    return lines


def _set_docx_cjk_font(doc, font: str = "宋体") -> None:
    """把正文与标题的东亚字体设为中文字体，避免默认 MS Gothic 造成排版错乱。"""
    from docx.shared import Pt
    from docx.oxml.ns import qn
    for style_name in ("Normal", "Heading 1", "Heading 2", "Title"):
        try:
            st = doc.styles[style_name]
        except KeyError:
            continue
        st.font.name = "Times New Roman"
        rpr = st.element.get_or_add_rPr()
        rfonts = rpr.get_or_add_rFonts()
        rfonts.set(qn("w:eastAsia"), font)
    doc.styles["Normal"].font.size = Pt(11)


def build_analysis_docx(name: str, questions: list[dict]) -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    _set_docx_cjk_font(doc)

    h = doc.add_heading(name, level=0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_heading("试题", level=1)
    for i, q in enumerate(questions, 1):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(f"{i}. ")
        run.bold = True
        p.add_run(_clean_text(q.get("content", "")))
        opts = q.get("options") or {}
        for k in sorted(opts.keys()):
            op = doc.add_paragraph()
            op.paragraph_format.left_indent = Pt(18)
            op.paragraph_format.space_after = Pt(0)
            op.add_run(f"{k}. {_clean_text(str(opts[k]))}")

    doc.add_page_break()
    doc.add_heading("答案与解析", level=1)
    for i, q in enumerate(questions, 1):
        doc.add_heading(f"第 {i} 题", level=2)
        if q.get("selected") and q.get("analysis_content"):
            for head, body in _analysis_blocks(q.get("analysis_content")):
                hp = doc.add_paragraph()
                hp.paragraph_format.space_after = Pt(2)
                hp.add_run(head).bold = True
                if body:
                    for ln in body.splitlines():
                        bp = doc.add_paragraph()
                        bp.paragraph_format.left_indent = Pt(18)
                        bp.paragraph_format.space_after = Pt(0)
                        bp.add_run(ln)
        else:
            ap = doc.add_paragraph()
            ap.add_run("答案：").bold = True
            ap.add_run(_clean_text(q.get("answer") or "—"))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_analysis_pdf(name: str, questions: list[dict]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

    font_name = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    except Exception:
        font_name = "Helvetica"

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ATitle", parent=styles["Title"], fontName=font_name, fontSize=20, alignment=TA_CENTER)
    h2 = ParagraphStyle("AH2", parent=styles["Heading2"], fontName=font_name, fontSize=13)
    body = ParagraphStyle("ABody", parent=styles["Normal"], fontName=font_name, fontSize=11, leading=18)
    opt = ParagraphStyle("AOpt", parent=body, leftIndent=16)

    def esc(t: str) -> str:
        return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    story: list[Any] = [Paragraph(esc(name), title_style), Spacer(1, 6 * mm)]
    story.append(Paragraph("试题", h2))
    story.append(Spacer(1, 2 * mm))
    for i, q in enumerate(questions, 1):
        story.append(Paragraph(f"<b>{i}.</b> {esc(_clean_text(q.get('content', '')))}", body))
        opts = q.get("options") or {}
        for k in sorted(opts.keys()):
            story.append(Paragraph(f"{k}. {esc(_clean_text(str(opts[k])))}", opt))
        story.append(Spacer(1, 2 * mm))

    story.append(PageBreak())
    story.append(Paragraph("答案与解析", title_style))
    story.append(Spacer(1, 4 * mm))
    for i, q in enumerate(questions, 1):
        story.append(Paragraph(f"第 {i} 题", h2))
        if q.get("selected") and q.get("analysis_content"):
            for head, bodytext in _analysis_blocks(q.get("analysis_content")):
                story.append(Paragraph(f"<b>{esc(head)}</b>", body))
                for ln in (bodytext or "").splitlines():
                    story.append(Paragraph(esc(ln), opt))
        else:
            story.append(Paragraph(f"<b>答案：</b>{esc(_clean_text(q.get('answer') or '—'))}", body))
        story.append(Spacer(1, 3 * mm))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=20 * mm, rightMargin=20 * mm)
    doc.build(story)
    return buf.getvalue()


def build_analysis_export(fmt: str, name: str, questions: list[dict]) -> tuple[bytes, str, str]:
    if fmt in ("docx", "doc"):
        return (
            build_analysis_docx(name, questions),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        )
    if fmt == "pdf":
        return build_analysis_pdf(name, questions), "application/pdf", "pdf"
    raise ValueError(f"不支持的导出格式：{fmt}")


def build_homework_export(fmt: str, title: str, paper_type: str, questions: list[dict]) -> tuple[bytes, str, str]:
    if fmt == "docx":
        return (
            build_homework_docx(title, paper_type, questions),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        )
    if fmt == "pdf":
        return build_homework_pdf(title, paper_type, questions), "application/pdf", "pdf"
    raise ValueError(f"不支持的导出格式：{fmt}")


def build_export(
    fmt: str, content: dict, title: str, images: dict[int, bytes], theme: str | None = None,
) -> tuple[bytes, str, str]:
    """返回 (bytes, media_type, filename_ext)"""
    if fmt == "pptx":
        return (
            build_pptx(content, title, images, theme),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "pptx",
        )
    if fmt == "docx":
        return (
            build_docx(content, title, images, theme),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        )
    if fmt == "pdf":
        return build_pdf(content, title, images, theme), "application/pdf", "pdf"
    raise ValueError(f"不支持的导出格式：{fmt}")
