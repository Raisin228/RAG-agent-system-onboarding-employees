"""RabbitMQ producer для публикации задач. Атрошенко Б. С."""
import logging

import aio_pika
from aio_pika import ExchangeType, DeliveryMode

from config import settings
from service.broker.const import EXCHANGE
from service.broker.models import TextTask, VoiceTask

logger = logging.getLogger(__name__)

_TEXT_ROUTING_KEY = "task.text"
_VOICE_ROUTING_KEY = "task.voice"


class RabbitMQPublisher:
    """Публикует задачи в RabbitMQ через DIRECT exchange."""

    def __init__(self) -> None:
        """Инициализатор."""

        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.RobustChannel | None = None
        self._exchange: aio_pika.Exchange | None = None

    async def connect(self) -> None:
        """Подключение к брокеру. Инициализация канала и обменника."""

        self._connection = await aio_pika.connect_robust(settings.m_queue_url)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            EXCHANGE, ExchangeType.DIRECT, durable=True
        )
        # Объявляем очереди, чтобы они существовали к моменту публикации
        text_q = await self._channel.declare_queue("finbridge.text", durable=True)
        voice_q = await self._channel.declare_queue("finbridge.voice", durable=True)
        await text_q.bind(self._exchange, routing_key=_TEXT_ROUTING_KEY)
        await voice_q.bind(self._exchange, routing_key=_VOICE_ROUTING_KEY)
        logger.info("[Publisher] подключён к RabbitMQ")

    async def publish_text_task(self, task: TextTask) -> None:
        """
        Публикация текстовой задачи.

        :param task: задача на публикацию.
        """

        await self._exchange.publish(
            aio_pika.Message(
                body=task.model_dump_json().encode(),
                delivery_mode=DeliveryMode.PERSISTENT,  # сообщение сохраняется на диск. Переживёт перезапуск
            ),
            routing_key=_TEXT_ROUTING_KEY,
        )
        logger.info(f"[Publisher] text task {task.task_id} опубликована")

    async def publish_voice_task(self, task: VoiceTask) -> None:
        """
        Публикация задачи на транскрибацию аудио.

        :param task: голосовая задача.
        :return:
        """

        await self._exchange.publish(
            aio_pika.Message(
                body=task.model_dump_json().encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
            ),
            routing_key=_VOICE_ROUTING_KEY,
        )
        logger.info(f"[Publisher] voice task {task.task_id} опубликована")

    async def close(self) -> None:
        """
        Закрыть подключение.

        :return:
        """

        if self._connection:
            await self._connection.close()
            logger.info("[Publisher] соединение с RabbitMQ закрыто")


publisher = RabbitMQPublisher()
