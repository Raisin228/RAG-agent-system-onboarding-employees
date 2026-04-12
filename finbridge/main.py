"""Точка входа в API-приложение. Атрошенко Б. С."""
import logging
import uvicorn

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
from service.api.router import router as chat_router

app = FastAPI(
    contact={
        "name": "Bogdan Atroshenko",
        "url": "https://t.me/BogdanAtroshenko",
        "email": "bogdanatrosenko@gmail.com",
    },
    title="FinBridgeRAGSystem 🛟",
)

app.include_router(chat_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

# TODO: добавить возможность физически обновлять RAG базу. Например: при помощи добавления новых документов.
#  В таком случае нужно подумать над обновлением сущ. чанков.
#  - Добавить память для бота
