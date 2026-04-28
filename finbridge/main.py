"""Точка входа в API-приложение. Атрошенко Б. С."""
import logging
from contextlib import asynccontextmanager

import uvicorn

from fastapi import FastAPI
from service.api.chat import router as chat_router
from service.api.Documents import router as docs_router


@asynccontextmanager
async def lifespan(_application: FastAPI):
    """Код исполняемый до | после запуска приложения."""
    logging.basicConfig(level=logging.INFO)
    yield


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
#  - Почистить стриминг
#  - Добавить RabbitMQ в voice_insight. Транскрибация долгая CPU задача. Нет смысла блокировать HTTP-поток
#  - Перевести на MLX модель. Иначе это пиздец как долго думает
