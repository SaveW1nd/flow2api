import asyncio
import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis
from app.core.security import ACCESS_TOKEN, decode_token
from app.models.generation import GenerationTask
from app.services.progress import CHANNEL, get_snapshot

router = APIRouter(tags=["ws"])


async def _authorize(token: str | None, public_id: str) -> bool:
    if not token:
        return False
    payload = decode_token(token)
    if not payload or payload.get("type") != ACCESS_TOKEN:
        return False
    user_id = int(payload["sub"])
    async with AsyncSessionLocal() as db:
        task = await db.scalar(
            select(GenerationTask).where(GenerationTask.public_id == public_id)
        )
        return bool(task and task.user_id == user_id)


@router.websocket("/ws/tasks/{public_id}")
async def task_progress(websocket: WebSocket, public_id: str, token: str | None = Query(None)):
    if not await _authorize(token, public_id):
        await websocket.close(code=4401)
        return

    await websocket.accept()

    snapshot = await get_snapshot(public_id)
    if snapshot:
        await websocket.send_text(json.dumps(snapshot, ensure_ascii=False))
        if snapshot.get("status") in ("succeeded", "failed", "cancelled"):
            await websocket.close()
            return

    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL.format(public_id=public_id))
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30)
            if message and message.get("type") == "message":
                data = message["data"]
                await websocket.send_text(data)
                try:
                    parsed = json.loads(data)
                    if parsed.get("status") in ("succeeded", "failed", "cancelled"):
                        break
                except json.JSONDecodeError:
                    pass
            else:
                # keepalive ping
                await websocket.send_text(json.dumps({"type": "ping"}))
            await asyncio.sleep(0)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(CHANNEL.format(public_id=public_id))
        await pubsub.aclose()
        try:
            await websocket.close()
        except RuntimeError:
            pass
