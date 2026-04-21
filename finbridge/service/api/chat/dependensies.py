"""Зависимости для endpoint'ов чата. Атрошенко Б. С."""

from fastapi import Header

SESSION_HEADER = "X-Session-Id"


def require_session_id(x_session_id: str = Header(..., alias=SESSION_HEADER)) -> str:
    """Зависимость, требующая session_id в заголовке."""

    return x_session_id
