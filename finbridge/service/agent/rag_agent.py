"""Инструменты и агент. Атрошенко Б. С."""
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_ollama import ChatOllama

from config import settings
from service.utils import load_prompt
from service.vectorstore.client import get_qdrant_vector_store

logger = logging.getLogger(__name__)


def retrieve_context(usr_req: dict) -> dict:
    """
    Извлеч похожие на запрос чанки из Qdrant.

    :param usr_req: запрос на поиск.
    :return: удобное строковое представление набранных чанков и список самих документов.
    """
    logger.info("[RAG] retrieve_context вызван с query=%r", usr_req["question"])
    retrieved_docs = get_qdrant_vector_store().similarity_search(usr_req.get('question'), k=10)
    logger.info("[RAG] найдено чанков: %d", len(retrieved_docs))
    serialized = "\n\n".join(
        f"Source: {doc.metadata}\nContent: {doc.page_content}"
        for doc in retrieved_docs
    )
    return {**usr_req, "context": serialized, "docs": retrieved_docs}


model = ChatOllama(model=settings.MODEL, temperature=0, num_predict=4096)

prompt = ChatPromptTemplate.from_messages([
    ("system", load_prompt("../prompts/rag_tools_explain.txt")),
    ("user", "Context: \n{context}\n\nQuestion: {question}")
])

chain = (
        RunnableLambda(retrieve_context)
        | RunnableParallel(
    answer=prompt | model, docs=RunnableLambda(lambda x: x["docs"])
)
)
