"""作业 / 试卷组卷：解析出题范围、按知识点筛题库、AI 补题、考试赋分。"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import AsyncSessionLocal
from app.models.courseware import Courseware
from app.models.homework import (
    HomeworkPaper, HomeworkQuestion, HomeworkType,
    HomeworkSourceType, QuestionSource,
)
from app.models.question import Question, QuestionType, DifficultyLevel, coerce_tags
from app.models.textbook import Textbook, TextbookChapter, ParseStatus

logger = logging.getLogger(__name__)

_CONTENT_CAP = 12000
_BANK_CANDIDATE_LIMIT = 200
_KP_MATCH_THRESHOLD = 0.78

_TYPE_ALIASES = {
    "single_choice": "single_choice",
    "multi_choice": "multi_choice",
    "fill_blank": "fill_blank",
    "true_false": "true_false",
    "short_answer": "short_answer",
    "essay": "essay",
    "calculation": "calculation",
    "单选": "single_choice",
    "单选题": "single_choice",
    "多选": "multi_choice",
    "多选题": "multi_choice",
    "填空": "fill_blank",
    "填空题": "fill_blank",
    "判断": "true_false",
    "判断题": "true_false",
    "简答": "short_answer",
    "简答题": "short_answer",
    "论述": "essay",
    "作文": "essay",
    "计算": "calculation",
    "计算题": "calculation",
}


def _coerce_qtype(raw) -> str:
    key = str(raw or "").strip()
    return _TYPE_ALIASES.get(key) or _TYPE_ALIASES.get(key.replace("题", "")) or "short_answer"


_DEFAULT_SCORES = {
    "single_choice": 5,
    "multi_choice": 6,
    "true_false": 4,
    "fill_blank": 5,
    "short_answer": 10,
    "calculation": 12,
    "essay": 15,
}

_ADJ_DIFF = {
    "easy": {"easy", "medium"},
    "medium": {"easy", "medium", "hard"},
    "hard": {"medium", "hard", "very_hard"},
    "very_hard": {"hard", "very_hard"},
}


def _norm(s: str) -> str:
    return re.sub(r"[\s\-_—·，。、；;：:（）()【】\[\]《》\"']+", "", (s or "")).lower()


def _enum_val(v) -> str:
    return getattr(v, "value", v) or ""


def _slide_text(slide: dict) -> str:
    parts: list[str] = []
    for key in ("title", "subtitle", "content", "prompt", "solution", "notes"):
        val = slide.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
        elif isinstance(val, list):
            parts.extend(str(x) for x in val if x)
    bullets = slide.get("bullets") or []
    if isinstance(bullets, list):
        parts.extend(str(b) for b in bullets if b)
    return "\n".join(parts)


def _kp_from_meta(content: dict | None) -> list[str]:
    if not isinstance(content, dict):
        return []
    raw = ((content.get("meta") or {}).get("knowledge_points")) or []
    names: list[str] = []
    for p in raw:
        if isinstance(p, dict):
            name = str(p.get("name") or p.get("title") or "").strip()
        else:
            name = str(p or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _uniq(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for x in items:
        s = (x or "").strip()
        if not s:
            continue
        key = _norm(s)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _match_kps(content: str, tags: list | None, aliases: list[str]) -> list[str]:
    """返回与本题命中的知识点原名（按 aliases 顺序）。"""
    blob = _norm(content or "")
    tag_n = [_norm(t) for t in (tags or []) if t]
    hit: list[str] = []
    for alias in aliases:
        na = _norm(alias)
        if len(na) < 2:
            continue
        tagged = any(
            na == t or (len(t) >= 2 and (na in t or t in na))
            for t in tag_n
        )
        in_text = na in blob
        if tagged or in_text:
            hit.append(alias)
    return hit


async def _points_from_graph(teacher_id: int, courseware_ids: list[int]) -> list[str]:
    try:
        from app.services import knowledge_graph_service as kg
        rows = await kg.points_by_courseware(teacher_id, courseware_ids)
    except Exception as e:  # noqa: BLE001
        logger.warning("图谱按课件取知识点失败：%s", e)
        return []
    names: list[str] = []
    for r in rows or []:
        n = (r.get("name") or "").strip()
        if n:
            names.append(n)
        for t in r.get("tags") or []:
            if t:
                names.append(str(t))
    return names


async def _expand_kp_aliases(
    teacher_id: int, subject_id: int | None, kp_names: list[str],
    embed_api_base: str | None, embed_api_key: str | None,
) -> list[str]:
    """用向量把课件/章节知识点扩成近义别名，缓解名称对不齐。"""
    aliases = list(kp_names)
    if not kp_names:
        return aliases
    try:
        from app.services.embedding_service import embed_text, embedding_enabled
        from app.core import qdrant_client as vec
        if not embedding_enabled():
            return _uniq(aliases)
        flt: dict = {"teacher_id": teacher_id}
        if subject_id:
            flt["subject_id"] = subject_id
        for name in kp_names[:12]:
            vector = await embed_text(
                name, api_base=embed_api_base, api_key=embed_api_key,
            )
            if not vector:
                continue
            hits = await vec.search_similar(vector, flt=flt, limit=3)
            for h in hits:
                if (h.get("score") or 0) < _KP_MATCH_THRESHOLD:
                    continue
                payload = h.get("payload") or {}
                extra = (payload.get("name") or "").strip()
                if extra:
                    aliases.append(extra)
    except Exception as e:  # noqa: BLE001
        logger.warning("知识点别名扩展失败：%s", e)
    return _uniq(aliases)


async def _extract_kp_names(cfg, title: str, content: str) -> list[str]:
    if not cfg or not (content or "").strip():
        return []
    from app.services.ai_service import _call_llm, _parse_json_object, _resp_content
    prompt = (
        "请从以下教学内容中列出核心知识点名称（3~8 个短词），不要超出材料范围。"
        "只输出 JSON：{\"knowledge_points\":[\"名称1\",\"名称2\"]}\n\n"
        f"课题：{title}\n\n内容：\n{content[:8000]}"
    )
    try:
        resp = await _call_llm(cfg, [{"role": "user", "content": prompt}], max_tokens=1024)
        obj = _parse_json_object(_resp_content(resp)) or {}
        raw = obj.get("knowledge_points") or []
        return _uniq([str(x) for x in raw])
    except Exception as e:  # noqa: BLE001
        logger.warning("组卷知识点抽取失败：%s", e)
        return []


async def _load_chapters(db, textbook_id: int, chapter_ids: list[int] | None) -> list[TextbookChapter]:
    rows = (await db.execute(
        select(TextbookChapter)
        .where(TextbookChapter.textbook_id == textbook_id)
        .order_by(TextbookChapter.sort_order, TextbookChapter.id)
    )).scalars().all()
    if not chapter_ids:
        return list(rows)
    wanted = set(int(x) for x in chapter_ids)
    by_parent: dict[int | None, list[TextbookChapter]] = defaultdict(list)
    for c in rows:
        by_parent[c.parent_id].append(c)

    def walk(pid: int):
        for child in by_parent.get(pid, []):
            if child.id not in wanted:
                wanted.add(child.id)
            walk(child.id)

    for cid in list(wanted):
        walk(cid)
    return [c for c in rows if c.id in wanted]


def _chapters_text(chapters: list[TextbookChapter]) -> tuple[str, list[str]]:
    chunks: list[str] = []
    titles: list[str] = []
    used = 0
    for ch in chapters:
        title = (ch.title or "").strip()
        if title:
            titles.append(title)
        body = (ch.content or "").strip()
        piece = f"## {title}\n{body}" if title else body
        if not piece.strip():
            continue
        remain = _CONTENT_CAP - used
        if remain <= 0:
            break
        chunks.append(piece[:remain])
        used += min(len(piece), remain)
    return "\n\n".join(chunks), titles


async def resolve_scope(db, paper: HomeworkPaper, cfg) -> dict:
    """解析出题范围 → 文本摘要、知识点、年级科目。"""
    teacher_id = paper.teacher_id
    source_type = _enum_val(paper.source_type) or HomeworkSourceType.courseware.value
    cw_ids = list(paper.courseware_ids or [])
    if not cw_ids and paper.courseware_id:
        cw_ids = [paper.courseware_id]

    kp_names: list[str] = []
    content = ""
    title = paper.title
    subject_id = grade_id = None
    textbook_id = paper.textbook_id

    if source_type == HomeworkSourceType.courseware.value or cw_ids:
        if not cw_ids:
            raise ValueError("未选择课件")
        coursewares = (await db.execute(
            select(Courseware).where(
                Courseware.id.in_(cw_ids),
                Courseware.teacher_id == teacher_id,
            )
        )).scalars().all()
        if not coursewares:
            raise ValueError("课件不存在")
        pieces: list[str] = []
        used = 0
        tb_ids: list[int] = []
        for cw in coursewares:
            title = title or cw.title
            kp_names.extend(_kp_from_meta(cw.content))
            if cw.textbook_id:
                tb_ids.append(cw.textbook_id)
            slides = []
            if isinstance(cw.content, dict):
                slides = cw.content.get("slides") or []
            body_parts = [_slide_text(s) for s in slides if isinstance(s, dict)]
            body = "\n".join(p for p in body_parts if p)
            block = f"课件《{cw.title}》\n{body}"
            remain = _CONTENT_CAP - used
            if remain <= 0:
                break
            pieces.append(block[:remain])
            used += min(len(block), remain)
        content = "\n\n".join(pieces)
        kp_names.extend(await _points_from_graph(teacher_id, [c.id for c in coursewares]))
        if tb_ids:
            textbook_id = textbook_id or tb_ids[0]
            tb = (await db.execute(
                select(Textbook).where(Textbook.id.in_(tb_ids))
            )).scalars().first()
            if tb:
                subject_id, grade_id = tb.subject_id, tb.grade_id

    elif source_type in (
        HomeworkSourceType.textbook.value, HomeworkSourceType.chapters.value,
    ):
        if not textbook_id:
            raise ValueError("未选择课本")
        tb = (await db.execute(
            select(Textbook).where(
                Textbook.id == textbook_id, Textbook.teacher_id == teacher_id,
            )
        )).scalar_one_or_none()
        if not tb:
            raise ValueError("课本不存在")
        subject_id, grade_id = tb.subject_id, tb.grade_id
        title = title or tb.title
        want_ids = paper.chapter_ids if source_type == HomeworkSourceType.chapters.value else None
        chapters = await _load_chapters(db, textbook_id, want_ids)
        content, titles = _chapters_text(chapters)
        kp_names.extend(titles)

    else:
        raise ValueError(f"不支持的出题范围：{source_type}")

    kp_names = _uniq(kp_names)
    if cfg and len(kp_names) < 2 and content.strip():
        extracted = await _extract_kp_names(cfg, title, content)
        kp_names = _uniq(kp_names + extracted)

    embed_base = embed_key = None
    try:
        from app.services.knowledge_extract_service import _embed_gateway
        embed_base, embed_key = await _embed_gateway(db, teacher_id)
    except Exception:  # noqa: BLE001
        pass
    aliases = await _expand_kp_aliases(
        teacher_id, subject_id, kp_names, embed_base, embed_key,
    )
    return {
        "title": title,
        "content": content,
        "kp_names": kp_names,
        "kp_aliases": aliases or kp_names,
        "subject_id": subject_id,
        "grade_id": grade_id,
        "teacher_id": teacher_id,
        "textbook_id": textbook_id,
    }


async def pick_from_bank(
    db,
    *,
    teacher_id: int,
    subject_id: int | None,
    grade_id: int | None,
    qtype: str,
    difficulty: str,
    needed: int,
    aliases: list[str],
    exclude_ids: set[int],
) -> list[Question]:
    if needed <= 0:
        return []
    try:
        qt = QuestionType(qtype)
    except Exception:
        return []
    stmt = select(Question).where(
        Question.teacher_id == teacher_id,
        Question.question_type == qt,
    )
    if subject_id:
        stmt = stmt.where(Question.subject_id == subject_id)
    if grade_id:
        stmt = stmt.where(Question.grade_id == grade_id)
    if exclude_ids:
        stmt = stmt.where(Question.id.not_in(exclude_ids))
    stmt = stmt.order_by(Question.created_at.desc()).limit(_BANK_CANDIDATE_LIMIT)
    candidates = (await db.execute(stmt)).scalars().all()
    if not candidates:
        return []

    allow_diff = _ADJ_DIFF.get(difficulty, {difficulty})
    scored: list[tuple[int, Question, list[str]]] = []
    for q in candidates:
        qdiff = _enum_val(q.difficulty)
        if qdiff not in allow_diff:
            continue
        hits = _match_kps(q.content or "", q.tags, aliases) if aliases else ["*"]
        if aliases and not hits:
            continue
        rank = 0
        if qdiff == difficulty:
            rank += 6
        else:
            rank += 2
        if q.tags:
            rank += 5 * min(len(hits), 3)
        elif aliases:
            rank += 2 * min(len(hits), 3)
        scored.append((rank, q, [] if hits == ["*"] else hits))

    scored.sort(key=lambda x: -x[0])
    picked: list[Question] = []
    for _, q, hits in scored[:needed]:
        picked.append(q)
        if hits and not q.tags:
            q.tags = coerce_tags(hits) or hits[:5]
            flag_modified(q, "tags")
    return picked


async def generate_by_ai(
    cfg, *, paper: HomeworkPaper, scope: dict, remain: dict[str, int],
) -> list[dict]:
    if not cfg or not any(v > 0 for v in remain.values()):
        return []
    from app.services.ai_service import _call_llm, _parse_json_object, _resp_content

    is_exam = _enum_val(paper.paper_type) == HomeworkType.exam.value
    difficulty_map = {"easy": "简单", "medium": "中等", "hard": "较难", "very_hard": "特难"}
    diff_label = difficulty_map.get(_enum_val(paper.difficulty), "中等")
    kind = "试卷" if is_exam else "作业"
    kp = scope.get("kp_names") or []
    kp_block = "、".join(kp) if kp else "（以材料为准）"
    score_rule = (
        ',"score": 5' if is_exam else ""
    )
    score_line = (
        "- 每题给出合理分值 score（整数）。\n" if is_exam else "- 不要输出 score 字段。\n"
    )
    remain_cfg = {k: v for k, v in remain.items() if v > 0}
    prompt = f"""请根据给定教学材料，出一份{diff_label}难度的{kind}。

