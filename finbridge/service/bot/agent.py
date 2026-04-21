"""Агент, к которому пользователь обращается по любому вопросу. Атрошенко Б. С."""
import logging
from typing import List

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from pydantic import Field, BaseModel
from typing_extensions import AsyncGenerator

from config import settings
from service.ShortTermMemory.redis_storage import RedisHistoryStore
from service.bot.tools import AgenticToolset
from service.utils import load_prompt

logger = logging.getLogger(__name__)


class State(BaseModel):
    """Состояние графа — передаётся между узлами и накапливает результат."""

    history: list[BaseMessage] = Field(description="Предыдущие 3 turn'а. По типу: запрос пользователя + ответ агента.")
    question: str = Field(description="Вопрос пользователя.")
    intent: str = Field(description="Намерение после классификации.", default="")
    answer: str = Field(description="Итоговый ответ бота.", default="")
    docs: List[Document] = Field(description="Источники из базы знаний.", default_factory=list)

    class Config:
        arbitrary_types_allowed = True


class RAGAgent:
    """Точка входа для работы с агентом. Синглтон."""

    # Промпты и модельки
    __LLM = ChatOllama(base_url=settings.BASE_URL, model=settings.MODEL, temperature=0, num_predict=4096)
    __RAG_PROMPT = ChatPromptTemplate.from_messages([
        ("system", load_prompt("../prompts/rag_tools_explain.txt")),
        MessagesPlaceholder(variable_name="history", optional=True),
        ("user", "Context: \n{context}\n\nQuestion: {question}")
    ])
    __SMALL_TALK_PROMPT = ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt("../prompts/talker_explain.txt")),
            MessagesPlaceholder(variable_name="history", optional=True),
            ("user", "{question}"),
        ]
    )

    # LCEL цепочки
    _RAG_CHAIN = (
            RunnableLambda(AgenticToolset.retrieve_context)
            | RunnableParallel(answer=__RAG_PROMPT | __LLM, docs=RunnableLambda(lambda x: x["docs"]))
    )
    _SMALL_TALK_CHAIN = __SMALL_TALK_PROMPT | __LLM

    def __init__(self):
        """Инициализатор."""

        g = StateGraph(State)

        # --- узлы ---
        g.add_node("classify", self._classify_node)
        g.add_node("rag", self._rag_node)
        g.add_node("small_talk", self._small_talk_node)

        # --- рёбра ---
        g.add_edge(START, "classify")
        g.add_conditional_edges("classify", self._route_by_intent, {
            "knowledge_base": "rag",
            "small_talk": "small_talk",
        })
        g.add_edge("rag", END)
        g.add_edge("small_talk", END)

        self._graph = g.compile()

    async def astream_tokens(self, question: str, session: str) -> AsyncGenerator:
        """
        Стриминг токенов из графа через SSE.

        Генерирует dict-события:
          {"type": "token",  "content": "..."}   — очередной токен LLM
          {"type": "done",   "sources": [...]}    — конец, список источников

        :param question: вопрос пользователя.
        :param session: сессия Redis.
        :return: словарь - чанк сгенерированного ответа.
        """

        history = RedisHistoryStore.get_last_full_msgs(session)
        RedisHistoryStore.add_user_msg(session, question)

        full_answer = ""
        docs: List[Document] = []

        async for event in self._graph.astream_events(
                State(history=history, question=question),
                version="v2",
        ):
            kind = event["event"]
            node = event.get("metadata", {}).get("langgraph_node", "")

            if kind == "on_chat_model_stream" and node in ("rag", "small_talk"):
                chunk = event["data"]["chunk"].content
                if chunk:
                    full_answer += chunk
                    yield {"type": "token", "content": chunk}

            elif kind == "on_chain_end" and node == "rag":
                output = event["data"].get("output", {})
                if isinstance(output, dict) and "docs" in output:
                    docs = output["docs"]

        RedisHistoryStore.add_ai_message(session, full_answer)
        yield {
            "type": "done",
            "sources": [
                {"content": doc.page_content, "metadata": doc.metadata}
                for doc in docs
            ],
        }

    def _classify_node(self, state: State) -> dict:
        """Классифицирует намерение и сохраняет в state.intent."""

        logger.info("[Agent] вопрос: %r", state.question)
        intent = AgenticToolset.classify_intent(self.__LLM, state.question)
        logger.info("[Agent] intent: %s", intent)
        return {"intent": intent}

    def _rag_node(self, state: State) -> dict:
        """Ищет релевантные чанки и формирует ответ через RAG."""

        result = self._RAG_CHAIN.invoke({"question": state.question, "history": state.history})
        return {"answer": result["answer"].content, "docs": result["docs"]}

    def _small_talk_node(self, state: State) -> dict:
        """Отвечает напрямую через LLM без обращения к базе знаний."""

        return {"answer": self._SMALL_TALK_CHAIN.invoke(
            {"question": state.question, "history": state.history}
        ).content, "docs": []}

    @staticmethod
    def _route_by_intent(state: State) -> str:
        """Возвращает имя следующего узла на основе intent. Маршрутизатор без логики."""

        return state.intent


agent = RAGAgent()
