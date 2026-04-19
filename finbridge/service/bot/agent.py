"""Агент, к которому пользователь обращается по любому вопросу. Атрошенко Б. С."""
import logging
from typing import List

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from pydantic import Field, BaseModel

from config import settings
from service.bot.tools import AgenticToolset
from service.utils import load_prompt

logger = logging.getLogger(__name__)


class State(BaseModel):
    """Состояние графа — передаётся между узлами и накапливает результат."""

    question: str = Field(description="Вопрос пользователя.")
    intent: str = Field(description="Намерение после классификации.", default="")
    answer: str = Field(description="Итоговый ответ бота.", default="")
    docs: List[Document] = Field(description="Источники из базы знаний.", default_factory=list)

    class Config:
        arbitrary_types_allowed = True


class RAGAgent:
    """Точка входа для работы с агентом. Синглтон."""

    _LLM = ChatOllama(model=settings.MODEL, temperature=0, num_predict=4096)
    _PROMPT = ChatPromptTemplate.from_messages([
        ("system", load_prompt("../prompts/rag_tools_explain.txt")),
        ("user", "Context: \n{context}\n\nQuestion: {question}")
    ])
    _RAG_CHAIN = (
            RunnableLambda(AgenticToolset.retrieve_context)
            | RunnableParallel(answer=_PROMPT | _LLM, docs=RunnableLambda(lambda x: x["docs"]))
    )

    def __init__(self):
        """Инициализатор."""

        g = StateGraph(State)

        # --- узлы ---
        g.add_node("classify", self._classify_node)
        g.add_node("rag", self._rag_node)
        g.add_node("small_talk", self._small_talk_node)
        g.add_node("out_of_scope", RAGAgent._out_of_scope_node)

        # --- рёбра ---
        g.add_edge(START, "classify")
        g.add_conditional_edges("classify", self._route_by_intent, {
            "knowledge_base": "rag",
            "small_talk": "small_talk",
            "out_of_scope": "out_of_scope",
        })
        g.add_edge("rag", END)
        g.add_edge("small_talk", END)
        g.add_edge("out_of_scope", END)

        self._graph = g.compile()

    def answer(self, question: str) -> dict:
        """
        Ответить на вопрос пользователя через граф.

        :param question: вопрос пользователя.
        :return: словарь с полями answer и docs.
        """

        result: State = self._graph.invoke(State(question=question))
        return {"answer": result["answer"], "docs": result["docs"]}

    def _classify_node(self, state: State) -> dict:
        """Классифицирует намерение и сохраняет в state.intent."""

        logger.info("[Agent] вопрос: %r", state.question)
        intent = AgenticToolset.classify_intent(self._LLM, state.question)
        logger.info("[Agent] intent: %s", intent)
        return {"intent": intent}

    def _rag_node(self, state: State) -> dict:
        """Ищет релевантные чанки и формирует ответ через RAG."""

        logger.info("[RAG] попали в RAG node")
        result = self._RAG_CHAIN.invoke({"question": state.question})
        return {"answer": result["answer"].content, "docs": result["docs"]}

    def _small_talk_node(self, state: State) -> dict:
        """Отвечает напрямую через LLM без обращения к базе знаний."""

        logger.info("[TALK] попали в SMALL_TALK node")
        return {"answer": self._LLM.invoke(state.question).content, "docs": []}

    @staticmethod
    def _out_of_scope_node(_state: State) -> dict:
        """Вежливо отклоняет вопросы вне области компетенции."""

        logger.info("[OUT_SCOPE] послали пользователя")
        return {"answer": "Я помогаю только с вопросами о компании FinBridge.", "docs": []}

    @staticmethod
    def _route_by_intent(state: State) -> str:
        """Возвращает имя следующего узла на основе intent. Маршрутизатор без логики."""

        return state.intent


agent = RAGAgent()
