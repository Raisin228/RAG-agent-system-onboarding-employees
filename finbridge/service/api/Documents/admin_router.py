"""Эндпоинты для управления документами RAG. Атрошенко Б. С."""

import os
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File

from service.RAG.docs_service import DocsDirectoryIngestion, DOCS_DIR
from service.api.Documents.models import DocumentsListResponse, DocumentsSummary, DocumentEntry, UploadResponse, \
    DeletedChunkDoc, DeleteDocsVectorStore
from service.api.core.responses import BAD_REQUEST

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/documents", response_model=DocumentsListResponse)
def list_documents() -> DocumentsListResponse:
    """Список всех .md документов из docs/ с данными об индексации из Qdrant."""
    docs, summary = DocsDirectoryIngestion.get_documents_info()
    return DocumentsListResponse(
        summary=DocumentsSummary(**summary),
        documents=[
            DocumentEntry(
                filename=d.filename,
                size_kb=d.size_kb,
                chunks_count=d.chunks_count,
                is_indexed=d.is_indexed,
                last_updated=d.last_updated,
            )
            for d in docs
        ],
    )


@router.post("/documents/upload", response_model=UploadResponse, status_code=201)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    """
    Загрузить новый .md документ в хранилище на диске.

    После загрузки файл появится в таблице со статусом "не проиндексирован".
    Для добавления в Qdrant запустите синхронизацию.
    """

    if not (file.filename or "").endswith(".md"):
        raise HTTPException(status_code=400, detail="Принимаются только .md файлы")

    dest = os.path.join(DOCS_DIR, file.filename)
    if os.path.exists(dest):
        raise HTTPException(
            status_code=409,
            detail=f"Файл '{file.filename}' уже существует. Удалите старую версию или переименуйте новую.",
        )

    content = await file.read()
    if not content.strip():
        raise HTTPException(status_code=400, detail="Файл пустой")

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(dest, "wb") as f:
        f.write(content)

    return UploadResponse(
        filename=file.filename,
        size_bytes=len(content),
        message="Файл сохранён. Запустите синхронизацию для индексации в Qdrant.",
    )


@router.delete("/documents/delete", response_model=List[DeletedChunkDoc], responses=BAD_REQUEST)
async def delete_docs(docs_ids: List[DeleteDocsVectorStore]) -> List[DeletedChunkDoc]:
    """
    Получает список идентификаторов [названий]
    документов и удаляет эти доки и все их points из Qdrant.

    :param docs_ids: список из идентификаторов.
    :return список с данными по удалённым документам.
    """

    uniq_docs = set(map(lambda pobj: pobj.required_file_name, docs_ids))
    if not uniq_docs:
        return []

    if any(map(lambda n: not (n or "").endswith(".md"), uniq_docs)):
        raise HTTPException(status_code=400, detail="Принимаются только .md файлы")
    return [DeletedChunkDoc(**statistic) for statistic in DocsDirectoryIngestion.erase_docs(uniq_docs)]

# сделать ручку для переиндексации доков и загрузки существующих доков с ФС
# Разобраться с проблемой роста числа чанков - кажется что это происходит при переинициализации
