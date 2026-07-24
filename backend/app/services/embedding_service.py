"""文本向量嵌入服务：为知识点生成 embedding，用于语义去重与相似检索。

使用 LiteLLM 统一接口调用嵌入模型。若未配置 EMBEDDING_MODEL 或调用失败，
返回 None，上层退化为按名称精确匹配。
"""
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def embedding_enabled() -> bool:
    return bool(settings.KG_ENABLED and settings.EMBEDDING_MODEL)


async def embed_text(
    text: str,
    *,
    api_base: str | None = None,
    api_key: str | None = None,
) -> list[float] | None:
    """对单段文本生成向量。失败或未启用时返回 None。

    api_base/api_key 为可选覆盖：当未在 EMBEDDING_API_BASE/KEY 单独配置时，
    上层可传入教师默认 LLM 网关的 base_url/api_key 复用同一网关。
    """
    if not embedding_enabled() or not (text or "").strip():
        return None
    from app.core.proxy import sanitize_proxy_env
    sanitize_proxy_env()
    import litellm

    base = settings.EMBEDDING_API_BASE or api_base
    key = settings.EMBEDDING_API_KEY or api_key
    model = settings.EMBEDDING_MODEL
    # 自建/兼容网关（有 base_url 且模型名未带 provider 前缀）走 openai 兼容通道
    if base and "/" not in model:
        model = f"openai/{model}"
    try:
        kwargs: dict = {"model": model, "input": [text[:4000]]}
        if base:
            kwargs["api_base"] = base
        if key:
            kwargs["api_key"] = key
        resp = await litellm.aembedding(**kwargs)
        data = resp["data"] if isinstance(resp, dict) else resp.data
        vec = data[0]["embedding"] if isinstance(data[0], dict) else data[0].embedding
        return list(vec)
    except Exception as e:  # noqa: BLE001
        logger.warning("嵌入生成失败（model=%s）：%s", settings.EMBEDDING_MODEL, e)
        return None
