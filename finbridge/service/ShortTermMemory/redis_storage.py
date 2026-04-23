"""Слой работы с Short Long Memory через Redis. Атрошенко Б. С."""

import redis as redis_lib
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from config import settings


class RedisHistoryStore:
    """CRUD для редиски."""

    @staticmethod
    def add_ai_message(session_id: str, text: str) -> None:
        """Добавить историю от агента."""

        RedisHistoryStore._get_client(session_id).add_message(AIMessage(text))

    @staticmethod
    def add_user_msg(session_id: str, text: str) -> None:
        """Добавить новое сообщение в Redis List."""

        RedisHistoryStore._get_client(session_id).add_message(HumanMessage(text))

    @staticmethod
    def clear_history(session_id: str) -> None:
        """
        Почистить историю Redis в рамках сессии.

        :param session_id: id сессии чата.
        """

        # Отдельно храниться summary и full. Поэтому чистим по отдельности.
        RedisHistoryStore._get_client(session_id).clear()
        RedisHistoryStore._get_raw_client().delete(f"summary/{session_id}")

    @staticmethod
    def get_last_full_msgs(session_id: str) -> list[BaseMessage]:
        """Получить последние 6 сообщений истории."""

        return RedisHistoryStore._get_client(session_id).messages[-6:]

    @staticmethod
    def get_summary(session_id: str) -> str:
        """
        Получить накопленную суммаризацию всей истории сессии.

        :param session_id: id сессии чата.
        """

        value = RedisHistoryStore._get_raw_client().get(f"summary/{session_id}")
        return value.decode() if value else ""

    @staticmethod
    def save_summary(session_id: str, summary: str) -> None:
        """
        Сохранить обновлённую суммаризацию истории сессии.

        :param session_id: id сессии чата.
        :param summary: текущее состояние summary.
        """

        RedisHistoryStore._get_raw_client().setex(
            f"summary/{session_id}", settings.REDIS_TTL, summary
        )

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
            key_prefix="chat/",
            ttl=settings.REDIS_TTL
        )

    @staticmethod
    def _get_raw_client():
        """Получить прямой Redis-клиент для работы со строковыми ключами."""

        return redis_lib.from_url(settings.REDIS_URL)
