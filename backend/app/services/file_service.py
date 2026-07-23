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
                chapters = _parse_docx(file_bytes, tb.file_type)
            elif tb.file_type == "txt":
                chapters = _parse_txt(file_bytes)
            elif tb.file_type == "epub":
                chapters = _parse_epub(file_bytes)
            else:
                chapters = [{"title": tb.title, "content": "", "level": 1, "sort": 0}]

            # 按 level 构建父子树：栈中保存 (level, chapter_id)，
            # flush 后拿到自增 id 再回填 parent_id
            level_stack: list[tuple[int, int]] = []
            for i, ch in enumerate(chapters):
                lvl = ch.get("level", 1) or 1
                chapter = TextbookChapter(
                    textbook_id=tb.id,
                    title=ch["title"],
                    content=ch.get("content", ""),
                    page_start=ch.get("page_start"),
                    page_end=ch.get("page_end"),
                    sort_order=i,
                    level=lvl,
                )
                db.add(chapter)
                await db.flush()
                while level_stack and level_stack[-1][0] >= lvl:
                    level_stack.pop()
                chapter.parent_id = level_stack[-1][1] if level_stack else None
                level_stack.append((lvl, chapter.id))

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


_HEADING_RE = re.compile(
    r"^(第\s*[一二三四五六七八九十百零两\d]+\s*[章节篇课单元回讲]"
    r"|Chapter\s*\d+|Unit\s*\d+|Lesson\s*\d+"
    r"|[\d]+(?:\.\d+){0,3}[\s、.．]+\S)",
    re.IGNORECASE,
)


def _detect_pdf_headings_by_font(data: bytes) -> list[dict]:
    """基于字号启发式识别章节标题（适用于有文字层的 PDF）。

    思路：统计全书正文主字号（按字符数加权的众数），明显大于正文的短行判为标题，
    再按不同标题字号从大到小映射为 1~3 级。返回 [{title, level, page(0基)}]。
    """
    from collections import Counter
    try:
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        logger.warning("字号标题识别打开 PDF 失败：%s", e)
        return []

    size_counter: Counter = Counter()
    lines: list[dict] = []
    for pno in range(len(doc)):
        try:
            blocks = doc[pno].get_text("dict").get("blocks", [])
        except Exception:
            continue
        for block in blocks:
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(s.get("text", "") for s in spans).strip()
                if not text:
                    continue
                max_size = max((s.get("size", 0) or 0 for s in spans), default=0)
                flags = max((s.get("flags", 0) or 0 for s in spans), default=0)
                for s in spans:
                    size_counter[round(s.get("size", 0) or 0)] += len(s.get("text", "") or "")
                lines.append({
                    "page": pno, "text": text,
                    "size": round(max_size), "bold": bool(flags & 16),
                })

    if not lines or not size_counter:
        return []
    body = size_counter.most_common(1)[0][0] or 0

    cand: list[dict] = []
    for ln in lines:
        t = ln["text"]
        if len(t) > 40:
            continue
        if re.fullmatch(r"[\d\s.\-—_]+", t):  # 纯页码/数字/分隔线
            continue
        rx = bool(_HEADING_RE.match(t))
        big = ln["size"] >= body + 1 and ln["size"] >= body * 1.12
        # 以标点结尾且非编号标题的，多为正文句子，排除
        if t[-1] in "。！？，、,.;；：:" and not rx:
            continue
        if big or (rx and (ln["bold"] or ln["size"] >= body)):
            cand.append(ln)

    if len(cand) < 2:
        return []

    sizes = sorted({c["size"] for c in cand}, reverse=True)
    size_to_level = {s: min(i + 1, 3) for i, s in enumerate(sizes)}
    return [
        {"title": c["text"][:60], "level": size_to_level[c["size"]], "page": c["page"]}
        for c in cand
    ]


def _detect_headings_by_regex(page_texts: list[str]) -> list[dict]:
    """基于正则识别章节标题（适用于扫描/OCR 得到的纯文本，无字号信息）。"""
    section_re = re.compile(r"^第\s*[一二三四五六七八九十百零两\d]+\s*[节课讲]")
    result: list[dict] = []
    for pno, text in enumerate(page_texts):
        for line in (text or "").splitlines():
            line = line.strip()
            if not line or len(line) > 40:
                continue
            if _HEADING_RE.match(line):
                level = 2 if section_re.match(line) else 1
                result.append({"title": line[:60], "level": level, "page": pno})
    return result


