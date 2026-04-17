"""Модельки для запроса | ответа по документам. Атрошенко Б. С."""
from pydantic import BaseModel, Field


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
    """Новый документ загружен в RAG."""

    filename: str
    size_bytes: int
    message: str


class RequiredDocsInteraction(BaseModel):
    """Отправить запрос на удаление | переиндексаци документа из хранилища."""

    required_file_name: str = Field(description="Требуемый файл. С расширением md", default="text.md")


class DeletedChunkDoc(BaseModel):
    """Статистика по удалённым чанкам в рамках одного документа."""

    filename: str = Field(description="Название файла + расширение", default="some.md")
    found: bool = Field(description="Нашёлся ли такой документ?", default=False)
    deleted_chunks: int = Field(description="Кол-во удалённых chunks | points", default=0)
    deleted_FS: bool = Field(description="Был ли удалён документ с ФС?", default=False)
