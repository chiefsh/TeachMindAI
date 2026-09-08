"""题库去重入库：按教师 + 题型 + 题干/选项指纹复用已有题目。"""
from __future__ import annotations

import copy
import hashlib
import logging
import re

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.question import Question, QuestionType, DifficultyLevel, coerce_tags
from app.models.textbook import ParseStatus

logger = logging.getLogger(__name__)

_CONTENT_MAX = 4000

# 题干开头序号：15. / 15、 / 15． / （15） / 第15题.
# 要求分隔符后不是数字，避免把 18.5cm 误切成 5cm。
_STEM_NO_RE = re.compile(
    r"^\s*(?:[(（]\s*)?(?:第\s*)?\d{1,3}\s*(?:题\s*)?[.、．)）]\s*(?!\d)"
)


def strip_stem_number(content: str | None) -> str:
    """去掉题干开头的试卷题号，保留真正题面。"""
    text = (content or "").strip()
    if not text:
        return ""
    stripped = _STEM_NO_RE.sub("", text, count=1).strip()
    return stripped or text


def _norm(s: str) -> str:
    return re.sub(r"[\s\-_—·，。、；;：:（）()【】\[\]《》\"'‘’“”？?！!．.]+", "", (s or "")).lower()


def _option_text(val) -> str:
    if isinstance(val, dict):
        return str(val.get("text") or "")
    return str(val or "")


def _enum_val(v) -> str:
    return getattr(v, "value", v) or ""


def coerce_question_type(val) -> QuestionType:
    key = str(_enum_val(val) or "").strip()
    try:
        return QuestionType(key)
    except Exception:
        return QuestionType.short_answer


def coerce_difficulty(val) -> DifficultyLevel:
    key = str(_enum_val(val) or "").strip()
    try:
        return DifficultyLevel(key)
    except Exception:
        return DifficultyLevel.medium


def question_content_hash(content: str | None, options, question_type) -> str:
    opt_part = ""
    if isinstance(options, dict) and options:
        parts = []
        for k in sorted(str(x) for x in options.keys()):
            parts.append(f"{k}:{_norm(_option_text(options.get(k)))}")
        opt_part = "|".join(parts)
    raw = f"{_enum_val(question_type) or 'short_answer'}\n{_norm(strip_stem_number(content))}\n{opt_part}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _merge_into(existing: Question, incoming: Question) -> None:
    if not (existing.answer or "").strip() and (incoming.answer or "").strip():
        existing.answer = incoming.answer
    if not (existing.explanation or "").strip() and (incoming.explanation or "").strip():
        existing.explanation = incoming.explanation
    if not existing.options and incoming.options:
        existing.options = incoming.options
        flag_modified(existing, "options")
    if not existing.images and incoming.images:
        existing.images = incoming.images
        flag_modified(existing, "images")
    if not bank_has_analysis(existing) and bank_has_analysis(incoming):
        existing.analysis_content = incoming.analysis_content
        flag_modified(existing, "analysis_content")
        if incoming.analysis_html:
            existing.analysis_html = incoming.analysis_html
    merged = coerce_tags(list(existing.tags or []) + list(incoming.tags or []))
    if merged and merged != (existing.tags or []):
        existing.tags = merged
        flag_modified(existing, "tags")


def build_question(
    *,
    teacher_id: int,
    subject_id: int,
    grade_id: int,
    content: str,
    question_type=None,
    difficulty=None,
    options=None,
    images=None,
    answer=None,
    explanation=None,
    tags=None,
    source_file_path: str | None = None,
    analysis_content=None,
    analysis_html: str | None = None,
) -> Question | None:
    text_content = strip_stem_number(content)
    if not text_content:
        return None
    qtype = coerce_question_type(question_type)
    q = Question(
        teacher_id=teacher_id,
        subject_id=subject_id,
        grade_id=grade_id,
        question_type=qtype,
        difficulty=coerce_difficulty(difficulty),
        content=text_content[:_CONTENT_MAX],
        options=options if isinstance(options, dict) else None,
        images=images if isinstance(images, dict) else None,
        answer=(str(answer).strip() if answer else None) or None,
        explanation=(str(explanation).strip() if explanation else None) or None,
        tags=coerce_tags(tags),
        source_file_path=source_file_path,
        use_count=0,
        analysis_content=analysis_content if isinstance(analysis_content, dict) else None,
        analysis_html=analysis_html,
    )
    q.content_hash = question_content_hash(q.content, q.options, q.question_type)
    return q


