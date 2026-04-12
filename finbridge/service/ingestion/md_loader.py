"""Ingestion: загрузка и индексация MD-документов в Qdrant. Атрошенко Б. С."""

import os

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.vectorstores import VectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from service.vectorstore.client import get_qdrant_vector_store

DOCS_DIR = os.path.join(os.path.dirname(__file__), "../docs")


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

        vector_store: VectorStore = get_qdrant_vector_store()
        vector_store.add_documents(chunks)
        print("Индексация завершена.")


DocsDirectoryIngestion.docs_load()
