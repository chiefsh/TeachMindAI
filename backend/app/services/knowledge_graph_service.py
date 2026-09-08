"""知识图谱服务：知识点（节点）与关系（边）的读写。

- 图存储：Neo4j（节点 KnowledgePoint / Concept，关系 PREREQUISITE / PART_OF / RELATED / APPLIES_IN / CONTRAST）
- 向量存储：Qdrant（知识点 embedding，用于语义去重与相似检索）
- 去重：优先向量相似度（同 teacher+subject 内 >= 阈值视为同一点），否则按名称精确匹配。
"""
import logging
import uuid
from datetime import datetime, timezone

from app.core.config import settings
from app.core import neo4j_client as neo
from app.core import qdrant_client as vec
from app.services.embedding_service import embed_text

logger = logging.getLogger(__name__)

# API 关系类型 → Neo4j 关系类型（白名单，防注入）
REL_TYPE_MAP = {
    "prerequisite": "PREREQUISITE",
    "part_of": "PART_OF",
    "related": "RELATED",
    "application": "APPLIES_IN",
    "contrast": "CONTRAST",
}
_NEO_TO_API = {v: k for k, v in REL_TYPE_MAP.items()}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _embed_source(name: str, description: str = "") -> str:
    return f"{name}。{description}".strip("。")


async def upsert_knowledge_point(
    *,
    teacher_id: int,
    name: str,
    subject_id: int | None = None,
    subject_name: str = "",
    school_level_id: int | None = None,
    grade_id: int | None = None,
    description: str = "",
    difficulty: int = 3,
    tags: list[str] | None = None,
    source: str = "llm",
    embed_api_base: str | None = None,
    embed_api_key: str | None = None,
) -> dict | None:
    """新增或复用知识点。返回 {id, name, merged}。KG 未启用返回 None。"""
    if not settings.KG_ENABLED:
        return None
    name = (name or "").strip()
    if not name:
        return None
    tags = [str(t).strip() for t in (tags or []) if str(t).strip()][:8]

    vector = await embed_text(
        _embed_source(name, description),
        api_base=embed_api_base, api_key=embed_api_key,
    )

    # ── 去重 ──
    existing_id: str | None = None
    if vector:
        flt = {"teacher_id": teacher_id}
        if subject_id:
            flt["subject_id"] = subject_id
        hits = await vec.search_similar(vector, flt=flt, limit=1)
        if hits and hits[0]["score"] >= settings.KG_DEDUP_THRESHOLD:
            existing_id = hits[0]["id"]
    if not existing_id:
        rows = await neo.run_read(
            "MATCH (k:KnowledgePoint {teacher_id:$tid, name:$name}) "
            "WHERE ($sid IS NULL OR k.subject_id=$sid) "
            "RETURN k.id AS id LIMIT 1",
            {"tid": teacher_id, "name": name, "sid": subject_id},
        )
        if rows:
            existing_id = rows[0]["id"]

    if existing_id:
        # 已存在：补全空描述、合并标签（不依赖 APOC，用原生列表去重）
        await neo.run_write(
            "MATCH (k:KnowledgePoint {id:$id}) "
            "SET k.description = CASE WHEN coalesce(k.description,'')='' THEN $desc ELSE k.description END, "
            "    k.tags = coalesce(k.tags,[]) + [t IN $tags WHERE NOT t IN coalesce(k.tags,[])], "
            "    k.updated_at = $now",
            {"id": existing_id, "desc": description, "tags": tags, "now": _now()},
        )
        return {"id": existing_id, "name": name, "merged": True}

    # ── 新建 ──
    kp_id = uuid.uuid4().hex
    await neo.run_write(
        "MERGE (k:KnowledgePoint {id:$id}) "
        "SET k.teacher_id=$tid, k.name=$name, k.subject_id=$sid, k.subject_name=$sname, "
        "    k.school_level_id=$level, k.grade_id=$gid, k.description=$desc, "
        "    k.difficulty=$diff, k.tags=$tags, k.source=$source, "
        "    k.courseware_ids=[], k.question_ids=[], k.created_at=$now, k.updated_at=$now",
        {
            "id": kp_id, "tid": teacher_id, "name": name, "sid": subject_id,
            "sname": subject_name, "level": school_level_id, "gid": grade_id,
            "desc": description, "diff": int(difficulty or 3), "tags": tags,
            "source": source, "now": _now(),
        },
    )
    if vector:
        await vec.upsert_vector(kp_id, vector, {
            "teacher_id": teacher_id, "subject_id": subject_id or 0, "name": name,
        })
    return {"id": kp_id, "name": name, "merged": False}


