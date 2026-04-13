"""Агент, к которому пользователь обращается по любому вопросу. Атрошенко Б. С."""
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_ollama import ChatOllama

from config import settings
from service.bot.tools import AgenticToolset
from service.utils import load_prompt

logger = logging.getLogger(__name__)


class RAGAgent:
    """Точка входа | работы с агентом. Синглтон."""

    _LLM = ChatOllama(model=settings.MODEL, temperature=0, num_predict=4096)
    _PROMPT = ChatPromptTemplate.from_messages([
        ("system", load_prompt("../prompts/rag_tools_explain.txt")),
        ("user", "Context: \n{context}\n\nQuestion: {question}")
    ])

    _CHAIN = (
            RunnableLambda(AgenticToolset.retrieve_context)
            | RunnableParallel(answer=_PROMPT | _LLM, docs=RunnableLambda(lambda x: x["docs"]))
    )

    def answer(self, question: str) -> dict:
        """
        Ответить на вопрос.

        :param question: вопрос пользователя.
        :return словарик с ответом на вопрос и списком источников.
        """
        logger.info("[Agent] вопрос: %r", question)
        intent = AgenticToolset.classify_intent(self._LLM, question)
        logger.info("[Agent] intent: %s", intent)

        if intent == "out_of_scope":
            return {
                "answer": "Я помогаю только с вопросами о компании FinBridge.",
                "docs": []
            }

        if intent == "small_talk":
            return {
                "answer": self._LLM.invoke(question).content,
                "docs": []
            }

        # knowledge_base — идём в RAG
        result = self._CHAIN.invoke({"question": question})
        return {
            "answer": result["answer"].content,
            "docs": result["docs"]
        }


agent = RAGAgent()
