"""Слой работы с Short Long Memory через Redis. Атрошенко Б. С."""
from fastapi import Request

from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

from config import settings

# class MemorySummarizer:
#     """Суммаризатор истории для Redis."""
#
#     def summarize(self):

SESSION_HEADER = "X-Session-Id"


def get_create_session_id(request: Request):
    ...

class RedisHistoryStore:
    """CRUD для редиски."""

    @staticmethod
    def add_ai_message(session_id: str, text: str):
        """Добавить историю от агента."""

        RedisHistoryStore._get_client(session_id).add_message(AIMessage(text))

    @staticmethod
    def add_user_msg(session_id: str, text: str):
        """Добавить новое сообщение в Redis List."""

        RedisHistoryStore._get_client(session_id).add_message(HumanMessage(text))

    @staticmethod
    def clear_history(session_id: str) -> None:
        """Почистить историю Redis в рамках сессии."""

        RedisHistoryStore._get_client(session_id).clear()

    @staticmethod
    def get_messages(session_id: str):
        """Получить сообщения последние N сообщений истории."""

        a = RedisHistoryStore._get_client(session_id).messages
        print(a)
        return a

    @staticmethod
    def _get_client(session_id: str):
        """
        Получить клиент для работы с историей.

        :param session_id: ID истории.
        :return клиент для доступов в Redis.
        """

        return RedisChatMessageHistory(
            session_id=session_id,
            url=settings.REDIS_URL,
            key_prefix="chat",
            ttl=settings.REDIS_TTL
        )
