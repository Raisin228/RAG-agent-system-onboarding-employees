"""Точка входа в API-приложение. Атрошенко Б. С."""
import logging
from contextlib import asynccontextmanager

import uvicorn

from fastapi import FastAPI
from service.api.router import router as chat_router


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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

# TODO: добавить возможность физически обновлять RAG базу. Например: при помощи добавления новых документов.
#  В таком случае нужно подумать над обновлением сущ. чанков.
#  - Добавить память для бота