def _build_chapters_from_headings(headings: list[dict], page_texts: list[str]) -> list[dict]:
    """依据识别出的标题序列切分正文，生成带层级/页码的章节列表。"""
    chapters: list[dict] = []
    n = len(headings)
    total = len(page_texts)
    for i, h in enumerate(headings):
        start_page = h["page"]
        end_page = headings[i + 1]["page"] if i + 1 < n else total - 1
        content = "\n".join(page_texts[start_page:min(end_page + 1, total)])
        # 起点对齐到本标题；终点截到下一标题，减少相邻章节内容重叠
        si = content.find(h["title"])
        if si > 0:
            content = content[si:]
        if i + 1 < n:
            ei = content.find(headings[i + 1]["title"], len(h["title"]))
            if ei > 0:
                content = content[:ei]
        chapters.append({
            "title": h["title"], "level": h["level"],
            "page_start": start_page + 1, "page_end": end_page + 1,
            "content": content[:5000], "sort": i,
        })
    return chapters


def _parse_pdf(parsed: dict, data: bytes, tb: Textbook) -> list[dict]:
    """基于 liteparse 解析结果构建章节。

    优先级：PDF 书签目录 → 字号启发式标题 → 正则标题(扫描件) → 逐页兜底。
    """
    page_texts = [pg["text"] for pg in parsed["pages"]]
    tb.total_pages = parsed["total_pages"] or len(page_texts)

    toc = _read_pdf_toc(data)
    chapters: list[dict] = []
    if toc:
        for i, (level, title, page) in enumerate(toc):
            end_page = toc[i + 1][2] - 1 if i + 1 < len(toc) else len(page_texts)
            content = ""
            # 读取本节全部页面（父节点若与子节同页起始可能为空，由生成时聚合子节补齐），
            # 累计够 5000 字即停止，避免长节被固定页数截断
            for p in range(page - 1, max(end_page, page)):
                if 0 <= p < len(page_texts):
                    content += page_texts[p] + "\n"
                    if len(content) >= 5000:
                        break
            chapters.append({
                "title": title, "level": level,
                "page_start": page, "page_end": end_page,
                "content": content[:5000],
                "sort": i,
            })
        return chapters

    # 无书签：启发式识别真实章节结构
    headings = _detect_pdf_headings_by_font(data)
    if len(headings) < 2:
        headings = _detect_headings_by_regex(page_texts)
    if len(headings) >= 2:
        logger.info("课本 %s 无书签，启发式识别到 %d 个章节标题", tb.id, len(headings))
        return _build_chapters_from_headings(headings, page_texts)

    # 兜底：逐页作为章节
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


def _parse_docx(data: bytes, ext: str = "docx") -> list[dict]:
    doc = _load_docx(data, ext)
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
        text = _extract_docx_text(file_bytes, file_type)
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


