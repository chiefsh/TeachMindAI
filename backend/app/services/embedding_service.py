"""文本向量嵌入：知识点语义去重与相似检索。

配置优先读教师「系统设置 → 模型设置 → 向量嵌入」；未保存过则回退环境变量。
未配置或调用失败时返回 None，上层按名称精确匹配。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_SETTING_KEY = "embedding"


@dataclass
class EmbeddingGateway:
    model: str
    api_base: str | None = None
    api_key: str | None = None
    dim: int = 1024


def embedding_enabled(gw: EmbeddingGateway | None = None) -> bool:
    if not settings.KG_ENABLED:
        return False
    if gw is not None:
        return bool(gw.model)
    return bool(settings.EMBEDDING_MODEL)


async def _default_llm_gateway(db: AsyncSession, teacher_id: int) -> tuple[str | None, str | None]:
    from app.core.security import decrypt_api_key
    from app.services.ai_service import _get_default_llm
    try:
        cfg = await _get_default_llm(teacher_id, db)
    except Exception:  # noqa: BLE001
        return None, None
    if not cfg:
        return None, None
    key = decrypt_api_key(cfg.api_key_encrypted) if cfg.api_key_encrypted else None
    return (cfg.base_url or None), key


async def load_embedding_row(db: AsyncSession, teacher_id: int):
    from app.models.teacher_setting import TeacherSetting
    rec = (
        await db.execute(
            select(TeacherSetting).where(
                TeacherSetting.teacher_id == teacher_id,
                TeacherSetting.key == EMBEDDING_SETTING_KEY,
            )
        )
    ).scalar_one_or_none()
    return rec


async def resolve_embedding(db: AsyncSession, teacher_id: int) -> EmbeddingGateway | None:
    """教师设置 > 环境变量。已保存但关闭/无模型名则禁用，不再回退 env。"""
    if not settings.KG_ENABLED:
        return None
    rec = await load_embedding_row(db, teacher_id)
    val = rec.value if rec and isinstance(rec.value, dict) else None
    llm_base, llm_key = await _default_llm_gateway(db, teacher_id)

    if val is not None:
        if not val.get("enabled", True):
            return None
        model = str(val.get("model") or "").strip()
        if not model:
            return None
        use_gw = bool(val.get("use_llm_gateway"))
        base = str(val.get("base_url") or "").strip() or None
        key = None
        enc = val.get("api_key_encrypted")
        if enc:
            from app.core.security import decrypt_api_key
            try:
                key = decrypt_api_key(enc)
            except Exception:  # noqa: BLE001
                key = None
        if use_gw:
            base = base or llm_base
            key = key or llm_key
        else:
            base = base or (settings.EMBEDDING_API_BASE or None) or llm_base
            key = key or (settings.EMBEDDING_API_KEY or None) or llm_key
        try:
            dim = int(val.get("dim") or settings.EMBEDDING_DIM or 1024)
        except (TypeError, ValueError):
            dim = settings.EMBEDDING_DIM or 1024
        return EmbeddingGateway(model=model, api_base=base, api_key=key, dim=dim)

    model = (settings.EMBEDDING_MODEL or "").strip()
    if not model:
        return None
    return EmbeddingGateway(
        model=model,
        api_base=(settings.EMBEDDING_API_BASE or None) or llm_base,
        api_key=(settings.EMBEDDING_API_KEY or None) or llm_key,
        dim=settings.EMBEDDING_DIM or 1024,
    )


async def embed_text(
    text: str,
    *,
    model: str | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    gateway: EmbeddingGateway | None = None,
) -> list[float] | None:
    """对单段文本生成向量。失败或未启用时返回 None。"""
    if gateway:
        model = gateway.model
        api_base = gateway.api_base
        api_key = gateway.api_key
    resolved = (model or "").strip()
    if not settings.KG_ENABLED or not resolved or not (text or "").strip():
        return None
    from app.core.proxy import sanitize_proxy_env
    sanitize_proxy_env()
    import litellm

    base = api_base or (settings.EMBEDDING_API_BASE or None)
    key = api_key or (settings.EMBEDDING_API_KEY or None)
    litellm_model = resolved
    if base and "/" not in litellm_model:
        litellm_model = f"openai/{litellm_model}"
    try:
        kwargs: dict = {"model": litellm_model, "input": [text[:4000]]}
        if base:
            kwargs["api_base"] = base
        if key:
            kwargs["api_key"] = key
        resp = await litellm.aembedding(**kwargs)
        data = resp["data"] if isinstance(resp, dict) else resp.data
        vec = data[0]["embedding"] if isinstance(data[0], dict) else data[0].embedding
        return list(vec)
    except Exception as e:  # noqa: BLE001
        logger.warning("嵌入生成失败（model=%s）：%s", resolved, e)
        return None
