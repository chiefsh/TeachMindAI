"""互动动画库：系统实验台缓存 + 教师另存，供课件引用而不重复生成。"""
from __future__ import annotations

import logging
import secrets
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.animation import InteractiveAsset

logger = logging.getLogger(__name__)


def _lab_rows() -> list[dict]:
    from app.services.skill_service import LAB_CATALOG, LAB_KEYWORDS
    rows = []
    for e in LAB_CATALOG:
        rows.append({
            "key": e["key"],
            "title": e["title"],
            "subject": "化学",
            "group": e["group"],
            "kind": "chem_lab",
            "origin": "system",
            "keywords": list(LAB_KEYWORDS.get(e["key"], ())),
            "knowledge_tags": [],
            "skill": "edu-chem-lab",
            "problem_type": e["key"],
            "spec": {},
        })
    return rows


async def ensure_system_labs(db: AsyncSession) -> None:
    """把 LAB_CATALOG 灌进库（只补缺失行，不覆盖教师改过的系统标题）。"""
    existing = {
        r[0] for r in (await db.execute(select(InteractiveAsset.key))).all()
    }
    added = False
    for row in _lab_rows():
        if row["key"] in existing:
            continue
        db.add(InteractiveAsset(**row, teacher_id=None, html=None))
        added = True
    if added:
        await db.commit()


async def get_by_key(db: AsyncSession, key: str) -> InteractiveAsset | None:
    if not key:
        return None
    return (await db.execute(
        select(InteractiveAsset).where(InteractiveAsset.key == key)
    )).scalar_one_or_none()


def to_out(row: InteractiveAsset) -> dict:
    return {
        "id": row.id,
        "key": row.key,
        "title": row.title,
        "subject": row.subject,
        "group": row.group,
        "kind": row.kind,
        "origin": row.origin,
        "teacher_id": row.teacher_id,
        "keywords": list(row.keywords or []),
        "knowledge_tags": list(row.knowledge_tags or []),
        "skill": row.skill,
        "problem_type": row.problem_type,
        "spec": row.spec or {},
        "has_html": bool(row.html),
        "created_at": row.created_at,
    }


async def list_assets(
    db: AsyncSession,
    teacher_id: int,
    *,
    subject: str | None = None,
    view_all: bool = False,
) -> list[InteractiveAsset]:
    await ensure_system_labs(db)
    q = select(InteractiveAsset)
    if view_all:
        pass
    else:
        q = q.where(or_(
            InteractiveAsset.origin == "system",
            InteractiveAsset.teacher_id == teacher_id,
        ))
    if subject:
        if subject == "科学":
            q = q.where(or_(
                InteractiveAsset.subject == "科学",
                InteractiveAsset.kind == "chem_lab",
            ))
        else:
            q = q.where(InteractiveAsset.subject == subject)
    q = q.order_by(InteractiveAsset.origin.asc(), InteractiveAsset.group.asc(), InteractiveAsset.id.asc())
    return list((await db.execute(q)).scalars().all())


async def render_and_store(db: AsyncSession, row: InteractiveAsset) -> str:
    html = ""
    if row.skill == "edu-chem-lab":
        from app.services.skill_service import render_chem_lab_html
        html = await render_chem_lab_html({
            "skill": "edu-chem-lab",
            "problem_type": row.problem_type,
            "spec": row.spec or {},
        })
    if html:
        row.html = html
        await db.commit()
        await db.refresh(row)
    return html or ""


async def html_for_row(db: AsyncSession, row: InteractiveAsset) -> str:
    if row.html:
        return row.html
    return await render_and_store(db, row)


async def html_for_key(key: str) -> str:
    html, _ = await payload_for_key(key)
    return html


async def payload_for_key(key: str) -> tuple[str, dict | None]:
    """返回 (html, skill 元数据)。库未命中则 ('', None)。"""
    async with AsyncSessionLocal() as db:
        await ensure_system_labs(db)
        row = await get_by_key(db, key)
        if not row:
            return "", None
        html = await html_for_row(db, row)
        if not html:
            return "", None
        return html, {
            "skill": row.skill,
            "problem_type": row.problem_type,
            "spec": row.spec or {},
            "asset_key": row.key,
            "title": row.title,
        }


async def duplicate_from_template(
    db: AsyncSession, teacher_id: int, template_key: str, title: str,
    keywords: list[str], knowledge_tags: list[str],
) -> InteractiveAsset:
    await ensure_system_labs(db)
    src = await get_by_key(db, template_key)
    if not src:
        raise ValueError("模板不存在")
    new_key = f"u{teacher_id}_{src.problem_type}_{secrets.token_hex(3)}"
    row = InteractiveAsset(
        key=new_key,
        title=title,
        subject=src.subject,
        group=src.group,
        kind=src.kind,
        origin="teacher",
        teacher_id=teacher_id,
        keywords=keywords or list(src.keywords or []),
        knowledge_tags=knowledge_tags or list(src.knowledge_tags or []),
        skill=src.skill,
        problem_type=src.problem_type,
        spec=dict(src.spec or {}),
        html=src.html,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    if not row.html:
        await render_and_store(db, row)
    return row


def resolve_keys(cw, points: list[dict], title: str, subject_name: str) -> list[str]:
    """出课用：手动选择 > 旧字段 virtual_lab_key > 自动匹配。"""
    raw = getattr(cw, "animation_keys", None) or []
    keys = [str(k).strip() for k in raw if str(k).strip()]
    if keys:
        return keys
    explicit = (getattr(cw, "virtual_lab_key", None) or "").strip()
    if explicit:
        return [explicit]
    if not getattr(cw, "want_virtual_lab", False):
        return []
    from app.services.skill_service import pick_chem_lab, _is_lab_subject
    if not (_is_lab_subject(subject_name) or explicit):
        return []
    picked = pick_chem_lab(points, title, None)
    return [picked[1]] if picked else []