async def points_by_courseware(teacher_id: int, courseware_ids: list[int]) -> list[dict]:
    """按课件 id 取已关联的知识点（名称 + 标签），用于组卷范围约束。"""
    if not settings.KG_ENABLED or not courseware_ids:
        return []
    rows = await neo.run_read(
        "MATCH (k:KnowledgePoint {teacher_id:$tid}) "
        "WHERE any(cid IN coalesce(k.courseware_ids,[]) WHERE cid IN $cids) "
        "RETURN k.name AS name, k.id AS id, k.tags AS tags",
        {"tid": teacher_id, "cids": list(courseware_ids)},
    )
    return rows or []


async def link_source(kp_id: str, *, courseware_id: int | None = None, question_id: int | None = None):
    """把知识点关联到业务实体（课件/题目），存为节点列表属性。"""
    if not settings.KG_ENABLED or not kp_id:
        return
    if courseware_id is not None:
        await neo.run_write(
            "MATCH (k:KnowledgePoint {id:$id}) "
            "SET k.courseware_ids = [x IN coalesce(k.courseware_ids,[]) | x] + "
            "  CASE WHEN $cid IN coalesce(k.courseware_ids,[]) THEN [] ELSE [$cid] END",
            {"id": kp_id, "cid": courseware_id},
        )
    if question_id is not None:
        await neo.run_write(
            "MATCH (k:KnowledgePoint {id:$id}) "
            "SET k.question_ids = [x IN coalesce(k.question_ids,[]) | x] + "
            "  CASE WHEN $qid IN coalesce(k.question_ids,[]) THEN [] ELSE [$qid] END",
            {"id": kp_id, "qid": question_id},
        )


async def add_relation(
    *, from_id: str, to_id: str, rel_type: str,
    weight: float = 0.6, cross_subject: bool = False,
    status: str = "approved", source: str = "manual", evidence: str = "",
) -> bool:
    """新增关系边。rel_type 为 API 类型（见 REL_TYPE_MAP）。"""
    if not settings.KG_ENABLED or from_id == to_id:
        return False
    neo_type = REL_TYPE_MAP.get(rel_type)
    if not neo_type:
        raise ValueError(f"不支持的关系类型：{rel_type}")
    # rel_type 已白名单化，可安全插入查询串
    await neo.run_write(
        f"MATCH (a:KnowledgePoint {{id:$from}}) "
        f"WITH a MATCH (b:KnowledgePoint {{id:$to}}) "
        f"MERGE (a)-[r:{neo_type}]->(b) "
        f"SET r.weight=$weight, r.cross_subject=$cross, r.status=$status, "
        f"    r.source=$source, r.evidence=$evidence, r.updated_at=$now",
        {
            "from": from_id, "to": to_id, "weight": float(weight),
            "cross": bool(cross_subject), "status": status, "source": source,
            "evidence": evidence, "now": _now(),
        },
    )
    return True


async def delete_relation(from_id: str, to_id: str, rel_type: str) -> None:
    neo_type = REL_TYPE_MAP.get(rel_type)
    if not neo_type:
        return
    await neo.run_write(
        f"MATCH (a:KnowledgePoint {{id:$from}})-[r:{neo_type}]->(b:KnowledgePoint {{id:$to}}) DELETE r",
        {"from": from_id, "to": to_id},
    )


async def set_relation_status(from_id: str, to_id: str, rel_type: str, status: str) -> None:
    neo_type = REL_TYPE_MAP.get(rel_type)
    if not neo_type:
        return
    await neo.run_write(
        f"MATCH (a:KnowledgePoint {{id:$from}})-[r:{neo_type}]->(b:KnowledgePoint {{id:$to}}) "
        f"SET r.status=$status",
        {"from": from_id, "to": to_id, "status": status},
    )


def _edge_out(row: dict) -> dict:
    return {
        "source": row["source"],
        "target": row["target"],
        "type": _NEO_TO_API.get(row["type"], row["type"].lower()),
        "weight": row.get("weight") or 0.5,
        "cross_subject": bool(row.get("cross_subject")),
        "status": row.get("status") or "approved",
    }


