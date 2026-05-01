"""Настройки из .env. Атрошенко Б. С."""

import os
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DOTENV = os.path.join(os.path.dirname(__file__), "../.env")


class Settings(BaseSettings):
    """Здесь происходит валидация и агрегация всех ключей и базовых констант."""

    # Конфиги векторной БД
    EMBEDDINGS_MODEL_NAME: str = Field(
        description="Модель используемая в качестве генерации embeddings.",
        min_length=3,
        default="BAAI/bge-small-en"
    )
    QDRANT_HOST: str = Field(description="Хост до контейнера с Qdrant", default="http://localhost")
    QDRANT_PORT: int = Field(description="Порт, на котором слушает Qdrant", default=6333)
    QDRANT_COLLECTION_NAME: str = Field(
        description="Название основной коллекции документов", min_length=5, default="finbridge_docs"
    )

    # Конфиги Redis [TTL = 1час]
    REDIS_URL: str = Field(description="Урл для экземпляра Redis", default="redis://localhost:6379")
    REDIS_TTL: int = Field(description="Время, в рамках которой хранится история чата в key-value DB", default=60 * 60)

    # Конфиги LLM модели
    AI_API_KEY: str = Field(description="Апи ключик к LLM провайдеру", default="ollama")
    BASE_URL: str = Field(description="УРЛ, на котором локально развёрнута ollama", default="http://localhost:11434")
    MODEL: str = Field(description="Модель используемая под капотом агента", default="deepseek-r1:1.5b")

    # Конфиги Whisper
    WHISPER_MODEL: Literal["tiny", "base", "small", "medium", "large"] = Field(
        description="Размер используемой модели", default="base"
    )

    # Настройки RabbitMQ
    RABBITMQ_USER: str = Field(description="Логин для входа в RabbitMQ", default="guest")
    RABBITMQ_PASS: str = Field(description="Пароль для входа в RabbitMQ", default="guest")
    RABBITMQ_HOST: str = Field(description="Хост для кролика", default="localhost")
    RABBITMQ_PORT: int = Field(description="AMQP-порт для RabbitMQ", default=5672)

    # Настройки Frontend
    API_URL: str = Field(description="Ссылка на UI-чат", default="http://localhost:8000")
    GRADIO_PORT: int = Field(description="Порт для Градио", default=7860)

    @property
    def m_queue_url(self):
        """URL брокера сообщений."""

        return (
            f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASS}"
            f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"
        )

    model_config = SettingsConfigDict(env_file=DOTENV)


settings = Settings()
