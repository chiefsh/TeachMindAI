"""知识点抽取与入图：从课本章节抽取知识点，或把课件已抽取的知识点回填到图谱。"""
import logging

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.textbook import TextbookChapter, Textbook
from app.models.education import Subject
from app.models.courseware import Courseware
from app.services import knowledge_graph_service as kg
from app.services.embedding_service import resolve_embedding, EmbeddingGateway

logger = logging.getLogger(__name__)


async def _subject_meta(db, subject_id: int | None):
    """返回 (subject_name, school_level_id)。"""
    if not subject_id:
        return "", None
    sub = (await db.execute(select(Subject).where(Subject.id == subject_id))).scalar_one_or_none()
    if not sub:
        return "", None
    return sub.name, sub.school_level_id


async def _embed_gw(db, teacher_id: int) -> EmbeddingGateway | None:
    try:
        return await resolve_embedding(db, teacher_id)
    except Exception:  # noqa: BLE001
        return None


async def _store_points(
    points: list[dict], *, teacher_id: int, subject_id: int | None,
    subject_name: str, school_level_id: int | None, grade_id: int | None,
    source: str, courseware_id: int | None = None,
    embedding: EmbeddingGateway | None = None,
) -> list[str]:
    """把规范化后的知识点写入图谱，串联为顺序前置链，返回节点 id 列表。"""
    ids: list[str] = []
    for p in points:
        desc_parts = [p.get("plain_explanation") or ""]
        if p.get("life_example"):
            desc_parts.append(f"例：{p['life_example']}")
        res = await kg.upsert_knowledge_point(
            teacher_id=teacher_id,
            name=p.get("name") or "",
            subject_id=subject_id,
            subject_name=subject_name,
            school_level_id=school_level_id,
            grade_id=grade_id,
            description="；".join([d for d in desc_parts if d])[:1000],
            difficulty=3,
            tags=(p.get("core_concepts") or [])[:5],
            source=source,
            embed_model=embedding.model if embedding else None,
            embed_api_base=embedding.api_base if embedding else None,
            embed_api_key=embedding.api_key if embedding else None,
        )
        if res:
            ids.append(res["id"])
            if courseware_id is not None:
                await kg.link_source(res["id"], courseware_id=courseware_id)

    # 顺序前置链（弱关系）：前一个知识点是后一个的前置
    for a, b in zip(ids, ids[1:]):
        if a != b:
            try:
                await kg.add_relation(
                    from_id=a, to_id=b, rel_type="prerequisite",
                    weight=0.4, cross_subject=False, status="approved", source="sequence",
                )
            except Exception:  # noqa: BLE001
                pass
    return ids


async def extract_and_store_for_chapter(chapter_id: int, teacher_id: int) -> dict:
    """对单个章节用 LLM 抽取知识点并入图。"""
    from app.services.ai_service import (
        _get_default_llm, _extract_knowledge_points, _resolve_subject_prompt,
    )
    async with AsyncSessionLocal() as db:
        ch = (await db.execute(
            select(TextbookChapter).where(TextbookChapter.id == chapter_id)
        )).scalar_one_or_none()
        if not ch:
            return {"stored": 0, "error": "章节不存在"}
        tb = (await db.execute(
            select(Textbook).where(Textbook.id == ch.textbook_id)
        )).scalar_one_or_none()
        if not tb:
            return {"stored": 0, "error": "课本不存在"}

        cfg = await _get_default_llm(teacher_id, db)
        if not cfg:
            return {"stored": 0, "error": "未配置大模型"}

        subject_name, school_level_id = await _subject_meta(db, tb.subject_id)
        _, subject_block, _ = await _resolve_subject_prompt(db, teacher_id, tb.subject_id)

        # 复用课件的知识点抽取逻辑：构造轻量 cw 承载 title/custom_prompt
        class _CW:
            title = ch.title
            custom_prompt = None
        content = f"## {ch.title}\n{ch.content or ''}"
        if not (ch.content or "").strip():
            return {"stored": 0, "error": "章节无正文内容"}
        points = await _extract_knowledge_points(cfg, _CW(), content, subject_name, subject_block)
        gw = await _embed_gw(db, teacher_id)
        ids = await _store_points(
            points, teacher_id=teacher_id, subject_id=tb.subject_id,
            subject_name=subject_name, school_level_id=school_level_id,
            grade_id=tb.grade_id, source="chapter",
            embedding=gw,
        )
        return {"stored": len(ids), "point_ids": ids, "names": [p["name"] for p in points]}


async def extract_and_store_for_textbook(textbook_id: int, teacher_id: int, max_chapters: int = 30) -> dict:
    """遍历课本章节抽取知识点入图（限制章节数，控制 LLM 成本）。"""
    async with AsyncSessionLocal() as db:
        chapters = (await db.execute(
            select(TextbookChapter.id)
            .where(TextbookChapter.textbook_id == textbook_id)
            .order_by(TextbookChapter.sort_order)
            .limit(max_chapters)
        )).scalars().all()
    total = 0
    for cid in chapters:
        try:
            r = await extract_and_store_for_chapter(cid, teacher_id)
            total += r.get("stored", 0)
        except Exception as e:  # noqa: BLE001
            logger.warning("章节 %s 抽取失败：%s", cid, e)
    return {"chapters": len(chapters), "stored": total}