async def upsert_question_models(
    db: AsyncSession, questions: list[Question],
) -> tuple[list[Question], int, int]:
    """按 content_hash 复用已有题。返回 (对应题目, 新录入数, 复用数)，不 commit。"""
    if not questions:
        return [], 0, 0

    teacher_id = questions[0].teacher_id
    for q in questions:
        if not q.content_hash:
            q.content_hash = question_content_hash(q.content, q.options, q.question_type)

    hashes = [q.content_hash for q in questions if q.content_hash]
    by_hash: dict[str, Question] = {}
    if hashes:
        rows = (await db.execute(
            select(Question).where(
                Question.teacher_id == teacher_id,
                Question.content_hash.in_(list(set(hashes))),
            )
        )).scalars().all()
        for row in rows:
            if row.content_hash and row.content_hash not in by_hash:
                by_hash[row.content_hash] = row

    resolved: list[Question] = []
    created = reused = 0
    for q in questions:
        hit = by_hash.get(q.content_hash or "")
        if hit:
            _merge_into(hit, q)
            resolved.append(hit)
            reused += 1
            continue
        if q.use_count is None:
            q.use_count = 0
        db.add(q)
        if q.content_hash:
            by_hash[q.content_hash] = q
        resolved.append(q)
        created += 1
    return resolved, created, reused


async def upsert_payloads(
    db: AsyncSession,
    *,
    teacher_id: int,
    subject_id: int | None,
    grade_id: int | None,
    items: list[dict],
) -> tuple[list[Question], int, int]:
    """把 dict 列表写入题库。缺年级/科目时只复用已有题，不新建。"""
    if not items:
        return [], 0, 0

    if subject_id and grade_id:
        models: list[Question] = []
        for item in items:
            q = build_question(
                teacher_id=teacher_id,
                subject_id=int(subject_id),
                grade_id=int(grade_id),
                content=str(item.get("content") or ""),
                question_type=item.get("question_type") or item.get("type"),
                difficulty=item.get("difficulty"),
                options=item.get("options"),
                images=item.get("images"),
                answer=item.get("answer"),
                explanation=item.get("explanation"),
                tags=item.get("tags") or item.get("knowledge_points") or item.get("知识点"),
                source_file_path=item.get("source_file_path"),
                analysis_content=item.get("analysis_content"),
                analysis_html=item.get("analysis_html"),
            )
            if q:
                models.append(q)
        return await upsert_question_models(db, models)

    resolved: list[Question] = []
    reused = 0
    for item in items:
        content = strip_stem_number(item.get("content") or "")
        if not content:
            continue
        qtype = coerce_question_type(item.get("question_type") or item.get("type"))
        digest = question_content_hash(content[:_CONTENT_MAX], item.get("options"), qtype)
        hit = (await db.execute(
            select(Question).where(
                Question.teacher_id == teacher_id,
                Question.content_hash == digest,
            )
        )).scalars().first()
        if hit:
            resolved.append(hit)
            reused += 1
    return resolved, 0, reused


def bank_has_analysis(q: Question | None) -> bool:
    ac = getattr(q, "analysis_content", None) if q else None
    return isinstance(ac, dict) and bool(ac)


def apply_analysis_from_bank(aq, bank: Question, source: str = "bank") -> bool:
    """把题库里的结构化解析套到试题分析题目上。"""
    if not bank_has_analysis(bank):
        return False
    aq.analysis_content = copy.deepcopy(bank.analysis_content)
    aq.analysis_html = bank.analysis_html
    aq.analysis_status = ParseStatus.done
    aq.selected = True
    aq.analysis_source = source
    if not (aq.answer or "").strip() and (bank.answer or "").strip():
        aq.answer = bank.answer
    return True


def write_analysis_to_question(
    bank: Question,
    analysis_content,
    analysis_html: str | None = None,
    *,
    overwrite: bool = True,
) -> None:
    """把试题分析的解析写回题库。overwrite=True 时覆盖已有解析。"""
    if not isinstance(analysis_content, dict) or not analysis_content:
        return
    if not overwrite and bank_has_analysis(bank):
        return
    bank.analysis_content = analysis_content
    flag_modified(bank, "analysis_content")
    if overwrite:
        bank.analysis_html = analysis_html
    elif analysis_html and not bank.analysis_html:
        bank.analysis_html = analysis_html
    from app.services.export_service import _analysis_lines
    expl = "\n".join(_analysis_lines(analysis_content)) or None
    if expl:
        bank.explanation = expl
    ans = analysis_content.get("答案")
    if ans and (overwrite or not (bank.answer or "").strip()):
        bank.answer = str(ans).strip() or bank.answer
    kps = analysis_content.get("知识点") or []
    merged = coerce_tags(list(bank.tags or []) + list(kps))
    if merged and merged != (bank.tags or []):
        bank.tags = merged
        flag_modified(bank, "tags")


def _digest_of(content, options, question_type) -> str:
    return question_content_hash((content or "")[:_CONTENT_MAX], options, question_type)


