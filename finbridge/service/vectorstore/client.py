"""Клиент Qdrant. Атрошенко Б. С."""

from config import settings
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from langchain_qdrant import QdrantVectorStore
from langchain_core.vectorstores import VectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from functools import lru_cache


@lru_cache(maxsize=256)
def get_qdrant_vector_store() -> VectorStore:
    """
    Получение и инициализация векторной БД.

    :return: векторное хранилище.
    """

    # Локальная модель через sentence-transformers, без OpenAI
    embeddings = HuggingFaceEmbeddings(
        model_name=settings.EMBEDDINGS_MODEL_NAME,
        model_kwargs={"local_files_only": True}
    )
    vector_size: int = embeddings._client.get_sentence_embedding_dimension()

    client = QdrantClient(url=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    if not client.collection_exists(
            collection_name=settings.QDRANT_COLLECTION_NAME
    ):
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )

    return QdrantVectorStore(
        client=client,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        embedding=embeddings,
    )
