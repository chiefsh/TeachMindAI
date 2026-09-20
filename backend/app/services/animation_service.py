"""互动动画库：系统预置（实验台 / 数学探究 / 分子 3D）+ 教师另存，供课件引用。"""
from __future__ import annotations

import json
import logging
import secrets
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select, or_
from sqlalchemy.orm import load_only
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.animation import InteractiveAsset

logger = logging.getLogger(__name__)

_SYNC_FIELDS = (
    "subject", "group", "kind", "keywords", "knowledge_tags",
    "skill", "problem_type", "spec",
)

_LAB_TAGS: dict[str, list[str]] = {
    "prep_oxygen_kmno4": ["制取氧气", "氧气"],
    "prep_hydrogen": ["制取氢气", "氢气"],
    "prep_co2": ["制取二氧化碳", "二氧化碳"],
    "electrolysis": ["电解水"],
    "neutralization": ["中和反应", "酸碱中和"],
    "metal_acid": ["金属活动性", "金属与酸"],
    "nh4hco3_decomp": ["碳酸氢铵分解", "铵盐"],
    "iron_in_oxygen": ["铁丝燃烧"],
    "filtration": ["过滤"],
    "evaporation": ["蒸发结晶"],
    "solution_prep": ["配制溶液", "溶质质量分数"],
}

