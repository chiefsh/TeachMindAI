"""文件解析服务：课本 / 题库 / 成绩表"""
import io
import re
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.minio_client import get_file_bytes, upload_file
from app.core.config import settings
from app.models.textbook import Textbook, TextbookChapter, TextbookImage, ParseStatus
from app.models.question import Question, QuestionType, DifficultyLevel
import uuid

logger = logging.getLogger(__name__)


# ─── 课本解析 ──────────────────────────────────────────────────────

async def parse_textbook_file(textbook_id: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Textbook).where(Textbook.id == textbook_id))
        tb = result.scalar_one_or_none()
        if not tb:
            return

        tb.parse_status = ParseStatus.processing
        await db.commit()

        try:
            file_bytes = get_file_bytes("textbooks", tb.file_path)
            chapters: list[dict] = []
            parsed_pdf: dict | None = None

            if tb.file_type == "pdf":
                from app.services import liteparse_service
                parsed_pdf = liteparse_service.parse_pdf(file_bytes)
                chapters = _parse_pdf(parsed_pdf, file_bytes, tb)
            elif tb.file_type in ("docx", "doc"):
                chapters = _parse_docx(file_bytes)
            elif tb.file_type == "txt":
                chapters = _parse_txt(file_bytes)
            elif tb.file_type == "epub":
                chapters = _parse_epub(file_bytes)
            else:
                chapters = [{"title": tb.title, "content": "", "level": 1, "sort": 0}]

            for i, ch in enumerate(chapters):
                chapter = TextbookChapter(
                    textbook_id=tb.id,
                    parent_id=ch.get("parent_id"),
                    title=ch["title"],
                    content=ch.get("content", ""),
                    page_start=ch.get("page_start"),
                    page_end=ch.get("page_end"),
                    sort_order=i,
                    level=ch.get("level", 1),
                )
                db.add(chapter)

            # 提取课本插图（仅 PDF），供课件引用
            if tb.file_type == "pdf":
                pages_with_images: set[int] = set()
                try:
                    pages_with_images = _extract_and_store_pdf_images(db, tb, file_bytes)
                except Exception as e:
                    logger.warning("课本 %s 图片提取失败：%s", tb.id, e)
                # 对扫描/图多文字少且无内嵌图的页面，渲染整页截图入库
                if settings.TEXTBOOK_PAGE_SCREENSHOT and parsed_pdf:
                    try:
                        _store_pdf_page_screenshots(db, tb, file_bytes, parsed_pdf, pages_with_images)
                    except Exception as e:
                        logger.warning("课本 %s 整页截图失败：%s", tb.id, e)

            # 内容全空时给出明确提示（多为扫描版 PDF 且 OCR 不可用）
            has_content = any((ch.get("content") or "").strip() for ch in chapters)
            if not has_content:
                tb.parse_error = (
                    "未提取到文字内容：该文档可能为扫描件（无文字层）。"
                    "liteparse 已尝试 OCR，请确认运行环境安装了 tesseract 中文包 "
                    "(tesseract-ocr-chi-sim)，或正确设置 TESSDATA_PREFIX / OCR_TESSDATA_PATH。"
                )
                logger.warning("课本 %s 解析后内容为空：%s", tb.id, tb.parse_error)

            tb.parse_status = ParseStatus.done
        except Exception as e:
            tb.parse_status = ParseStatus.failed
            tb.parse_error = str(e)
        finally:
            await db.commit()


def _derive_title(text: str, fallback: str) -> str:
    """用正文首行作为章节标题，更直观。"""
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()  # 去掉 markdown 标题符号
        if line:
            return line[:60]
    return fallback


