"""Модельки для запроса | ответа по документам. Атрошенко Б. С."""
from pydantic import BaseModel


class DocumentEntry(BaseModel):
    """Данные по одному документу."""

    filename: str
    size_kb: float
    chunks_count: int
    is_indexed: bool
    last_updated: str


class DocumentsSummary(BaseModel):
    """Общая статистика по документам в хранилище."""

    total_docs: int
    total_chunks: int
    indexed_count: int
    indexed_pct: int


class DocumentsListResponse(BaseModel):
    """Финальный ответ по списку доков."""

    summary: DocumentsSummary
    documents: list[DocumentEntry]


class UploadResponse(BaseModel):
    """Выгрузить новый документ в RAG."""

    filename: str
    size_bytes: int
    message: str
