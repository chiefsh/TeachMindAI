"""课件导出服务：将课件内容导出为 PPTX / DOCX / PDF。"""
import io
import re
from typing import Any

# ---------- 通用工具 ----------

TYPE_LABELS = {
    "title": "封面",
    "objectives": "教学目标",
    "intro": "情境导入",
    "content": "新知讲解",
    "example": "例题精讲",
    "activity": "课堂活动",
    "interactive": "互动环节",
    "summary": "课堂小结",
    "homework": "课后作业",
    "board": "板书设计",
    "quiz": "随堂测验",
    "exercise": "练习",
}


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

def build_pptx(content: dict, title: str, images: dict[int, bytes]) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    meta = content.get("meta") or {}
    slides = content.get("slides") or []

    def add_text_slide(heading: str, lines: list[str], notes: str = "", img_ids: list[int] | None = None):
        slide = prs.slides.add_slide(blank)
        # 标题
        tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(12), Inches(1))
        p = tb.text_frame.paragraphs[0]
        p.text = heading
        p.font.size = Pt(30)
        p.font.bold = True
        p.font.color.rgb = RGBColor(0x4F, 0x46, 0xE5)

        has_img = bool(img_ids)
        body_w = Inches(7.2) if has_img else Inches(12)
        body = slide.shapes.add_textbox(Inches(0.6), Inches(1.6), body_w, Inches(5.4))
        tf = body.text_frame
        tf.word_wrap = True
        first = True
        for line in lines:
            para = tf.paragraphs[0] if first else tf.add_paragraph()
            para.text = line
            para.font.size = Pt(18)
            first = False

        if has_img:
            top = Inches(1.6)
            for iid in (img_ids or [])[:2]:
                data = images.get(iid)
                if not data:
                    continue
                try:
                    slide.shapes.add_picture(io.BytesIO(data), Inches(8.1), top, width=Inches(4.6))
                    top = Inches(top.inches + 2.8)
                except Exception:
                    pass

        if notes:
            slide.notes_slide.notes_text_frame.text = notes

    # 封面
    add_text_slide(
        meta.get("title") or title,
        [meta.get("duration", ""), "AI 智能教学课件"],
    )
    # 教学目标/重难点
    for h, items in _meta_blocks(meta):
        add_text_slide(h, [f"• {x}" for x in items])
    # 正文
    for s in slides:
        if s.get("type") == "title":
            continue
        label = TYPE_LABELS.get(s.get("type"), "")
        heading = s.get("title") or label or "幻灯片"
        if label and label not in heading:
            heading = f"【{label}】{heading}"
        add_text_slide(heading, _slide_lines(s), s.get("notes", ""), s.get("images"))

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ---------- DOCX ----------

def build_docx(content: dict, title: str, images: dict[int, bytes]) -> bytes:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor

    doc = Document()
    meta = content.get("meta") or {}
    slides = content.get("slides") or []

    h = doc.add_heading(meta.get("title") or title, level=0)
    if meta.get("duration"):
        doc.add_paragraph(f"课时：{meta['duration']}")

    for hd, items in _meta_blocks(meta):
        doc.add_heading(hd, level=2)
        for x in items:
            doc.add_paragraph(x, style="List Bullet")

    for s in slides:
        if s.get("type") == "title":
            continue
        label = TYPE_LABELS.get(s.get("type"), "")
        heading = s.get("title") or label or "幻灯片"
        if label and label not in heading:
            heading = f"【{label}】{heading}"
        doc.add_heading(heading, level=1)
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

def build_pdf(content: dict, title: str, images: dict[int, bytes]) -> bytes:
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

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("CnTitle", parent=styles["Title"], fontName=font_name, fontSize=22)
    h1 = ParagraphStyle("CnH1", parent=styles["Heading1"], fontName=font_name, fontSize=15,
                        textColor=colors.HexColor("#4F46E5"))
    h2 = ParagraphStyle("CnH2", parent=styles["Heading2"], fontName=font_name, fontSize=13)
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
        if s.get("type") == "title":
            continue
        label = TYPE_LABELS.get(s.get("type"), "")
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
    doc.build(story)
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

def _analysis_lines(analysis: dict | None) -> list[str]:
    """把结构化解析 dict 拉平成可读文本行（纯文字，不含图）。"""
    if not analysis:
        return []
    lines: list[str] = []
    if analysis.get("思路"):
        lines.append(f"【思路】{_strip_markdown(str(analysis['思路']))}")
    for i, s in enumerate(analysis.get("steps") or [], 1):
        title = _strip_markdown(str(s.get("title") or ""))
        detail = _strip_markdown(str(s.get("detail") or ""))
        formula = str(s.get("formula") or "").strip()
        seg = f"步骤{i}"
        if title:
            seg += f"：{title}"
        lines.append(seg)
        if detail:
            lines.append(f"    {detail}")
        if formula:
            lines.append(f"    公式：{formula}")
    kps = analysis.get("知识点") or []
    if kps:
        lines.append("【知识点】" + "、".join(_strip_markdown(str(k)) for k in kps))
    if analysis.get("易错点"):
        lines.append(f"【易错点】{_strip_markdown(str(analysis['易错点']))}")
    if analysis.get("答案"):
        lines.append(f"【答案】{_strip_markdown(str(analysis['答案']))}")
    return lines


def build_analysis_docx(name: str, questions: list[dict]) -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    h = doc.add_heading(name, level=0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for i, q in enumerate(questions, 1):
        p = doc.add_paragraph()
        p.add_run(f"{i}. {q.get('content', '')}")
        opts = q.get("options") or {}
        for k in sorted(opts.keys()):
            doc.add_paragraph(f"{k}. {opts[k]}", style="List Bullet")

    doc.add_page_break()
    doc.add_heading("答案与解析", level=1)
    for i, q in enumerate(questions, 1):
        doc.add_heading(f"第 {i} 题", level=2)
        if q.get("selected") and q.get("analysis_content"):
            for line in _analysis_lines(q.get("analysis_content")):
                doc.add_paragraph(line)
        else:
            doc.add_paragraph(f"答案：{q.get('answer') or '—'}")

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
    for i, q in enumerate(questions, 1):
        story.append(Paragraph(f"{i}. {esc(q.get('content', ''))}", body))
        opts = q.get("options") or {}
        for k in sorted(opts.keys()):
            story.append(Paragraph(f"{k}. {esc(str(opts[k]))}", opt))
        story.append(Spacer(1, 2 * mm))

    story.append(PageBreak())
    story.append(Paragraph("答案与解析", title_style))
    story.append(Spacer(1, 4 * mm))
    for i, q in enumerate(questions, 1):
        story.append(Paragraph(f"第 {i} 题", h2))
        if q.get("selected") and q.get("analysis_content"):
            for line in _analysis_lines(q.get("analysis_content")):
                story.append(Paragraph(esc(line), body))
        else:
            story.append(Paragraph(f"答案：{esc(q.get('answer') or '—')}", body))
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


def build_export(fmt: str, content: dict, title: str, images: dict[int, bytes]) -> tuple[bytes, str, str]:
    """返回 (bytes, media_type, filename_ext)"""
    if fmt == "pptx":
        return (
            build_pptx(content, title, images),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "pptx",
        )
    if fmt == "docx":
        return (
            build_docx(content, title, images),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        )
    if fmt == "pdf":
        return build_pdf(content, title, images), "application/pdf", "pdf"
    raise ValueError(f"不支持的导出格式：{fmt}")