def _read_pdf_toc(data: bytes) -> list:
    """仅读取 PDF 书签目录（轻量），用于还原章节结构。失败返回空列表。"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=data, filetype="pdf")
        return doc.get_toc()  # [[level, title, page], ...]
    except Exception as e:
        logger.warning("读取 PDF 书签失败：%s", e)
        return []


def _parse_pdf(parsed: dict, data: bytes, tb: Textbook) -> list[dict]:
    """基于 liteparse 解析结果构建章节；章节结构沿用 PDF 书签目录。"""
    page_texts = [pg["text"] for pg in parsed["pages"]]
    tb.total_pages = parsed["total_pages"] or len(page_texts)

    toc = _read_pdf_toc(data)
    chapters: list[dict] = []
    if toc:
        for i, (level, title, page) in enumerate(toc):
            end_page = toc[i + 1][2] - 1 if i + 1 < len(toc) else len(page_texts)
            content = ""
            for p in range(page - 1, min(end_page, page + 5)):
                if 0 <= p < len(page_texts):
                    content += page_texts[p] + "\n"
            chapters.append({
                "title": title, "level": level,
                "page_start": page, "page_end": end_page,
                "content": content[:5000],
                "sort": i,
            })
    else:
        for i, text in enumerate(page_texts):
            chapters.append({
                "title": _derive_title(text, f"第 {i+1} 页"), "level": 1,
                "page_start": i + 1, "page_end": i + 1,
                "content": text[:3000],
                "sort": i,
            })
    return chapters


def _extract_and_store_pdf_images(db, tb: Textbook, data: bytes, max_images: int = 80) -> set[int]:
    """提取 PDF 内嵌图片，上传 MinIO 并写入 textbook_images 表。返回已配图的页码集合。"""
    import fitz
    doc = fitz.open(stream=data, filetype="pdf")
    seen: set[int] = set()
    pages_with_images: set[int] = set()
    count = 0
    for pno in range(len(doc)):
        for img in doc[pno].get_images(full=True):
            if count >= max_images:
                break
            xref = img[0]
            if xref in seen:
                continue
            seen.add(xref)
            try:
                base = doc.extract_image(xref)
            except Exception:
                continue
            w, h = base.get("width", 0), base.get("height", 0)
            # 过滤过小的装饰性图片（图标/线条）
            if w < 120 or h < 120:
                continue
            ext = base.get("ext", "png")
            image_bytes = base["image"]
            object_name = f"images/{tb.id}/{uuid.uuid4()}.{ext}"
            upload_file(
                settings.MINIO_BUCKET_TEXTBOOKS, object_name, image_bytes, f"image/{ext}"
            )
            db.add(TextbookImage(
                textbook_id=tb.id,
                page_number=pno + 1,
                object_name=object_name,
                content_type=f"image/{ext}",
                sort_order=count,
            ))
            pages_with_images.add(pno + 1)
            count += 1
    logger.info("课本 %s 提取内嵌图片 %d 张", tb.id, count)
    return pages_with_images


def _store_pdf_page_screenshots(
    db, tb: Textbook, data: bytes, parsed: dict, pages_with_images: set[int],
):
    """对扫描/图多文字少且无内嵌图的页面渲染整页截图入库，作为课件配图补充。"""
    from app.services import liteparse_service

    threshold = settings.TEXTBOOK_SCAN_TEXT_THRESHOLD
    max_shots = settings.TEXTBOOK_PAGE_SCREENSHOT_MAX

    candidates: list[int] = []
    for pg in parsed.get("pages") or []:
        num = pg.get("page_num")
        if not isinstance(num, int):
            continue
        if num in pages_with_images:
            continue  # 该页已有内嵌图，无需整页截图
        if len((pg.get("text") or "").strip()) >= threshold:
            continue  # 文字充足的普通页，不截图，避免冗余
        candidates.append(num)

    if not candidates:
        return
    candidates = candidates[:max_shots]

    shots = liteparse_service.screenshot_pdf(data, page_numbers=candidates)
    count = 0
    for num, png in shots:
        object_name = f"images/{tb.id}/page_{num}_{uuid.uuid4()}.png"
        upload_file(settings.MINIO_BUCKET_TEXTBOOKS, object_name, png, "image/png")
        db.add(TextbookImage(
            textbook_id=tb.id,
            page_number=num,
            object_name=object_name,
            content_type="image/png",
            sort_order=1000 + count,  # 排在内嵌图之后
        ))
        count += 1
    logger.info("课本 %s 整页截图 %d 张", tb.id, count)


def _parse_docx(data: bytes) -> list[dict]:
    from docx import Document
    doc = Document(io.BytesIO(data))
    chapters = []
    current: Optional[dict] = None
    for i, para in enumerate(doc.paragraphs):
        style = para.style.name
        text = para.text.strip()
        if not text:
            continue
        if style.startswith("Heading"):
            level = int(style[-1]) if style[-1].isdigit() else 1
            if current:
                chapters.append(current)
            current = {"title": text, "level": level, "content": "", "sort": len(chapters)}
        else:
            if current is None:
                current = {"title": "正文", "level": 1, "content": "", "sort": 0}
            current["content"] = (current["content"] + "\n" + text)[:5000]
    if current:
        chapters.append(current)
    return chapters


def _parse_txt(data: bytes) -> list[dict]:
    text = data.decode("utf-8", errors="ignore")
    lines = text.splitlines()
    chapters = []
    current: Optional[dict] = None
    heading_re = re.compile(r"^(第[一二三四五六七八九十百\d]+[章节课]|Chapter\s*\d+|\d+\.\s)", re.IGNORECASE)
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if heading_re.match(line) and len(line) < 60:
            if current:
                chapters.append(current)
            current = {"title": line, "level": 1, "content": "", "sort": len(chapters)}
        else:
            if current is None:
                current = {"title": "正文", "level": 1, "content": "", "sort": 0}
            current["content"] = (current["content"] + "\n" + line)[:5000]
    if current:
        chapters.append(current)
    return chapters or [{"title": "全文", "level": 1, "content": text[:5000], "sort": 0}]


def _parse_epub(data: bytes) -> list[dict]:
    import ebooklib
    from ebooklib import epub
    from html.parser import HTMLParser

    class _TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text = []
        def handle_data(self, d):
            self.text.append(d)
        def get_text(self):
            return " ".join(self.text)

    book = epub.read_epub(io.BytesIO(data))
    chapters = []
    for i, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        parser = _TextExtractor()
        parser.feed(item.get_content().decode("utf-8", errors="ignore"))
        text = parser.get_text().strip()
        if text:
            chapters.append({
                "title": item.get_name().split("/")[-1].replace(".xhtml", "").replace(".html", ""),
                "level": 1,
                "content": text[:5000],
                "sort": i,
            })
    return chapters


# ─── 题库解析 ─────────────────────────────────────────────────────

async def parse_question_file(
    teacher_id: int, subject_id: int, grade_id: int,
    bucket: str, object_name: str, file_type: str,
):
    file_bytes = get_file_bytes(bucket, object_name)

    if file_type in ("jpg", "jpeg", "png", "webp"):
        await _parse_question_image(teacher_id, subject_id, grade_id, file_bytes, object_name)
        return

    if file_type == "pdf":
        text = _extract_pdf_text(file_bytes)
    elif file_type in ("docx", "doc"):
        text = _extract_docx_text(file_bytes)
    elif file_type == "txt":
        text = file_bytes.decode("utf-8", errors="ignore")
    else:
        return

    questions = _split_questions(text, teacher_id, subject_id, grade_id, object_name)
    async with AsyncSessionLocal() as db:
        db.add_all(questions)
        await db.commit()


def _extract_pdf_text(data: bytes) -> str:
    from app.services import liteparse_service
    parsed = liteparse_service.parse_pdf(data)
    return parsed["full_text"] or parsed["markdown"]


def _extract_docx_text(data: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _split_questions(text: str, teacher_id: int, subject_id: int, grade_id: int, source: str) -> list[Question]:
    """简单按编号分割题目"""
    pattern = re.compile(r"(?:^|\n)(\d+)[.、．]\s+(.+?)(?=\n\d+[.、．]|\Z)", re.DOTALL)
    matches = pattern.findall(text)
    questions = []
    for _, content in matches[:200]:
        content = content.strip()
        if len(content) < 5:
            continue
        q = Question(
            teacher_id=teacher_id,
            subject_id=subject_id,
            grade_id=grade_id,
            question_type=QuestionType.short_answer,
            difficulty=DifficultyLevel.medium,
            content=content[:2000],
            source_file_path=source,
        )
        questions.append(q)
    return questions


async def _parse_question_image(teacher_id, subject_id, grade_id, data, source):
    """使用 AI Vision 识别图片中的题目"""
    from app.services.ai_service import do_ocr_grades
    import json
    async with AsyncSessionLocal() as db:
        from app.core.security import decrypt_api_key
        from app.models.llm_config import LLMConfig
        result = await db.execute(
            select(LLMConfig).where(
                LLMConfig.teacher_id == teacher_id,
                LLMConfig.is_active == True,
                LLMConfig.is_default == True,
            )
        )
        cfg = result.scalar_one_or_none()
        if not cfg:
            return

    import base64, litellm
    from app.services.ai_service import build_litellm_kwargs
    api_key = decrypt_api_key(cfg.api_key_encrypted) if cfg.api_key_encrypted else None
    b64 = base64.b64encode(data).decode()
    resp = await litellm.acompletion(
        messages=[{"role": "user", "content": [
            {"type": "text", "text": '请识别图片中的题目，以JSON返回：{"questions":[{"content":"题干","answer":"答案"}]}'},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
        max_tokens=2048,
        **build_litellm_kwargs(cfg, api_key),
    )
    try:
        raw = resp.choices[0].message.content
        parsed = json.loads(raw[raw.find("{"):raw.rfind("}")+1])
        items = parsed.get("questions", [])
        qs = [Question(
            teacher_id=teacher_id, subject_id=subject_id, grade_id=grade_id,
            question_type=QuestionType.short_answer,
            difficulty=DifficultyLevel.medium,
            content=q.get("content", "")[:2000],
            answer=q.get("answer"),
            source_file_path=source,
        ) for q in items if q.get("content")]
        async with AsyncSessionLocal() as db:
            db.add_all(qs)
            await db.commit()
    except Exception:
        pass


# ─── 成绩导入 ─────────────────────────────────────────────────────

async def import_grades_from_file(teacher_id: int, filename: str, file_data: bytes):
    """从 Excel 导入成绩（需配合前端约定列格式）"""
    import pandas as pd
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("xls", "xlsx"):
        df = pd.read_excel(io.BytesIO(file_data))
    else:
        df = pd.read_csv(io.BytesIO(file_data))

    # 期望列：student_no, name, exam_name, subject_id, score, full_score
    required = {"student_no", "name", "exam_name", "score"}
    if not required.issubset(set(df.columns)):
        return

    from app.models.student import Student, ExamResult, EntryMethod
    async with AsyncSessionLocal() as db:
        for _, row in df.iterrows():
            student_no = str(row.get("student_no", "")).strip()
            if not student_no:
                continue
            result = await db.execute(
                select(Student).where(Student.teacher_id == teacher_id, Student.student_no == student_no)
            )
            student = result.scalar_one_or_none()
            if not student:
                student = Student(
                    teacher_id=teacher_id,
                    student_no=student_no,
                    name=str(row.get("name", student_no)),
                    grade_id=int(row.get("grade_id", 1)),
                    class_name=str(row.get("class_name", "")),
                )
                db.add(student)
                await db.flush()

            er = ExamResult(
                student_id=student.id,
                teacher_id=teacher_id,
                subject_id=int(row.get("subject_id", 1)),
                exam_name=str(row.get("exam_name", "导入考试")),
                score=float(row.get("score", 0)),
                full_score=float(row.get("full_score", 100)),
                entry_method=EntryMethod.document,
            )
            db.add(er)
        await db.commit()
