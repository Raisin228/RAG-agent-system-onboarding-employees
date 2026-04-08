"""Настройки из .env. Атрошенко Б. С."""

import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DOTENV = os.path.join(os.path.dirname(__file__), "../.env")


class Settings(BaseSettings):
    """Здесь происходит валидация и агрегация всех ключей и базовых констант."""

    EMBEDDINGS_MODEL_NAME: str = Field(description="Модель используемая в качестве генерации embeddings.", min_length=3)
    QDRANT_HOST: str = Field(description="Хост до контейнера с Qdrant", default="http://localhost")
    QDRANT_PORT: int = Field(description="Порт, на котором слушает Qdrant", default=6333)
    QDRANT_COLLECTION_NAME: str = Field(description="Название основной коллекции документов", min_length=5)

    model_config = SettingsConfigDict(env_file=DOTENV)


settings = Settings()
