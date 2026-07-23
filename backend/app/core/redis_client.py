import redis.asyncio as aioredis
from app.core.config import settings

_redis_client: aioredis.Redis | None = None


def _base_kwargs() -> dict:
    return {
        "encoding": "utf-8",
        "decode_responses": True,
        "socket_connect_timeout": 5,
        "retry_on_timeout": True,
        "health_check_interval": 30,
    }


async def get_redis() -> aioredis.Redis:
    """常规命令（get/set/publish）用短超时即可。"""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            socket_timeout=10,
            **_base_kwargs(),
        )
    return _redis_client


async def create_pubsub_redis() -> aioredis.Redis:
    """Pub/Sub 长连接：listen() 会阻塞等待消息，必须禁用读超时。"""
    return aioredis.from_url(
        settings.REDIS_URL,
        socket_timeout=None,
        **_base_kwargs(),
    )


async def close_redis():
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
