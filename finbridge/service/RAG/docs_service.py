"""Серивис загрузки, индексация и работы с докуменами на ФС. Атрошенко Б. С."""

import os
import logging
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.vectorstores import VectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dataclasses import dataclass
from datetime import datetime

from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, FilterSelector

from config import settings
from qdrant_client import QdrantClient

from service.vectorstore.client import QdrantService

DOCS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../docs")
)

logger = logging.getLogger(__name__)


@dataclass
class DocumentInfo:
    """Базовая сводка информации по документу."""

    filename: str
    chunks_count: int
    is_indexed: bool
    last_updated: str  # "YYYY-MM-DD HH:MM"
    size_kb: float


class DocsDirectoryIngestion:
    """Загрузчик документов из директории."""

    @staticmethod
    def docs_load() -> None:
        """Загрузить документы из директории."""

        loader = DirectoryLoader(
            DOCS_DIR,
            glob="**/*.md",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=True,
        )
        docs = loader.load()
        print(f"Загружено документов: {len(docs)}")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=64,
            separators=["\n", " ", "."],
        )
        chunks = splitter.split_documents(docs)
        print(f"Чанков после разбивки: {len(chunks)}")

        vector_store: VectorStore = QdrantService.get_qdrant_vector_store()
        vector_store.add_documents(chunks)
        print("Индексация завершена.")

    @staticmethod
    def erase_docs(doc_names: set):
        """
        Выполнить весь цикл удаления:
            * Удалить пойнты из Qdrant.
            * Удалить доки из ФС.

        :param doc_names: множ-во названий доков.
        """

        res = []
        doc_names = list(doc_names)
        # удалил из Qdrant'а + удалил с ФС
        for doc in doc_names:
            removed_chunks = DocsDirectoryIngestion._rm_points_by_source(doc)
            fs_remove_resp = DocsDirectoryIngestion._rm_doc_file_system(doc)

            removed_chunks["deleted_FS"] = fs_remove_resp.get("deleted_FS")
            res.append(removed_chunks)

        return res

    @staticmethod
    def get_documents_info() -> tuple[list[DocumentInfo], dict]:
        """
        Возвращает список документов из docs/ с данными об индексации Qdrant.

        Если Qdrant недоступен или коллекция не существует —
        все документы показываются с is_indexed=False.

        :return: (список DocumentInfo, сводная статистика)
        """

        # прохожусь по коллекции и считаю кол-во чанков у каждого документа
        indexed_chunks: dict[str, int] = {}
        try:
            client = QdrantService.get()
            if client.collection_exists(settings.QDRANT_COLLECTION_NAME):
                indexed_chunks = DocsDirectoryIngestion._get_chunks_by_filename(client)
        except Exception:
            pass

        docs: list[DocumentInfo] = []

        # для каждого документа считаю статистику
        if os.path.isdir(DOCS_DIR):
            for fname in sorted(os.listdir(DOCS_DIR)):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(DOCS_DIR, fname)
                stat = os.stat(fpath)
                last_updated = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                size_kb = round(stat.st_size / 1024, 1)
                chunks = indexed_chunks.get(fname, 0)
                docs.append(DocumentInfo(
                    filename=fname,
                    chunks_count=chunks,
                    is_indexed=chunks > 0,
                    last_updated=last_updated,
                    size_kb=size_kb,
                ))

        # информация по всем документам
        total_docs = len(docs)
        total_chunks = sum(d.chunks_count for d in docs)
        indexed_count = sum(1 for d in docs if d.is_indexed)
        indexed_pct = round(indexed_count / total_docs * 100) if total_docs > 0 else 0

        summary = {
            "total_docs": total_docs,
            "total_chunks": total_chunks,
            "indexed_count": indexed_count,
            "indexed_pct": indexed_pct,
        }
        return docs, summary

    @staticmethod
    def _get_chunks_by_filename(client: QdrantClient) -> dict[str, int]:
        """
        Прохожусь по коллекции Qdrant и считаю чанки для каждого файла.

        LangChain сохраняет путь к файлу в payload["metadata"]["source"].
        Сравнение по basename.

        :return: {basename_файла: количество_чанков}
        """
        counts: dict[str, int] = {}
        offset = None

        while True:
            results, offset = client.scroll(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                with_payload=["metadata"],
                limit=256,
                offset=offset,
            )
            for point in results:
                payload = point.payload or {}
                source = payload.get("metadata", {}).get("source", "")
                if source:
                    name = os.path.basename(source)
                    counts[name] = counts.get(name, 0) + 1

            if offset is None:
                break

        return counts

    @staticmethod
    def _rm_doc_file_system(doc: str) -> dict:
        """
        Удаляю документ с ФС.

        :param doc: название удаляемого документа.
        :return удалось ли удалить док.
        """

        path = Path(DOCS_DIR) / doc
        if path.exists():
            path.unlink()
            return {"filename": doc, "deleted_FS": True}
        return {"filename": doc, "deleted_FS": False}

    @staticmethod
    def _rm_points_by_source(file_name: str) -> dict:
        """
        Удалить все точки из Qdrant, относящиеся к файлу file_name.

        :param file_name: название файла, чанки которого мы должны удалить.
        :return: словарь с результатами удаления.
        """
        full_path = os.path.join(DOCS_DIR, file_name)
        client = QdrantService.get()
        filter_chunks = Filter(
            must=[FieldCondition(key="metadata.source", match=MatchValue(value=full_path))]
        )

        chunks_before, _ = client.scroll(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            scroll_filter=filter_chunks
        )

        if not chunks_before:
            return {"filename": file_name, "deleted_chunks": 0, "found": False}

        try:
            client.delete(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points_selector=FilterSelector(filter=filter_chunks)
            )
        except UnexpectedResponse:
            logger.error("Не удалось выполнить удаление чанков документа. Вероятнр указано не верное хранилище!")
        return {"filename": file_name, "deleted_chunks": len(chunks_before), "found": True}


DocsDirectoryIngestion.docs_load()
