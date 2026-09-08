"""课件 / 试题分析免登录分享。"""
from datetime import datetime, timedelta
from math import ceil
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_teacher
from app.core.config import settings
from app.core.database import get_db
from app.core.minio_client import get_presigned_url
from app.core.security import get_password_hash, verify_password
from app.models.courseware import Courseware
from app.models.education import Grade, Subject
from app.models.question_analysis import AnalysisSet
from app.models.share import ShareLink
from app.models.teacher import Teacher
from app.models.textbook import ParseStatus, Textbook, TextbookImage
from app.schemas.share import ShareAccessIn, ShareCreateIn, ShareMetaOut, ShareOut, SharePayloadOut

router = APIRouter(tags=["分享"])


def _now() -> datetime:
    return datetime.utcnow()


def _expired(link: ShareLink) -> bool:
    return bool(link.expires_at and link.expires_at <= _now())


def _to_out(link: ShareLink, title: str = "") -> ShareOut:
    return ShareOut(
        id=link.id,
        token=link.token,
        resource_type=link.resource_type,
        resource_id=link.resource_id,
        title=title,
        has_password=bool(link.password_hash),
        expires_at=link.expires_at,
        revoked=bool(link.revoked),
        created_at=link.created_at,
    )


async def _owned_title(
    resource_type: str, resource_id: int, teacher_id: int, db: AsyncSession, *, require_ready: bool,
) -> str:
    if resource_type == "courseware":
        cw = (
            await db.execute(
                select(Courseware).where(Courseware.id == resource_id, Courseware.teacher_id == teacher_id)
            )
        ).scalar_one_or_none()
        if not cw:
            raise HTTPException(status_code=404, detail="课件不存在")
        if require_ready and (cw.gen_status != ParseStatus.done or not cw.content):
            raise HTTPException(status_code=400, detail="课件尚未生成完成，无法分享")
        return cw.title
    if resource_type == "question_analysis":
        aset = (
            await db.execute(
                select(AnalysisSet)
                .options(selectinload(AnalysisSet.questions))
                .where(AnalysisSet.id == resource_id, AnalysisSet.teacher_id == teacher_id)
            )
        ).scalar_one_or_none()
        if not aset:
            raise HTTPException(status_code=404, detail="试题批次不存在")
        if require_ready and (aset.parse_status != ParseStatus.done or not aset.questions):
            raise HTTPException(status_code=400, detail="试题尚未解析完成，无法分享")
        return aset.name
    raise HTTPException(status_code=400, detail="不支持的分享类型")