# 数学 / 分子 3D：每条对应一个常用知识点，key 与 chem-lab 不冲突。
_EXTRA_ASSETS: list[dict] = [
    {
        "key": "solid_cube",
        "title": "正方体探究台",
        "subject": "数学",
        "group": "立体几何",
        "kind": "solid_explore",
        "keywords": ["正方体", "立方体", "正六面体"],
        "knowledge_tags": ["正方体", "立方体", "立体图形"],
        "skill": "edu-solid-geometry",
        "problem_type": "solid_explore",
        "spec": {"body": "cube", "edge": 2},
    },
    {
        "key": "solid_cuboid",
        "title": "长方体探究台",
        "subject": "数学",
        "group": "立体几何",
        "kind": "solid_explore",
        "keywords": ["长方体", "直四棱柱"],
        "knowledge_tags": ["长方体", "立体图形"],
        "skill": "edu-solid-geometry",
        "problem_type": "solid_explore",
        "spec": {"body": "cuboid", "lx": 3, "ly": 4, "lz": 5},
    },
    {
        "key": "solid_quad_pyramid",
        "title": "正四棱锥探究台",
        "subject": "数学",
        "group": "立体几何",
        "kind": "solid_explore",
        "keywords": ["正四棱锥", "四棱锥", "棱锥"],
        "knowledge_tags": ["正四棱锥", "棱锥", "立体图形"],
        "skill": "edu-solid-geometry",
        "problem_type": "solid_explore",
        "spec": {"body": "quad_pyramid", "base_edge": 4, "height": 3},
    },
    {
        "key": "solid_tetrahedron",
        "title": "正四面体探究台",
        "subject": "数学",
        "group": "立体几何",
        "kind": "solid_explore",
        "keywords": ["正四面体", "四面体"],
        "knowledge_tags": ["正四面体", "立体图形"],
        "skill": "edu-solid-geometry",
        "problem_type": "solid_explore",
        "spec": {"body": "tetrahedron", "edge": 2},
    },
    {
        "key": "solid_tri_prism",
        "title": "正三棱柱探究台",
        "subject": "数学",
        "group": "立体几何",
        "kind": "solid_explore",
        "keywords": ["正三棱柱", "三棱柱", "棱柱"],
        "knowledge_tags": ["正三棱柱", "棱柱", "立体图形"],
        "skill": "edu-solid-geometry",
        "problem_type": "solid_explore",
        "spec": {"body": "tri_prism", "base_edge": 2, "height": 3},
    },
    {
        "key": "curve_ellipse",
        "title": "椭圆定义画板",
        "subject": "数学",
        "group": "圆锥曲线",
        "kind": "curve_explore",
        "keywords": ["椭圆", "长轴", "短轴", "椭圆的定义"],
        "knowledge_tags": ["椭圆", "圆锥曲线"],
        "skill": "edu-analytic-geometry",
        "problem_type": "curve_explore",
        "spec": {"curve": "ellipse", "a": 2, "b": 1},
    },
    {
        "key": "curve_hyperbola",
        "title": "双曲线定义画板",
        "subject": "数学",
        "group": "圆锥曲线",
        "kind": "curve_explore",
        "keywords": ["双曲线", "渐近线", "双曲线的定义"],
        "knowledge_tags": ["双曲线", "圆锥曲线"],
        "skill": "edu-analytic-geometry",
        "problem_type": "curve_explore",
        "spec": {"curve": "hyperbola", "a": 2, "b": 1, "orient": "x"},
    },
    {
        "key": "curve_parabola",
        "title": "抛物线定义画板",
        "subject": "数学",
        "group": "圆锥曲线",
        "kind": "curve_explore",
        "keywords": ["抛物线", "准线", "抛物线的定义"],
        "knowledge_tags": ["抛物线", "圆锥曲线"],
        "skill": "edu-analytic-geometry",
        "problem_type": "curve_explore",
        "spec": {"curve": "parabola", "p": 2, "axis": "x"},
    },
    {
        "key": "curve_circle",
        "title": "圆的方程画板",
        "subject": "数学",
        "group": "圆锥曲线",
        "kind": "curve_explore",
        "keywords": ["圆的标准方程", "圆的方程", "圆心距"],
        "knowledge_tags": ["圆", "圆的方程"],
        "skill": "edu-analytic-geometry",
        "problem_type": "curve_explore",
        "spec": {"curve": "circle", "r": 2},
    },
    {
        "key": "combustion_ch4",
        "title": "甲烷燃烧（分子 3D）",
        "subject": "化学",
        "group": "分子反应",
        "kind": "chem_reaction",
        "keywords": ["甲烷燃烧", "甲烷", "CH4"],
        "knowledge_tags": ["甲烷燃烧", "燃烧"],
        "skill": "edu-chem-reaction",
        "problem_type": "combustion_ch4",
        "spec": {},
    },
    {
        "key": "combustion_h2",
        "title": "氢气燃烧（分子 3D）",
        "subject": "化学",
        "group": "分子反应",
        "kind": "chem_reaction",
        "keywords": ["氢气燃烧", "氢氧燃烧"],
        "knowledge_tags": ["氢气燃烧", "燃烧"],
        "skill": "edu-chem-reaction",
        "problem_type": "combustion_h2",
        "spec": {},
    },
    {
        "key": "electrolysis_water",
        "title": "电解水（分子 3D）",
        "subject": "化学",
        "group": "分子反应",
        "kind": "chem_reaction",
        "keywords": ["电解水", "正氧负氢", "水的电解"],
        "knowledge_tags": ["电解水"],
        "skill": "edu-chem-reaction",
        "problem_type": "electrolysis_water",
        "spec": {},
    },
    {
        "key": "redox_na_cl2",
        "title": "钠与氯气反应（电子转移）",
        "subject": "化学",
        "group": "分子反应",
        "kind": "chem_reaction",
        "keywords": ["钠与氯气", "氯化钠", "离子键", "电子转移", "氧化还原"],
        "knowledge_tags": ["钠与氯气", "离子键", "氧化还原"],
        "skill": "edu-chem-reaction",
        "problem_type": "redox_na_cl2",
        "spec": {},
    },
    {
        "key": "esterification",
        "title": "酯化反应（乙酸+乙醇）",
        "subject": "化学",
        "group": "分子反应",
        "kind": "chem_reaction",
        "keywords": ["酯化", "乙酸乙酯", "乙醇和乙酸"],
        "knowledge_tags": ["酯化反应"],
        "skill": "edu-chem-reaction",
        "problem_type": "esterification",
        "spec": {},
    },
    {
        "key": "glucose_combustion",
        "title": "葡萄糖有氧氧化（细胞呼吸）",
        "subject": "生物",
        "group": "细胞呼吸",
        "kind": "chem_reaction",
        "keywords": ["葡萄糖", "有氧呼吸", "细胞呼吸", "有氧氧化"],
        "knowledge_tags": ["细胞呼吸", "有氧呼吸", "葡萄糖"],
        "skill": "edu-chem-reaction",
        "problem_type": "glucose_combustion",
        "spec": {},
    },
]

KIND_SUBTITLE = {
    "chem_lab": "动画库 · 选仪器 · 加药品 · 观察现象",
    "solid_explore": "动画库 · 可旋转 3D 探究",
    "curve_explore": "动画库 · 可拖动画板",
    "chem_reaction": "动画库 · 分子 3D 反应",
    "bio_explore": "动画库 · 点击结构 · 看功能",
    "physics_explore": "动画库 · 拖动物体 · 调参看规律",
}


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
            "knowledge_tags": list(_LAB_TAGS.get(e["key"], [])),
            "skill": "edu-chem-lab",
            "problem_type": e["key"],
            "spec": {},
        })
    return rows


