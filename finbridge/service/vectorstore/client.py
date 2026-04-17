"""Клиент Qdrant. Атрошенко Б. С."""

from config import settings
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from langchain_qdrant import QdrantVectorStore
from langchain_core.vectorstores import VectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from functools import lru_cache


class QdrantService:
    """Синглтон для работы с Qdrant."""

    client = None
    embeddings = None

    @classmethod
    def get(cls) -> QdrantClient:
        """Получить клиента и инициализировать коллекцию Qdrant."""
        if cls.client is None:
            cls.client = QdrantClient(url=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

        if not cls.client.collection_exists(
                collection_name=settings.QDRANT_COLLECTION_NAME
        ):
            # Локальная модель через sentence-transformers, без OpenAI
            cls.embeddings = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDINGS_MODEL_NAME,
                model_kwargs={"local_files_only": True}
            )

            vector_size: int = cls.embeddings._client.get_sentence_embedding_dimension()
            cls.client.create_collection(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )

        return cls.client

    @classmethod
    @lru_cache(maxsize=256)
    def get_qdrant_vector_store(cls) -> VectorStore:
        """
        Клиент для работы с Qdrant данными.

        :return: векторное хранилище.
        """

        return QdrantVectorStore(
            client=QdrantService.get(),
            collection_name=settings.QDRANT_COLLECTION_NAME,
            embedding=cls.embeddings,
        )