【硬约束】
- 只考察以下知识点，不得超纲（前置知识可当背景，不能当新考点）：{kp_block}
- 题目必须能从材料中找到依据，不要引入材料未覆盖的概念。
- 严格按题型数量出题：{json.dumps(remain_cfg, ensure_ascii=False)}
{score_line}- question_type 取值：single_choice/multi_choice/fill_blank/true_false/short_answer/essay/calculation
- 选择题 options 为 {{"A":"...","B":"...","C":"...","D":"..."}}，非选择题 options 为 null。
- 只输出 JSON。

教学材料：
{(scope.get("content") or "")[:_CONTENT_CAP]}

输出格式：
{{
  "questions": [
    {{
      "type": "single_choice",
      "content": "题干",
      "options": {{"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}},
      "answer": "A",
      "explanation": "解析",
      "knowledge_points": ["所用知识点"]{score_rule}
    }}
  ]
}}"""
    try:
        resp = await _call_llm(
            cfg, [{"role": "user", "content": prompt}],
            max_tokens=max(cfg.max_tokens or 0, 4096),
        )
        obj = _parse_json_object(_resp_content(resp)) or {}
        questions = obj.get("questions") or []
    except Exception as e:  # noqa: BLE001
        logger.warning("作业 AI 出题失败：%s", e)
        return []

    aliases = scope.get("kp_aliases") or kp
    kept: list[dict] = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        content = str(q.get("content") or "").strip()
        if not content:
            continue
        declared = q.get("knowledge_points") or q.get("tags") or []
        declared = [str(x) for x in declared if x]
        if aliases:
            hits = _match_kps(content + " " + " ".join(declared), declared, aliases)
            if not hits and declared:
                # 模型声称的知识点完全不在范围内则丢弃
                continue
        qtype = _coerce_qtype(q.get("type") or q.get("question_type"))
        kept.append({
            "type": qtype,
            "content": content[:4000],
            "options": q.get("options") if isinstance(q.get("options"), dict) else None,
            "answer": q.get("answer"),
            "score": q.get("score"),
        })
    return kept


def _assign_score(is_exam: bool, qtype: str, raw) -> int | None:
    if not is_exam:
        return None
    try:
        if raw is not None:
            n = int(raw)
            if 1 <= n <= 50:
                return n
    except (TypeError, ValueError):
        pass
    return _DEFAULT_SCORES.get(qtype, 10)


async def generate_homework(paper_id: int):
    async with AsyncSessionLocal() as db:
        paper = (await db.execute(
            select(HomeworkPaper).where(HomeworkPaper.id == paper_id)
        )).scalar_one_or_none()
        if not paper:
            raise ValueError(f"作业 {paper_id} 不存在，稍后重试")

        paper.gen_status = ParseStatus.processing
        await db.commit()

        try:
            from app.services.ai_service import _get_default_llm
            cfg = await _get_default_llm(paper.teacher_id, db)
            scope = await resolve_scope(db, paper, cfg)

            q_source = _enum_val(paper.question_source) or QuestionSource.ai.value
            use_bank = q_source in (QuestionSource.bank.value, QuestionSource.mixed.value)
            use_ai = q_source in (QuestionSource.ai.value, QuestionSource.mixed.value, QuestionSource.bank.value)
            is_exam = _enum_val(paper.paper_type) == HomeworkType.exam.value

            config = {
                k: int(v) for k, v in (paper.question_config or {}).items()
                if int(v or 0) > 0
            }
            if not config:
                raise ValueError("题目数量不能为 0")

            difficulty = _enum_val(paper.difficulty) or "medium"
            remain = dict(config)
            bank_picked: dict[str, list[Question]] = {k: [] for k in remain}
            used_ids: set[int] = set()

            if use_bank:
                for qtype, n in list(remain.items()):
                    rows = await pick_from_bank(
                        db,
                        teacher_id=paper.teacher_id,
                        subject_id=scope.get("subject_id"),
                        grade_id=scope.get("grade_id"),
                        qtype=qtype,
                        difficulty=difficulty,
                        needed=n,
                        aliases=scope.get("kp_aliases") or [],
                        exclude_ids=used_ids,
                    )
                    bank_picked[qtype] = rows
                    used_ids.update(q.id for q in rows)
                    remain[qtype] = max(0, n - len(rows))

            ai_items: list[dict] = []
            need_ai = use_ai and any(v > 0 for v in remain.values())
            # bank 模式题量不够时回退 AI
            if need_ai:
                if not cfg:
                    if not any(bank_picked.values()):
                        paper.gen_status = ParseStatus.failed
                        paper.content = "未配置默认大模型，且题库没有匹配题目"
                        await db.commit()
                        return
                else:
                    ai_items = await generate_by_ai(
                        cfg, paper=paper, scope=scope, remain=remain,
                    )

            # 按题型配额组装，题库在前
            assembled: list[HomeworkQuestion] = []
            ai_by_type: dict[str, list[dict]] = defaultdict(list)
            for item in ai_items:
                ai_by_type[_coerce_qtype(item.get("type"))].append(item)

            order = 0
            for qtype, n in config.items():
                slot = 0
                for q in bank_picked.get(qtype) or []:
                    if slot >= n:
                        break
                    order += 1
                    slot += 1
                    assembled.append(HomeworkQuestion(
                        paper_id=paper.id,
                        question_id=q.id,
                        sort_order=order,
                        content=q.content,
                        options=q.options,
                        answer=q.answer,
                        score=_assign_score(is_exam, qtype, None),
                        source=QuestionSource.bank.value,
                    ))
                for item in ai_by_type.get(qtype) or []:
                    if slot >= n:
                        break
                    order += 1
                    slot += 1
                    assembled.append(HomeworkQuestion(
                        paper_id=paper.id,
                        sort_order=order,
                        content=item["content"],
                        options=item.get("options"),
                        answer=item.get("answer"),
                        score=_assign_score(is_exam, qtype, item.get("score")),
                        source=QuestionSource.ai.value,
                    ))

            if not assembled:
                paper.gen_status = ParseStatus.failed
                paper.content = "未能生成任何题目（题库无匹配且 AI 未返回有效题目）"
                await db.commit()
                return

            for hq in assembled:
                db.add(hq)

            paper.content = json.dumps({
                "kp_names": scope.get("kp_names") or [],
                "question_source": q_source,
                "bank": sum(1 for x in assembled if x.source == "bank"),
                "ai": sum(1 for x in assembled if x.source == "ai"),
            }, ensure_ascii=False)
            paper.gen_status = ParseStatus.done
        except Exception as e:
            logger.exception("作业 %s 生成失败：%s", paper.id, e)
            paper.gen_status = ParseStatus.failed
            paper.content = str(e)[:500]
        finally:
            await db.commit()