async def get_graph(
    teacher_id: int, subject_id: int | None = None,
    grade_id: int | None = None, limit: int = 300,
) -> dict:
    """返回可视化用的 {nodes, edges}。含跨学科邻居节点以保证连通。"""
    if not settings.KG_ENABLED:
        return {"nodes": [], "edges": []}
    nodes_rows = await neo.run_read(
        "MATCH (k:KnowledgePoint) WHERE k.teacher_id=$tid "
        "AND ($sid IS NULL OR k.subject_id=$sid) "
        "AND ($gid IS NULL OR k.grade_id=$gid) "
        "RETURN k{.*} AS node ORDER BY k.created_at DESC LIMIT $limit",
        {"tid": teacher_id, "sid": subject_id, "gid": grade_id, "limit": limit},
    )
    nodes = {r["node"]["id"]: r["node"] for r in nodes_rows}
    if not nodes:
        return {"nodes": [], "edges": []}

    ids = list(nodes.keys())
    edge_rows = await neo.run_read(
        "MATCH (a:KnowledgePoint)-[r]->(b:KnowledgePoint) "
        "WHERE a.id IN $ids OR b.id IN $ids "
        "RETURN a.id AS source, b.id AS target, type(r) AS type, "
        "r.weight AS weight, r.cross_subject AS cross_subject, r.status AS status",
        {"ids": ids},
    )
    edges = [_edge_out(r) for r in edge_rows]

    # 补齐边引用到但不在节点集合中的跨学科邻居
    missing = {e["source"] for e in edges} | {e["target"] for e in edges}
    missing -= set(nodes.keys())
    if missing:
        extra = await neo.run_read(
            "MATCH (k:KnowledgePoint) WHERE k.id IN $ids RETURN k{.*} AS node",
            {"ids": list(missing)},
        )
        for r in extra:
            nodes[r["node"]["id"]] = r["node"]

    return {"nodes": list(nodes.values()), "edges": edges}


async def get_point(kp_id: str) -> dict | None:
    if not settings.KG_ENABLED:
        return None
    rows = await neo.run_read(
        "MATCH (k:KnowledgePoint {id:$id}) RETURN k{.*} AS node", {"id": kp_id})
    if not rows:
        return None
    node = rows[0]["node"]
    nbr = await neo.run_read(
        "MATCH (k:KnowledgePoint {id:$id})-[r]-(o:KnowledgePoint) "
        "RETURN type(r) AS type, "
        "startNode(r).id=$id AS outgoing, o{.id,.name,.subject_name} AS other, "
        "r.weight AS weight, r.cross_subject AS cross_subject, r.status AS status",
        {"id": kp_id},
    )
    neighbors = [{
        "type": _NEO_TO_API.get(r["type"], r["type"].lower()),
        "direction": "out" if r["outgoing"] else "in",
        "other": r["other"],
        "weight": r.get("weight") or 0.5,
        "cross_subject": bool(r.get("cross_subject")),
        "status": r.get("status") or "approved",
    } for r in nbr]
    node["neighbors"] = neighbors
    return node


async def search_points(
    teacher_id: int, keyword: str = "", subject_id: int | None = None, limit: int = 30
) -> list[dict]:
    if not settings.KG_ENABLED:
        return []
    rows = await neo.run_read(
        "MATCH (k:KnowledgePoint) WHERE k.teacher_id=$tid "
        "AND ($kw='' OR toLower(k.name) CONTAINS toLower($kw)) "
        "AND ($sid IS NULL OR k.subject_id=$sid) "
        "RETURN k{.*} AS node ORDER BY k.updated_at DESC LIMIT $limit",
        {"tid": teacher_id, "kw": keyword or "", "sid": subject_id, "limit": limit},
    )
    return [r["node"] for r in rows]


async def prerequisite_path(kp_id: str) -> list[dict]:
    """返回该知识点的前置链（去重，按依赖深度）。"""
    if not settings.KG_ENABLED:
        return []
    rows = await neo.run_read(
        "MATCH (pre:KnowledgePoint)-[:PREREQUISITE*1..6]->(k:KnowledgePoint {id:$id}) "
        "RETURN DISTINCT pre{.id,.name,.subject_name} AS node",
        {"id": kp_id},
    )
    return [r["node"] for r in rows]


async def delete_point(kp_id: str) -> None:
    if not settings.KG_ENABLED:
        return
    await neo.run_write(
        "MATCH (k:KnowledgePoint {id:$id}) DETACH DELETE k", {"id": kp_id})
    await vec.delete_vector(kp_id)


async def stats(teacher_id: int) -> dict:
    if not settings.KG_ENABLED:
        return {"point_count": 0, "relation_count": 0}
    n = await neo.run_read(
        "MATCH (k:KnowledgePoint {teacher_id:$tid}) RETURN count(k) AS c", {"tid": teacher_id})
    r = await neo.run_read(
        "MATCH (a:KnowledgePoint {teacher_id:$tid})-[rel]->(b:KnowledgePoint) RETURN count(rel) AS c",
        {"tid": teacher_id})
    return {
        "point_count": (n[0]["c"] if n else 0),
        "relation_count": (r[0]["c"] if r else 0),
    }