async def persist_courseware_points(courseware_id: int) -> dict:
    """把课件生成阶段已抽取的知识点（存于 content.meta.knowledge_points）回填到图谱。"""
    async with AsyncSessionLocal() as db:
        cw = (await db.execute(
            select(Courseware).where(Courseware.id == courseware_id)
        )).scalar_one_or_none()
        if not cw or not isinstance(cw.content, dict):
            return {"stored": 0}
        points = ((cw.content.get("meta") or {}).get("knowledge_points")) or []
        if not points:
            return {"stored": 0}

        subject_id = grade_id = None
        subject_name, school_level_id = "", None
        if cw.textbook_id:
            tb = (await db.execute(
                select(Textbook).where(Textbook.id == cw.textbook_id)
            )).scalar_one_or_none()
            if tb:
                subject_id, grade_id = tb.subject_id, tb.grade_id
                subject_name, school_level_id = await _subject_meta(db, tb.subject_id)
        teacher_id = cw.teacher_id
        gw = await _embed_gw(db, teacher_id)

    ids = await _store_points(
        points, teacher_id=teacher_id, subject_id=subject_id,
        subject_name=subject_name, school_level_id=school_level_id,
        grade_id=grade_id, source="courseware", courseware_id=courseware_id,
        embedding=gw,
    )
    return {"stored": len(ids), "point_ids": ids}


async def persist_analysis_points(set_id: int) -> dict:
    """把试题分析产出的知识点（analysis_content.知识点）沉淀进图谱，并关联到题目。

    - 每道已解析题目的知识点入图，link_source(question_id)。
    - 同一道题内的知识点之间建立弱「相关」关系（共现），便于串联。
    """
    from app.models.question_analysis import AnalysisSet, AnalysisQuestion
    async with AsyncSessionLocal() as db:
        aset = (await db.execute(
            select(AnalysisSet).where(AnalysisSet.id == set_id)
        )).scalar_one_or_none()
        if not aset:
            return {"stored": 0}
        teacher_id = aset.teacher_id
        subject_id = aset.subject_id
        grade_id = aset.grade_id
        subject_name, school_level_id = await _subject_meta(db, subject_id)
        gw = await _embed_gw(db, teacher_id)
        rows = (await db.execute(
            select(AnalysisQuestion).where(AnalysisQuestion.set_id == set_id)
        )).scalars().all()
        # 快照，避免在图/向量异步调用期间持有会话
        items = [
            (q.id, (q.analysis_content or {}).get("知识点") or [])
            for q in rows
            if q.analysis_content and (q.analysis_content or {}).get("知识点")
        ]

    total = 0
    for question_id, kp_names in items:
        names = [str(n).strip() for n in kp_names if str(n).strip()][:6]
        ids: list[str] = []
        for name in names:
            res = await kg.upsert_knowledge_point(
                teacher_id=teacher_id,
                name=name,
                subject_id=subject_id,
                subject_name=subject_name,
                school_level_id=school_level_id,
                grade_id=grade_id,
                description="",
                difficulty=3,
                tags=[],
                source="analysis",
                embed_model=gw.model if gw else None,
                embed_api_base=gw.api_base if gw else None,
                embed_api_key=gw.api_key if gw else None,
            )
            if res:
                ids.append(res["id"])
                await kg.link_source(res["id"], question_id=question_id)
                total += 1
        # 同题共现：知识点两两建立弱相关关系
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                if ids[i] == ids[j]:
                    continue
                try:
                    await kg.add_relation(
                        from_id=ids[i], to_id=ids[j], rel_type="related",
                        weight=0.3, cross_subject=False, status="approved",
                        source="analysis", evidence="同题共现",
                    )
                except Exception:  # noqa: BLE001
                    pass
    return {"stored": total}


async def suggest_cross_subject_relations(
    teacher_id: int, threshold: float = 0.82, per_node: int = 3, max_nodes: int = 200
) -> dict:
    """用向量相似度发现跨学科关联，写入 status=pending 的 RELATED 边，待教师审核。"""
    from app.services.embedding_service import embed_text
    from app.core import qdrant_client as vec
    from app.core import neo4j_client as neo

    async with AsyncSessionLocal() as db:
        gw = await _embed_gw(db, teacher_id)
    if not gw:
        return {"suggested": 0, "error": "未启用向量嵌入，无法自动发现跨学科关联"}

    nodes = await neo.run_read(
        "MATCH (k:KnowledgePoint {teacher_id:$tid}) "
        "RETURN k{.id,.name,.subject_id,.description} AS node LIMIT $lim",
        {"tid": teacher_id, "lim": max_nodes},
    )
    suggested = 0
    for row in nodes:
        n = row["node"]
        vector = await embed_text(
            f"{n['name']}。{n.get('description') or ''}",
            gateway=gw,
        )
        if not vector:
            continue
        hits = await vec.search_similar(vector, flt={"teacher_id": teacher_id}, limit=per_node + 3)
        for h in hits:
            if h["id"] == n["id"]:
                continue
            other_subject = (h.get("payload") or {}).get("subject_id")
            if other_subject and n.get("subject_id") and other_subject != n["subject_id"] \
                    and h["score"] >= threshold:
                try:
                    await kg.add_relation(
                        from_id=n["id"], to_id=h["id"], rel_type="related",
                        weight=round(float(h["score"]), 3), cross_subject=True,
                        status="pending", source="vector",
                        evidence=f"语义相似度 {h['score']:.2f}",
                    )
                    suggested += 1
                except Exception:  # noqa: BLE001
                    pass
    return {"suggested": suggested}
