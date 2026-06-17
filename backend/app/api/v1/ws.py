"""WebSocket：任务进度推送"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.redis_client import get_redis
import asyncio, json

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/task/{task_id}")
async def task_progress(websocket: WebSocket, task_id: str):
    """订阅 Celery 任务进度，结果通过 Redis pubsub 推送"""
    await websocket.accept()
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"task_progress:{task_id}")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"task_progress:{task_id}")
        await pubsub.close()


@router.websocket("/ping")
async def ping(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_text("pong")
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        pass
