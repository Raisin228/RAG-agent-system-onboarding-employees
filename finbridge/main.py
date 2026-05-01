"""Точка входа в API-приложение. Атрошенко Б. С."""
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn

from fastapi import FastAPI
from service.api.chat import router as chat_router
from service.api.Documents import router as docs_router
from service.broker import result_store, publisher, consumer
from service.broker.handlers import handle_text_task, handle_voice_task


@asynccontextmanager
async def lifespan(_application: FastAPI):
    """Код исполняемый до | после запуска приложения."""
    logging.basicConfig(level=logging.INFO)

    await publisher.connect()  # Публикация задач со стороны API endpoint в RabbitMQ.
    await result_store.connect()  # Отправка результатов генерации в Redis Pub | Sub канал и вычитка этих данных.
    await consumer.connect()  # RabbitMQ worker, который будет разгребать задачи.
    # В фоне запускаю прослушку очереди. Средствами consumer в RabbitMQ. Формально я один раз прогоняю start_consuming,
    # но фактически я подписываю workerов на определённые callback.
    consume_task = asyncio.create_task(
        consumer.start_consuming(text_handler=handle_text_task, voice_handler=handle_voice_task)
    )
    yield
    await publisher.close()
    await result_store.close()
    await consumer.close()


app = FastAPI(
    contact={
        "name": "Bogdan Atroshenko",
        "url": "https://t.me/BogdanAtroshenko",
        "email": "bogdanatrosenko@gmail.com",
    },
    title="FinBridgeRAGSystem 🛟",
    lifespan=lifespan
)

app.include_router(chat_router)
app.include_router(docs_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

# TODO: добавить возможность физически обновлять RAG базу. Например: при помощи добавления новых документов.
#  В таком случае нужно подумать над обновлением сущ. чанков.
#  - Добавить роли и доступы. Чтоб не все могли менять структуру документов.
#  - Проверить что временные файлы удаляются и задачи после выполнения rabbitmq удаляются
#  - Перевести на MLX модель. Иначе это пиздец как долго думает
