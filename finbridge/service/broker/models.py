"""Модель задачи для брокера. Атрошенко Б. С."""
from enum import Enum

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Один из возможных типов задачи."""

    TEXT = "text"
    VOICE = "voice"


class _BaseTask(BaseModel):
    """Шаблон задачи для RabbitMQ."""

    task_id: str
    session_id: str
    t_type: TaskType


class TextTask(_BaseTask):
    """Шаблон текстовой задачи. Запрос пользователя к агенту."""

    query: str = Field(description="Вопрос пользователя")
    t_type: TaskType = TaskType.TEXT


class VoiceTask(_BaseTask):
    """Задача конвертации гс в текст."""

    filename: str = Field(description="Имя буферного файла, в котором сохранено ГС.")
    t_type: TaskType = TaskType.VOICE
