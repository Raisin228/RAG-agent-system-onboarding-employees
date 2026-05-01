"""
Обработчики сообщений из RabbitMQ.
Приходит сообщение.
    * Если это текстовая задача - отправляем в LLM на генерацию и стримим через Redis ответ.
    * Если это LLM задача - транскрибируем её в текст, отправляем в LLM, после делаем стриминг ответа.
Атрошенко Б. С.
"""

import logging
import os

from service.bot import agent
from service.broker.models import TextTask, VoiceTask
from service.broker.result_store import result_store
from service.whisper import WhisperTranscriber

logger = logging.getLogger(__name__)


async def handle_text_task(body: bytes) -> None:
    """
    Запускает агента по текстовой задаче и стримит токены в Redis.

    :param body: текстовая задача на выполнение.
    :return:
    """

    task = TextTask.model_validate_json(body)
    logger.info(f"[Handler] text task {task.task_id} начата")
    try:
        async for event in agent.astream_tokens(task.query, task.session_id):
            await result_store.publish_event(task.task_id, event)
    except Exception as ex:
        logger.error(f"[Handler] ошибка text task {task.task_id}: {ex}")
        await result_store.publish_event(task.task_id, {"type": "error", "content": str(ex)})


async def handle_voice_task(body: bytes) -> None:
    """
    Транскрибирует аудио, запускает агента и стримит токены в Redis.

    :param body: запрос на ГС задачу.
    :return:
    """

    task = VoiceTask.model_validate_json(body)
    logger.info(f"[Handler] voice task {task.task_id} начата")
    try:
        with open(task.filename, "rb") as f:
            audio_bytes = f.read()
        os.unlink(task.filename)

        query = WhisperTranscriber.transcribe(audio_bytes, task.filename)
        if not query:
            await result_store.publish_event(
                task.task_id, {"type": "error", "content": "Не удалось распознать речь в аудиофайле"}
            )
            return

        await result_store.publish_event(task.task_id, {"type": "transcript", "content": query})
        async for event in agent.astream_tokens(query, task.session_id):
            await result_store.publish_event(task.task_id, event)
    except Exception as ex:
        logger.error(f"[Handler] ошибка voice task {task.task_id}: {ex}")
        await result_store.publish_event(task.task_id, {"type": "error", "content": str(ex)})
