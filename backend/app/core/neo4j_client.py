"""Neo4j 异步客户端封装：知识图谱的图存储。

- 延迟导入 neo4j 驱动，未安装或未启用时不影响主应用启动。
- 提供单例 driver、schema 初始化、以及 read/write 执行助手。
"""
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_driver = None  # neo4j.AsyncDriver


def _get_driver():
    """获取（并缓存）异步 Neo4j 驱动。未启用则返回 None。"""
    global _driver
    if not settings.KG_ENABLED:
        return None
    if _driver is None:
        from neo4j import AsyncGraphDatabase  # 延迟导入
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_lifetime=3600,
        )
    return _driver


async def close_neo4j():
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def run_write(cypher: str, params: dict | None = None) -> list[dict]:
    """执行写事务，返回记录字典列表。"""
    driver = _get_driver()
    if driver is None:
        return []
    async with driver.session(database=settings.NEO4J_DATABASE) as session:
        result = await session.execute_write(_collect, cypher, params or {})
        return result


async def run_read(cypher: str, params: dict | None = None) -> list[dict]:
    """执行读事务，返回记录字典列表。"""
    driver = _get_driver()
    if driver is None:
        return []
    async with driver.session(database=settings.NEO4J_DATABASE) as session:
        result = await session.execute_read(_collect, cypher, params or {})
        return result


async def _collect(tx, cypher: str, params: dict) -> list[dict]:
    res = await tx.run(cypher, **params)
    records = [r.data() async for r in res]
    return records


async def init_schema():
    """创建唯一约束与索引（幂等）。"""
    if not settings.KG_ENABLED:
        return
    stmts = [
        "CREATE CONSTRAINT kp_id IF NOT EXISTS "
        "FOR (k:KnowledgePoint) REQUIRE k.id IS UNIQUE",
        "CREATE CONSTRAINT concept_id IF NOT EXISTS "
        "FOR (c:Concept) REQUIRE c.id IS UNIQUE",
        "CREATE INDEX kp_teacher IF NOT EXISTS "
        "FOR (k:KnowledgePoint) ON (k.teacher_id)",
        "CREATE INDEX kp_subject IF NOT EXISTS "
        "FOR (k:KnowledgePoint) ON (k.subject_id)",
        "CREATE INDEX kp_name IF NOT EXISTS "
        "FOR (k:KnowledgePoint) ON (k.name)",
    ]
    for s in stmts:
        try:
            await run_write(s)
        except Exception as e:  # noqa: BLE001
            logger.warning("Neo4j schema 初始化失败：%s", e)


async def ping() -> bool:
    try:
        rows = await run_read("RETURN 1 AS ok")
        return bool(rows and rows[0].get("ok") == 1)
    except Exception as e:  # noqa: BLE001
        logger.warning("Neo4j 连接失败：%s", e)
        return False
