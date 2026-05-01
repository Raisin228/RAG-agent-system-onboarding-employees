"""Инфраструктура брокера через Redis Pub/Sub хранилище. Атрошенко Б. С."""

import json
import logging
from collections.abc import AsyncGenerator

import redis.asyncio as aio_redis

from config import settings

logger = logging.getLogger(__name__)

_CHANNEL_PREFIX = "llm:result:"


class RedisResultStore:
    """Публикует LLM-события и стримит их через Redis Pub/Sub."""

    def __init__(self) -> None:
        """Инициализатор."""

        self._client: aio_redis.Redis | None = None

    async def connect(self) -> None:
        """Настройка и подключение клиента redis."""

        self._client = await aio_redis.from_url(settings.REDIS_URL, decode_responses=True)
        logger.info("[ResultStore] подключён к Redis")

    async def publish_event(self, task_id: str, event: dict) -> None:
        """
        Опубликовать результат генерации LLM в канал задачи. Используется обработчиками RabbitMQ.

        :param task_id: Id задачи. Нужен для инициализации канала.
        :param event: Результат гененрации.
        :return:
        """

        await self._client.publish(
            channel=f"{_CHANNEL_PREFIX}{task_id}",
            message=json.dumps(event, ensure_ascii=False),
        )

    @staticmethod
    async def stream_events(task_id: str) -> AsyncGenerator[str, None]:
        """
        Подписывается на канал задачи и отдаёт события в виде JSON-строк. Используется в endpoints.

        Завершается после события типа "done" или "error".

        :param task_id: ID задачи, на канал которой подписываюсь.
        """

        channel = f"{_CHANNEL_PREFIX}{task_id}"
        # Отдельный клиент на каждый SSE-запрос — pubsub требует выделенного соединения
        client = await aio_redis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                raw: str = message["data"]
                yield raw
                if json.loads(raw).get("type") in ("done", "error"):
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            await client.aclose()

    async def close(self) -> None:
        """Закрывает соединение с Redis каналом."""

        if self._client:
            await self._client.aclose()
            logger.info("[ResultStore] соединение с Redis закрыто")


result_store = RedisResultStore()