def _bio_rows() -> list[dict]:
    from app.services.skill_service import BIO_CATALOG
    rows = []
    for e in BIO_CATALOG:
        rows.append({
            "key": e["key"],
            "title": e["title"],
            "subject": "生物",
            "group": e["group"],
            "kind": "bio_explore",
            "origin": "system",
            "keywords": list(e.get("keywords") or ()),
            "knowledge_tags": list(e.get("knowledge_tags") or []),
            "skill": "edu-bio",
            "problem_type": e["key"],
            "spec": {},
        })
    return rows


def _physics_rows() -> list[dict]:
    from app.services.skill_service import PHYSICS_CATALOG
    rows = []
    for e in PHYSICS_CATALOG:
        rows.append({
            "key": e["key"],
            "title": e["title"],
            "subject": "物理",
            "group": e["group"],
            "kind": "physics_explore",
            "origin": "system",
            "keywords": list(e.get("keywords") or ()),
            "knowledge_tags": list(e.get("knowledge_tags") or []),
            "skill": "edu-physics",
            "problem_type": e["key"],
            "spec": {},
        })
    return rows


def system_catalog() -> list[dict]:
    """全部系统动画（实验台 + 数学探究 + 分子 3D + 生物 / 物理探究）。"""
    rows = _lab_rows()
    for e in _EXTRA_ASSETS:
        rows.append({**e, "origin": "system"})
    rows.extend(_bio_rows())
    rows.extend(_physics_rows())
    return rows


def catalog_for_picker() -> dict:
    """课件下拉用：按科目 · 分组。"""
    items = []
    for e in system_catalog():
        group = e.get("group") or ""
        label = f"{e['subject']} · {group}" if group else e["subject"]
        items.append({"key": e["key"], "title": e["title"], "group": label})
    return {"items": items}


def _dump(val) -> str:
    return json.dumps(val, ensure_ascii=False, sort_keys=True, default=str)


async def ensure_system_labs(db: AsyncSession) -> None:
    """把系统目录灌进库：补缺失行；同步系统行的科目/分组/关键词/spec，不改标题和 HTML。"""
    catalog = system_catalog()
    existing_keys = {r[0] for r in (await db.execute(select(InteractiveAsset.key))).all()}
    sys_rows = list((await db.execute(
        select(InteractiveAsset)
        .where(InteractiveAsset.origin == "system")
        .options(load_only(
            InteractiveAsset.id, InteractiveAsset.key, InteractiveAsset.origin,
            InteractiveAsset.subject, InteractiveAsset.group, InteractiveAsset.kind,
            InteractiveAsset.keywords, InteractiveAsset.knowledge_tags,
            InteractiveAsset.skill, InteractiveAsset.problem_type, InteractiveAsset.spec,
        ))
    )).scalars().all())
    by_key = {r.key: r for r in sys_rows}
    dirty = False
    for spec in catalog:
        row = by_key.get(spec["key"])
        if row:
            for field in _SYNC_FIELDS:
                new_val = spec[field]
                if _dump(getattr(row, field)) != _dump(new_val):
                    setattr(row, field, new_val)
                    dirty = True
            continue
        if spec["key"] in existing_keys:
            continue
        payload = {k: spec[k] for k in (
            "key", "title", "subject", "group", "kind", "origin",
            "keywords", "knowledge_tags", "skill", "problem_type", "spec",
        )}
        db.add(InteractiveAsset(**payload, teacher_id=None, html=None))
        dirty = True
    if dirty:
        await db.commit()


async def get_by_key(db: AsyncSession, key: str) -> InteractiveAsset | None:
    if not key:
        return None
    return (await db.execute(
        select(InteractiveAsset).where(InteractiveAsset.key == key)
    )).scalar_one_or_none()


def to_out(row: InteractiveAsset, *, has_html: bool | None = None) -> dict:
    if has_html is None:
        try:
            has_html = False if "html" in sa_inspect(row).unloaded else bool(row.html)
        except Exception:
            has_html = False
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
        "has_html": bool(has_html),
        "created_at": row.created_at,
    }


_LIST_LOAD = load_only(
    InteractiveAsset.id,
    InteractiveAsset.key,
    InteractiveAsset.title,
    InteractiveAsset.subject,
    InteractiveAsset.group,
    InteractiveAsset.kind,
    InteractiveAsset.origin,
    InteractiveAsset.teacher_id,
    InteractiveAsset.keywords,
    InteractiveAsset.knowledge_tags,
    InteractiveAsset.skill,
    InteractiveAsset.problem_type,
    InteractiveAsset.spec,
    InteractiveAsset.created_at,
)


