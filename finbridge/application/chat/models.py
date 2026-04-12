"""Модельки запроса | ответа для чата. Атрошенко Б. С."""
from pydantic import BaseModel, Field


class InsightRequest(BaseModel):
    """Вопрос боту в чат."""

    query: str = Field(description="Вопрос пользователя к базе знаний компании", min_length=3)


class SourceDocument(BaseModel):
    """Данные чанка документа, используемые для ответа."""

    content: str = Field(description="Фрагмент документа, использованный при ответе")
    metadata: dict = Field(description="Метаданные документа (источник, заголовок и т.д.)")


class InsightResponse(BaseModel):
    """Финальный ответ, от агента."""

    answer: str = Field(description="Ответ агента на вопрос пользователя")
    sources: list[SourceDocument] = Field(
        description="Список документов из базы знаний, на которые опирался агент",
        default_factory=list,
    )