def _soffice_convert_to_docx(data: bytes, src_ext: str) -> bytes | None:
    """用 LibreOffice 把旧版 .doc（或格式与扩展名不符的文件）转换为 .docx，失败返回 None。"""
    import shutil, tempfile, subprocess, glob as _glob, os as _os
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        src = _os.path.join(tmp, f"input.{src_ext or 'doc'}")
        with open(src, "wb") as f:
            f.write(data)
        try:
            # 独立 profile 目录，避免并发转换时共享用户配置的文件锁冲突
            profile = _os.path.join(tmp, "lo_profile")
            subprocess.run(
                [
                    soffice, "--headless",
                    f"-env:UserInstallation=file://{profile}",
                    "--convert-to", "docx", "--outdir", tmp, src,
                ],
                check=True, capture_output=True, timeout=180,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("LibreOffice 转换 .doc 失败：%s", e)
            return None
        outs = _glob.glob(_os.path.join(tmp, "*.docx"))
        if not outs:
            return None
        with open(outs[0], "rb") as f:
            return f.read()


def _load_docx(data: bytes, ext: str = "docx"):
    """加载 Word 文档为 python-docx Document。
    旧版 .doc 或扩展名与实际格式不符时，先用 LibreOffice 转成 .docx。
    """
    from docx import Document
    if ext == "doc":
        converted = _soffice_convert_to_docx(data, "doc")
        if not converted:
            raise ValueError("旧版 .doc 文档无法解析，请转换为 .docx 或 PDF 后重新上传")
        data = converted
    try:
        return Document(io.BytesIO(data))
    except Exception:
        # 可能是被误标为 docx 的旧版 doc，尝试转换后重试
        converted = _soffice_convert_to_docx(data, ext or "doc")
        if converted:
            return Document(io.BytesIO(converted))
        raise


def _extract_docx_text(data: bytes, ext: str = "docx") -> str:
    doc = _load_docx(data, ext)
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


# ─── 试题分析：文件解析 ───────────────────────────────────────────

def _fallback_split_dicts(text: str) -> list[dict]:
    """无 LLM 或 LLM 失败时的兜底：按题号拆分为题目 dict 列表。"""
    parts = re.split(r"\n(?=\s*\d+\s*[.、．)])", text)
    items: list[dict] = []
    for p in parts:
        c = p.strip()
        if len(c) >= 4:
            items.append({"content": c})
    if not items and text.strip():
        items = [{"content": text.strip()}]
    return items


def _coerce_qtype(val) -> QuestionType:
    try:
        return QuestionType(val)
    except Exception:
        return QuestionType.short_answer


def _coerce_difficulty(val) -> DifficultyLevel:
    try:
        return DifficultyLevel(val)
    except Exception:
        return DifficultyLevel.medium


async def parse_analysis_file(set_id: int, task_id: str | None = None):
    """解析「试题分析」导入的文件，拆题（默认调用 LLM）并写入 analysis_questions。"""
    from app.models.question_analysis import AnalysisSet, AnalysisQuestion
    from app.services.ai_service import _publish_progress

    async with AsyncSessionLocal() as db:
        aset = (await db.execute(
            select(AnalysisSet).where(AnalysisSet.id == set_id)
        )).scalar_one_or_none()
        if not aset:
            return

        # 优先用 Celery 传入的 task_id（避免 API 回写前 worker 已启动导致进度丢通道）
        task_id = task_id or aset.task_id
        if task_id and not aset.task_id:
            aset.task_id = task_id
        aset.parse_status = ParseStatus.processing
        await db.commit()
        await _publish_progress(task_id, {"stage": "parse_start", "message": "正在提取试题内容..."})

        try:
            from app.services.ai_service import (
                _get_default_llm, parse_questions_from_text, parse_questions_from_image,
            )
            cfg = await _get_default_llm(aset.teacher_id, db)
            file_bytes = get_file_bytes(settings.MINIO_BUCKET_QUESTIONS, aset.source_file_path)
            ext = (aset.source_file_path or "").rsplit(".", 1)[-1].lower()

            parsed: list[dict] = []
            if ext in ("jpg", "jpeg", "png", "webp"):
                await _publish_progress(task_id, {"stage": "parse_llm", "message": "正在用 AI 识别图片中的题目..."})
                if cfg:
                    parsed = await parse_questions_from_image(cfg, file_bytes)
            else:
                if ext == "pdf":
                    text = _extract_pdf_text(file_bytes)
                elif ext in ("docx", "doc"):
                    text = _extract_docx_text(file_bytes, ext)
                elif ext == "txt":
                    text = file_bytes.decode("utf-8", errors="ignore")
                else:
                    text = ""
                if cfg and text.strip():
                    await _publish_progress(task_id, {"stage": "parse_llm", "message": "正在用 AI 拆分题目..."})
                    try:
                        parsed = await parse_questions_from_text(cfg, text)
                    except Exception:
                        parsed = []
                if not parsed and text.strip():
                    parsed = _fallback_split_dicts(text)

            seq = 0
            for item in parsed:
                content = (item.get("content") or "").strip()
                if not content:
                    continue
                seq += 1
                db.add(AnalysisQuestion(
                    set_id=aset.id,
                    teacher_id=aset.teacher_id,
                    seq=seq,
                    content=content[:8000],
                    options=item.get("options") or None,
                    answer=(item.get("answer") or None),
                    question_type=_coerce_qtype(item.get("question_type")),
                    difficulty=_coerce_difficulty(item.get("difficulty")),
                ))

            if seq == 0:
                aset.parse_error = "未能识别出有效题目，请检查文件内容或稍后重试。"
            aset.parse_status = ParseStatus.done
            await _publish_progress(task_id, {
                "stage": "parse_completed", "question_count": seq,
                "message": f"已拆出 {seq} 道题" if seq else "未识别到题目",
            })
        except Exception as e:
            aset.parse_status = ParseStatus.failed
            aset.parse_error = str(e)
            await _publish_progress(task_id, {"stage": "parse_error", "message": str(e)})
        finally:
            await db.commit()


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
        # 预收集学号，一次查出已有学生，避免逐行 N+1
        nos: list[str] = []
        for _, row in df.iterrows():
            no = str(row.get("student_no", "")).strip()
            if no:
                nos.append(no)
        student_map: dict[str, Student] = {}
        if nos:
            existing = (await db.execute(
                select(Student).where(
                    Student.teacher_id == teacher_id,
                    Student.student_no.in_(list(set(nos))),
                )
            )).scalars().all()
            student_map = {s.student_no: s for s in existing}

        for _, row in df.iterrows():
            student_no = str(row.get("student_no", "")).strip()
            if not student_no:
                continue
            student = student_map.get(student_no)
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
                student_map[student_no] = student

            db.add(ExamResult(
                student_id=student.id,
                teacher_id=teacher_id,
                subject_id=int(row.get("subject_id", 1)),
                exam_name=str(row.get("exam_name", "导入考试")),
                score=float(row.get("score", 0)),
                full_score=float(row.get("full_score", 100)),
                entry_method=EntryMethod.document,
            ))
        await db.commit()