async def list_assets(
    db: AsyncSession,
    teacher_id: int,
    *,
    subject: str | None = None,
    view_all: bool = False,
) -> list[InteractiveAsset]:
    await ensure_system_labs(db)
    q = select(InteractiveAsset).options(_LIST_LOAD)
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
    q = q.order_by(
        InteractiveAsset.origin.asc(),
        InteractiveAsset.subject.asc(),
        InteractiveAsset.group.asc(),
        InteractiveAsset.id.asc(),
    )
    return list((await db.execute(q)).scalars().all())


async def render_and_store(db: AsyncSession, row: InteractiveAsset) -> str:
    from app.services.skill_service import render_skill_html
    html = await render_skill_html({
        "skill": row.skill,
        "problem_type": row.problem_type,
        "spec": row.spec or {},
    })
    if html:
        row.html = html
        await db.commit()
        await db.refresh(row)
    return html or ""


async def html_for_row(db: AsyncSession, row: InteractiveAsset) -> str:
    stale = False
    if row.kind == "bio_explore":
        stale = not row.html or "edu-sim:1" not in row.html
    elif row.kind == "physics_explore":
        stale = not row.html or "edu-sim:3" not in row.html
    elif row.kind == "chem_lab":
        stale = not row.html or "edu-lab:7" not in row.html
    if row.html and not stale:
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
            "kind": row.kind,
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


def _subject_compatible(subject_name: str, row: dict) -> bool:
    s = subject_name or ""
    subj = row.get("subject") or ""
    if not s:
        return True
    if subj and subj in s:
        return True
    if "科学" in s and row.get("kind") == "chem_lab":
        return True
    return False


def _term_in_text(term: str, text: str) -> bool:
    """中文标签匹配：至少两字才允许子串，避免「圆」打中「椭圆」。"""
    if not term or not text:
        return False
    if len(term) < 2:
        return text == term
    return term in text


def _term_in_names(term: str, names: list[str]) -> bool:
    if not term:
        return False
    for n in names:
        if not n:
            continue
        if n == term or term == n:
            return True
        if len(term) >= 2 and (term in n or (len(n) >= 2 and n in term)):
            return True
    return False


def pick_catalog_keys(points: list[dict], title: str, subject_name: str, limit: int = 2) -> list[str]:
    """按知识点名称 / 关键词给本章挑动画，同分时保留目录顺序。

    只认够强的匹配：标签打中知识点名称，或至少两个区分性关键词。
    避免「酚酞/指示剂」把中和实验台贴到溶液酸碱性课时上。
    """
    point_names = [str(p.get("name") or "") for p in (points or [])]
    name_blob = " ".join([title or "", *point_names])
    explain_parts = []
    for p in points or []:
        explain_parts.append(str(p.get("plain_explanation") or ""))
        explain_parts.append(str(p.get("activity_goal") or ""))
    explain_blob = " ".join(explain_parts)

    scored: list[tuple[int, int, str]] = []
    for i, row in enumerate(system_catalog()):
        if not _subject_compatible(subject_name, row):
            continue
        score = 0
        for t in row.get("knowledge_tags") or []:
            if _term_in_names(t, point_names):
                score += 5
            elif _term_in_text(t, name_blob):
                score += 3
        for w in row.get("keywords") or []:
            if _term_in_text(w, name_blob):
                score += 3
            elif _term_in_text(w, explain_blob):
                score += 1
        # 至少一次标签命中（5）或名称里两个关键词（6）才收下
        if score >= 5:
            scored.append((score, -i, row["key"]))
    scored.sort(reverse=True)
    keys: list[str] = []
    for _, _, key in scored:
        if key not in keys:
            keys.append(key)
        if len(keys) >= limit:
            break
    return keys


def resolve_keys(cw, points: list[dict], title: str, subject_name: str) -> list[str]:
    """出课用：手动选择 > 旧字段 virtual_lab_key > 目录匹配 > 化学实验台兜底。"""
    raw = getattr(cw, "animation_keys", None) or []
    keys = [str(k).strip() for k in raw if str(k).strip()]
    if keys:
        return keys
    explicit = (getattr(cw, "virtual_lab_key", None) or "").strip()
    if explicit:
        return [explicit]
    if not getattr(cw, "want_virtual_lab", False):
        return []
    matched = pick_catalog_keys(points, title, subject_name, limit=1)
    if matched:
        return matched
    # 自动匹配宁可不贴实验台，也不要用制氧等默认实验硬塞进不相关课时
    return []
