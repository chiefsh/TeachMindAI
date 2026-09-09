"""Qdrant 异步客户端封装：知识点向量存储，用于语义去重与相似检索。

- 延迟导入 qdrant_client，未安装/未启用时不影响主应用。
- collection 懒创建：首次写入时按向量维度创建（cosine 距离）。
"""
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None            # qdrant_client.AsyncQdrantClient
_collection_ready = False


def _vector_enabled() -> bool:
    return bool(settings.KG_ENABLED)


def _get_client():
    global _client
    if not _vector_enabled():
        return None
    if _client is None:
        from qdrant_client import AsyncQdrantClient  # 延迟导入
        _client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            timeout=15,
        )
    return _client


async def close_qdrant():
    global _client, _collection_ready
    if _client is not None:
        try:
            await _client.close()
        except Exception:  # noqa: BLE001
            pass
        _client = None
        _collection_ready = False


async def ensure_collection(dim: int):
    """确保 collection 存在（懒创建，按实际向量维度）。"""
    global _collection_ready
    client = _get_client()
    if client is None or _collection_ready:
        return
    from qdrant_client.models import Distance, VectorParams
    try:
        exists = await client.collection_exists(settings.KG_COLLECTION)
        if not exists:
            await client.create_collection(
                collection_name=settings.KG_COLLECTION,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
        _collection_ready = True
    except Exception as e:  # noqa: BLE001
        logger.warning("Qdrant collection 初始化失败：%s", e)


async def upsert_vector(point_id: str, vector: list[float], payload: dict) -> None:
    client = _get_client()
    if client is None or not vector:
        return
    await ensure_collection(len(vector))
    from qdrant_client.models import PointStruct
    try:
        await client.upsert(
            collection_name=settings.KG_COLLECTION,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Qdrant 写入失败（%s）：%s", point_id, e)


async def search_similar(
    vector: list[float], flt: dict | None = None, limit: int = 5
) -> list[dict]:
    """按向量检索，flt 为 payload 精确过滤（如 {"subject_id":2}）。
    返回 [{"id":..., "score":..., "payload":...}]。
    """
    client = _get_client()
    if client is None or not vector:
        return []
    await ensure_collection(len(vector))
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    q_filter = None
    if flt:
        q_filter = Filter(must=[
            FieldCondition(key=k, match=MatchValue(value=v)) for k, v in flt.items()
        ])
    try:
        res = await client.search(
            collection_name=settings.KG_COLLECTION,
            query_vector=vector,
            query_filter=q_filter,
            limit=limit,
        )
        return [{"id": str(p.id), "score": p.score, "payload": p.payload or {}} for p in res]
    except Exception as e:  # noqa: BLE001
        logger.warning("Qdrant 检索失败：%s", e)
        return []


async def delete_vector(point_id: str) -> None:
    client = _get_client()
    if client is None:
        return
    from qdrant_client.models import PointIdsList
    try:
        await client.delete(
            collection_name=settings.KG_COLLECTION,
            points_selector=PointIdsList(points=[point_id]),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Qdrant 删除失败（%s）：%s", point_id, e)