async def find_questions_by_hashes(
    db: AsyncSession, teacher_id: int, hashes: list[str],
) -> dict[str, Question]:
    uniq = [h for h in dict.fromkeys(hashes) if h]
    if not uniq:
        return {}
    rows = (await db.execute(
        select(Question).where(
            Question.teacher_id == teacher_id,
            Question.content_hash.in_(uniq),
        )
    )).scalars().all()
    out: dict[str, Question] = {}
    for row in rows:
        if row.content_hash and row.content_hash not in out:
            out[row.content_hash] = row
    return out


async def attach_bank_analysis(db: AsyncSession, teacher_id: int, aqs: list) -> int:
    """导入后：题库已有解析则直接套用。"""
    if not aqs:
        return 0
    hashes = [_digest_of(q.content, q.options, q.question_type) for q in aqs]
    by_hash = await find_questions_by_hashes(db, teacher_id, hashes)
    n = 0
    for q in aqs:
        bank = by_hash.get(_digest_of(q.content, q.options, q.question_type))
        if bank and apply_analysis_from_bank(q, bank):
            n += 1
    return n


async def upsert_and_write_analysis(
    db: AsyncSession,
    *,
    teacher_id: int,
    subject_id: int | None,
    grade_id: int | None,
    content: str,
    options,
    question_type,
    difficulty=None,
    answer=None,
    analysis_content=None,
    analysis_html: str | None = None,
    overwrite: bool = True,
) -> Question | None:
    digest = _digest_of(content, options, question_type)
    bank = (await db.execute(
        select(Question).where(
            Question.teacher_id == teacher_id,
            Question.content_hash == digest,
        )
    )).scalars().first()
    if not bank and subject_id and grade_id:
        bank = build_question(
            teacher_id=teacher_id,
            subject_id=int(subject_id),
            grade_id=int(grade_id),
            content=content,
            question_type=question_type,
            difficulty=difficulty,
            options=options,
            answer=answer,
        )
        if bank:
            db.add(bank)
            await db.flush()
    if not bank:
        return None
    write_analysis_to_question(bank, analysis_content, analysis_html, overwrite=overwrite)
    return bank


async def backfill_question_bank_meta() -> None:
    """给已有题目补指纹，并用现有作业/试卷行回填使用次数（仅补 0）。"""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        from app.models.question_analysis import AnalysisQuestion
        q_rows = (await db.execute(select(Question))).scalars().all()
        aq_rows = (await db.execute(select(AnalysisQuestion))).scalars().all()
        n_q = n_a = 0
        for q in q_rows:
            stripped = strip_stem_number(q.content)
            digest = question_content_hash(stripped, q.options, q.question_type)
            if stripped != (q.content or "") or q.content_hash != digest:
                q.content = stripped
                q.content_hash = digest
                n_q += 1
        for aq in aq_rows:
            stripped = strip_stem_number(aq.content)
            if stripped != (aq.content or ""):
                aq.content = stripped
                n_a += 1
        if n_q or n_a:
            await db.commit()
            logger.info("题干序号清理 题库 %s 道，试题分析 %s 道", n_q, n_a)

        try:
            await db.execute(text(
                "UPDATE questions q "
                "INNER JOIN ("
                "  SELECT question_id, COUNT(*) AS c FROM homework_questions "
                "  WHERE question_id IS NOT NULL GROUP BY question_id"
                ") t ON q.id = t.question_id "
                "SET q.use_count = t.c "
                "WHERE q.use_count = 0"
            ))
            await db.commit()
        except Exception:
            logger.exception("题库使用次数回填失败")
            await db.rollback()

        try:
            from app.models.question_analysis import AnalysisQuestion
            from sqlalchemy import or_
            banks = (await db.execute(
                select(Question).where(
                    Question.analysis_content.isnot(None),
                    or_(Question.analysis_html.is_(None), Question.analysis_html == ""),
                )
            )).scalars().all()
            if banks:
                teacher_ids = list({q.teacher_id for q in banks})
                aqs = (await db.execute(
                    select(AnalysisQuestion).where(
                        AnalysisQuestion.teacher_id.in_(teacher_ids),
                        AnalysisQuestion.analysis_html.isnot(None),
                    )
                )).scalars().all()
                aq_map: dict[tuple[int, str], str] = {}
                for aq in aqs:
                    html = (aq.analysis_html or "").strip()
                    if not html:
                        continue
                    digest = question_content_hash(
                        (aq.content or "")[:_CONTENT_MAX], aq.options, aq.question_type,
                    )
                    key = (aq.teacher_id, digest)
                    if key not in aq_map:
                        aq_map[key] = html
                n = 0
                for q in banks:
                    digest = q.content_hash or question_content_hash(q.content, q.options, q.question_type)
                    html = aq_map.get((q.teacher_id, digest))
                    if html:
                        q.analysis_html = html
                        n += 1
                if n:
                    await db.commit()
                    logger.info("题库图解回填 %s 道", n)
        except Exception:
            logger.exception("题库图解回填失败")
            await db.rollback()