@router.post("/shares", response_model=ShareOut, status_code=201)
async def create_share(
    data: ShareCreateIn,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    title = await _owned_title(data.resource_type, data.resource_id, teacher.id, db, require_ready=True)
    link = ShareLink(
        teacher_id=teacher.id,
        resource_type=data.resource_type,
        resource_id=data.resource_id,
        token=secrets.token_urlsafe(16),
        password_hash=get_password_hash(data.password) if data.password else None,
        expires_at=_now() + timedelta(days=data.expire_days),
        revoked=False,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return _to_out(link, title)


@router.get("/shares", response_model=list[ShareOut])
async def list_shares(
    resource_type: str,
    resource_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    title = await _owned_title(resource_type, resource_id, teacher.id, db, require_ready=False)
    rows = (
        await db.execute(
            select(ShareLink)
            .where(
                ShareLink.teacher_id == teacher.id,
                ShareLink.resource_type == resource_type,
                ShareLink.resource_id == resource_id,
                ShareLink.revoked.is_(False),
            )
            .order_by(ShareLink.id.desc())
        )
    ).scalars().all()
    return [_to_out(r, title) for r in rows]


@router.delete("/shares/{share_id}", status_code=204)
async def revoke_share(
    share_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    link = (
        await db.execute(
            select(ShareLink).where(ShareLink.id == share_id, ShareLink.teacher_id == teacher.id)
        )
    ).scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="分享不存在")
    link.revoked = True
    await db.commit()


def _meta_for(link: ShareLink | None, title: str = "") -> ShareMetaOut:
    if not link:
        return ShareMetaOut(status="not_found")
    if link.revoked:
        return ShareMetaOut(status="revoked", title=title, resource_type=link.resource_type)
    if _expired(link):
        return ShareMetaOut(
            status="expired", title=title, resource_type=link.resource_type, expires_at=link.expires_at,
        )
    has_pwd = bool(link.password_hash)
    return ShareMetaOut(
        status="need_password" if has_pwd else "ok",
        title=title,
        resource_type=link.resource_type,
        has_password=has_pwd,
        expires_at=link.expires_at,
    )


async def _load_link(token: str, db: AsyncSession) -> ShareLink | None:
    return (
        await db.execute(select(ShareLink).where(ShareLink.token == token))
    ).scalar_one_or_none()


async def _resource_title(link: ShareLink, db: AsyncSession) -> str:
    if link.resource_type == "courseware":
        cw = (await db.execute(select(Courseware).where(Courseware.id == link.resource_id))).scalar_one_or_none()
        return cw.title if cw else ""
    if link.resource_type == "question_analysis":
        aset = (await db.execute(select(AnalysisSet).where(AnalysisSet.id == link.resource_id))).scalar_one_or_none()
        return aset.name if aset else ""
    return ""


@router.get("/public/shares/{token}", response_model=ShareMetaOut)
async def public_share_meta(token: str, db: AsyncSession = Depends(get_db)):
    link = await _load_link(token, db)
    title = await _resource_title(link, db) if link else ""
    return _meta_for(link, title)


def _image_ids(content: dict | None) -> list[int]:
    ids: list[int] = []
    for s in (content or {}).get("slides") or []:
        if not isinstance(s, dict):
            continue
        for iid in s.get("images") or []:
            if isinstance(iid, int):
                ids.append(iid)
            elif isinstance(iid, str) and iid.isdigit():
                ids.append(int(iid))
    return list(dict.fromkeys(ids))


async def _courseware_payload(cw: Courseware, expires_at: datetime, db: AsyncSession) -> dict:
    remain_h = max(1, min(168, ceil((expires_at - _now()).total_seconds() / 3600)))
    images: dict[str, str] = {}
    ids = _image_ids(cw.content if isinstance(cw.content, dict) else None)
    if ids:
        rows = (
            await db.execute(select(TextbookImage).where(TextbookImage.id.in_(ids)))
        ).scalars().all()
        for img in rows:
            try:
                images[str(img.id)] = get_presigned_url(
                    settings.MINIO_BUCKET_TEXTBOOKS, img.object_name, expires_hours=remain_h,
                )
            except Exception:
                continue
    grade_name = subject_name = ""
    if cw.textbook_id:
        tb = (
            await db.execute(select(Textbook).where(Textbook.id == cw.textbook_id))
        ).scalar_one_or_none()
        if tb:
            g = (await db.execute(select(Grade).where(Grade.id == tb.grade_id))).scalar_one_or_none()
            s = (await db.execute(select(Subject).where(Subject.id == tb.subject_id))).scalar_one_or_none()
            grade_name = g.name if g else ""
            subject_name = s.name if s else ""
    return {
        "render_style": cw.render_style.value if hasattr(cw.render_style, "value") else (cw.render_style or "ppt"),
        "theme": cw.theme or "indigo",
        "content": cw.content or {},
        "images": images,
        "grade_name": grade_name,
        "subject_name": subject_name,
        "is_interactive": bool(cw.is_interactive),
    }


async def _analysis_payload(aset: AnalysisSet, db: AsyncSession) -> dict:
    aset = (
        await db.execute(
            select(AnalysisSet)
            .options(selectinload(AnalysisSet.questions))
            .where(AnalysisSet.id == aset.id)
        )
    ).scalar_one_or_none() or aset
    g = (await db.execute(select(Grade).where(Grade.id == aset.grade_id))).scalar_one_or_none()
    s = (await db.execute(select(Subject).where(Subject.id == aset.subject_id))).scalar_one_or_none()
    questions = []
    for q in aset.questions or []:
        questions.append({
            "id": q.id,
            "seq": q.seq,
            "content": q.content,
            "options": q.options,
            "answer": q.answer,
            "question_type": q.question_type.value if hasattr(q.question_type, "value") else q.question_type,
            "difficulty": q.difficulty.value if hasattr(q.difficulty, "value") else q.difficulty,
            "analysis_status": q.analysis_status.value if hasattr(q.analysis_status, "value") else q.analysis_status,
            "analysis_content": q.analysis_content,
            "analysis_html": q.analysis_html,
        })
    return {
        "name": aset.name,
        "grade_name": g.name if g else "",
        "subject_name": s.name if s else "",
        "questions": questions,
    }


async def _build_payload(link: ShareLink, db: AsyncSession) -> dict:
    if link.resource_type == "courseware":
        cw = (
            await db.execute(select(Courseware).where(Courseware.id == link.resource_id))
        ).scalar_one_or_none()
        if not cw or cw.gen_status != ParseStatus.done or not cw.content:
            raise HTTPException(status_code=404, detail="分享内容已不可用")
        return await _courseware_payload(cw, link.expires_at, db)
    if link.resource_type == "question_analysis":
        aset = (
            await db.execute(select(AnalysisSet).where(AnalysisSet.id == link.resource_id))
        ).scalar_one_or_none()
        if not aset or aset.parse_status != ParseStatus.done:
            raise HTTPException(status_code=404, detail="分享内容已不可用")
        return await _analysis_payload(aset, db)
    raise HTTPException(status_code=404, detail="分享内容已不可用")


@router.post("/public/shares/{token}/access", response_model=SharePayloadOut)
async def public_share_access(
    token: str,
    data: ShareAccessIn = ShareAccessIn(),
    db: AsyncSession = Depends(get_db),
):
    link = await _load_link(token, db)
    title = await _resource_title(link, db) if link else ""
    meta = _meta_for(link, title)
    if meta.status == "not_found":
        raise HTTPException(status_code=404, detail="分享链接不存在")
    if meta.status == "revoked":
        raise HTTPException(status_code=410, detail="分享链接已被取消")
    if meta.status == "expired":
        raise HTTPException(status_code=410, detail="分享链接已过期")
    assert link is not None
    if link.password_hash:
        pwd = data.password or ""
        if not pwd or not verify_password(pwd, link.password_hash):
            raise HTTPException(status_code=403, detail="密码错误")
    return SharePayloadOut(
        resource_type=link.resource_type,
        title=title,
        expires_at=link.expires_at,
        payload=await _build_payload(link, db),
    )
