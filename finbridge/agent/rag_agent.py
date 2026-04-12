"""Инструменты и агент. Атрошенко Б. С."""
from langchain.agents import create_agent
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

from config import settings
from utils import load_prompt
from vectorstore.client import get_qdrant_vector_store


@tool(response_format="content_and_artifact")
def retrieve_context(query: str) -> tuple[str, list[Document]]:
    """
    Извлеч похожие на запрос чанки из Qdrant.

    :param query: запрос на поиск.
    :return: удобное строковое представление набранных чанков и список самих документов.
    """
    retrieved_docs = get_qdrant_vector_store().similarity_search(query, k=5)
    serialized = "\n\n".join(
        f"Source: {doc.metadata}\nContent: {doc.page_content}"
        for doc in retrieved_docs
    )
    return serialized, retrieved_docs


# Список всех доступных инструментов
tools = [retrieve_context]

model = ChatOllama(model=settings.MODEL, temperature=0.6, num_predict=2048)
agent = create_agent(model, tools, system_prompt=load_prompt("../prompts/rag_tools_explain.txt"))
