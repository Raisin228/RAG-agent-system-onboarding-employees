"""RabbitMQ consumer для чтения и диспетчеризации задач. Атрошенко Б. С."""
import logging
from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika import ExchangeType

from config import settings
from service.broker.const import EXCHANGE

logger = logging.getLogger(__name__)

# Ф-ия обработчик, которую можно вызвать. Аргументы - байты, await объект.
MessageHandler = Callable[[bytes], Awaitable[None]]


class RabbitMQConsumer:
    """Читает задачи из очередей RabbitMQ и вызывает соответствующие обработчики."""

    def __init__(self) -> None:
        """Инициализатор."""

        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.RobustChannel | None = None

    async def connect(self) -> None:
        """Подключение к очереди."""

        self._connection = await aio_pika.connect_robust(settings.m_queue_url)
        self._channel = await self._connection.channel()
        # prefetch_count=1 — воркер берёт одну задачу за раз
        await self._channel.set_qos(prefetch_count=1)
        logger.info("[Consumer] подключён к RabbitMQ")

    async def start_consuming(
            self,
            text_handler: MessageHandler,
            voice_handler: MessageHandler,
    ) -> None:
        """
        Подписывается на обе очереди и запускает прослушку.

        :param text_handler: обработчик, который сработает при задаче на генерацию исходя из текстового вопроса.
        :param voice_handler: обработчик, голосового ввода.
        :return:
        """

        # 2ой раз я не создаю повторно обменник и очередь. Если очереди уже есть, а они есть, т.к их
        # создали в publisher, подключаюсь к ним.
        exchange = await self._channel.declare_exchange(
            EXCHANGE, ExchangeType.DIRECT, durable=True
        )
        text_q = await self._channel.declare_queue("finbridge.text", durable=True)
        voice_q = await self._channel.declare_queue("finbridge.voice", durable=True)
        await text_q.bind(exchange, routing_key="task.text")
        await voice_q.bind(exchange, routing_key="task.voice")

        async def _on_text(msg: aio_pika.IncomingMessage) -> None:
            """CallBack ф-ия. Вернёт ack в Rabbit, если сообщение обработается успешно."""

            async with msg.process():
                await text_handler(msg.body)

        async def _on_voice(msg: aio_pika.IncomingMessage) -> None:
            """
            Регистрирую ф-ию, которую будет вызывать RabbitMQ, сразу, как только появится сообщение.
            + Делаю так из-за управления ACK | NACK логикой. Rabbit должен знать результат выполнения обработчика.
            + Нужна конвертация в bytes.
            """

            async with msg.process():
                await voice_handler(msg.body)

        # Consumer. Подписываюсь на очереди и указываю обработчика.
        await text_q.consume(_on_text)
        await voice_q.consume(_on_voice)
        logger.info("[Consumer] слушает finbridge.text и finbridge.voice")

    async def close(self) -> None:
        """Закрываем подключение."""

        if self._connection:
            await self._connection.close()
            logger.info("[Consumer] соединение закрыто")


consumer = RabbitMQConsumer()
