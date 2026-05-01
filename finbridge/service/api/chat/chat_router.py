"""Ручки для получения чата. Атрошенко Б. С."""
import logging
import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from service.api.chat.dependensies import require_session_id
from service.api.chat.models import InsightRequest, GenerateSession, TaskAccepted
from service.broker import publisher, result_store
from service.broker.models import TextTask, VoiceTask

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


@router.post(path="/create_insight_stream")
async def create_insight_stream(
        request: InsightRequest, session_id: str = Depends(require_session_id)
) -> TaskAccepted:
    """
    Публикация задачи на выполнение в RabbitMQ.

    :return: ид задачи из очереди.
    """

    task_id = str(uuid.uuid4())
    task = TextTask(task_id=task_id, session_id=session_id, query=request.query)
    await publisher.publish_text_task(task)
    logger.info(f"[Chat] text task_id := {task_id} отправлена. Session_id := {session_id}")
    return TaskAccepted(**{"task_id": task_id})


@router.post(path="/voice_insight_stream")
async def voice_insight_stream(
        file: UploadFile = File(...), session_id: str = Depends(require_session_id)
) -> TaskAccepted:
    """Принимаем аудиофайл, публикует голосовую задачу в RabbitMQ и возвращает task_id."""

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Аудиофайл пустой")

    # генерирую уникальный суффикс и расширение для временных файлов.
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".wav"
    suffix = f"_{uuid.uuid4().hex}{file_ext}"
    # создаю временный файл вида: /tmp/tmpABCDE123_a345gux.wav
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_f:
        tmp_f.write(audio_bytes)
        tmp_path = tmp_f.name

    # отправляю задачу на транскрибацию в rabbit
    task_id = str(uuid.uuid4())
    task = VoiceTask(task_id=task_id, session_id=session_id, filename=tmp_path)
    await publisher.publish_voice_task(task)
    logger.info(f"[Chat] voice task_id := {task_id} опубликована. Session_id := {session_id}")
    return TaskAccepted(**{"task_id": task_id})


@router.post(path="/sessions", response_model=GenerateSession)
async def create_session() -> GenerateSession:
    """Сгенерировать ID сессии. Используется для хранения истории Redis."""

    session_id = str(uuid.uuid4())
    return GenerateSession(user_identity=session_id)


@router.get(path="/stream/{task_id}")
async def stream_task_result(task_id: str) -> StreamingResponse:
    """SSE-стриминг токенов из Redis Pub | Sub по task_id."""

    async def _generate():
        async for raw in result_store.stream_events(task_id):
            yield f"data: {raw}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
