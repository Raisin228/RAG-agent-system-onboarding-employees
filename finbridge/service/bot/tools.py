"""Инструменты, используемые агентом. Атрошенко Б. С."""
import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from service.utils import load_prompt
from service.vectorstore.client import QdrantService

logger = logging.getLogger(__name__)


class AgenticToolset:
    """Всё что умеет делать агент [классификацию | извлечение RAG данных]."""

    _CLASSIFIER_PROMPT = ChatPromptTemplate.from_messages([
        ("system", load_prompt("../prompts/classifier.txt")),
        ("human", "{question}")
    ])

    @classmethod
    def classify_intent(cls, llm, question: str) -> str:
        """"
        Intent Classifier — определяет тип запроса пользователя.

        Возвращает одну из трёх категорий:
        - knowledge_base → вопрос по документам компании → идёт в RAG
        - small_talk     → приветствие, болтовня → LLM отвечает напрямую

        :param llm: модель для обработки ответа.
        :param question: вопрос пользователя.
        :return: категория классификации.
        """

        classification_chain = cls._CLASSIFIER_PROMPT | llm | StrOutputParser()
        result = classification_chain.invoke({"question": question}).strip().lower()
        # Определяю категорию
        if "knowledge_base" in result:
            return "knowledge_base"
        return "small_talk"

    @classmethod
    def retrieve_context(cls, usr_req: dict) -> dict:
        """
        Извлеч похожие на запрос чанки из Qdrant.

        :param usr_req: запрос на поиск.
        :return: удобное строковое представление набранных чанков и список самих документов.
        """

        logger.info("---[RAG]--- retrieve_context вызван с query=%r", usr_req["question"])
        retrieved_docs = QdrantService.get_qdrant_vector_store().similarity_search(usr_req.get('question'), k=10)
        logger.info("---[RAG]--- найдено чанков: %d", len(retrieved_docs))
        serialized = "\n\n".join(
            f"Source: {doc.metadata}\nContent: {doc.page_content}"
            for doc in retrieved_docs
        )
        return {**usr_req, "context": serialized, "docs": retrieved_docs}
