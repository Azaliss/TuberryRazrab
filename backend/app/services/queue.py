import json
from typing import Any, Dict

import redis.asyncio as redis

from app.core.config import settings


class TaskQueue:
    queue_name = "tuberry:tasks"
    personal_queue_name = "tuberry:personal:tasks"
    outbound_prefix = "tuberry:avito:sent"
    outbound_ttl_seconds = 3600 * 12  # 12 часов достаточно для дедупликации
    _client: redis.Redis | None = None

    @classmethod
    def client(cls) -> redis.Redis:
        if cls._client is None:
            cls._client = redis.from_url(settings.redis_url, decode_responses=True)
        return cls._client

    @classmethod
    async def enqueue(cls, task_type: str, payload: Dict[str, Any]) -> None:
        client = cls.client()
        await client.rpush(cls.queue_name, json.dumps({"type": task_type, "payload": payload}))

    @classmethod
    async def dequeue(cls, timeout: int = 5) -> Dict[str, Any] | None:
        client = cls.client()
        item = await client.blpop(cls.queue_name, timeout=timeout)
        if not item:
            return None
        _, data = item
        return json.loads(data)

    @classmethod
    async def enqueue_personal(cls, task_type: str, payload: Dict[str, Any]) -> None:
        client = cls.client()
        await client.rpush(cls.personal_queue_name, json.dumps({"type": task_type, "payload": payload}))

    @classmethod
    async def dequeue_personal(cls, timeout: int = 5) -> Dict[str, Any] | None:
        client = cls.client()
        item = await client.blpop(cls.personal_queue_name, timeout=timeout)
        if not item:
            return None
        _, data = item
        return json.loads(data)

    @classmethod
    async def remember_outbound_message(
        cls,
        message_id: str,
        *,
        account_id: int,
        dialog_id: str,
        ttl: int | None = None,
    ) -> None:
        if not message_id:
            return
        client = cls.client()
        key = f"{cls.outbound_prefix}:{message_id}"
        payload = json.dumps({"account_id": account_id, "dialog_id": dialog_id})
        await client.set(key, payload, ex=ttl or cls.outbound_ttl_seconds)

    @classmethod
    async def pop_outbound_message(cls, message_id: str) -> Dict[str, Any] | None:
        if not message_id:
            return None
        client = cls.client()
        key = f"{cls.outbound_prefix}:{message_id}"
        pipe = client.pipeline()
        pipe.get(key)
        pipe.delete(key)
        result = await pipe.execute()
        raw = result[0] if result else None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
