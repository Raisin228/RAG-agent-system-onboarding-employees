"""Ручки для получения чата. Атрошенко Б. С."""
import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse

from service.api.chat.dependensies import require_session_id
from service.bot import agent
from service.api.chat.models import InsightRequest, GenerateSession
from service.whisper import WhisperTranscriber

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


@router.post(path="/create_insight_stream")
async def create_insight_stream(
        request: InsightRequest, session_id: str = Depends(require_session_id)
) -> StreamingResponse:
    """SSE-стриминг токенов от агента."""

    logger.info(f"[stream] ID сессии чата, Backend: {session_id}")

    async def _generate() -> AsyncGenerator:
        """Асинхронный генератор для извлечения стриминга LLM."""
        yield f"data: {json.dumps({"type": "transcript", "content": request.query}, ensure_ascii=False)}\n\n"
        try:
            async for event_data in agent.astream_tokens(request.query, session_id):
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
        except Exception as ex:
            logger.error(f"[stream] ошибка стриминга {ex}")
            yield f"data: {json.dumps({"type": "error", "content": str(ex)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.post(path="/voice_insight_stream")
async def voice_insight_stream(file: UploadFile = File(...), session_id: str = Depends(require_session_id)):
    """Принимаем аудиофайл, транскрибируем через Fast-whisper -> стриминг ответа через SSE."""

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Аудиофайл пустой")

    try:
        query = WhisperTranscriber.transcribe(audio_bytes, file.filename or "audio.wav")
    except Exception as ex:
        logger.error(f"[Voice Converter] ошибка транскрибации аудио {ex}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Ошибка транскрибации аудио {ex}"
        )

    if not query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Не удалось распознать речь в аудиофайле"
        )

    logger.info(f"[Voice Converter] транскрипция выполнена {repr(query)}")

    async def _generate() -> AsyncGenerator:
        # Тут специально сразу же устанавливаем соединение. Чтоб клиент знал что мы выполняемся
        yield f"data: {json.dumps({"type": "transcript", "content": query}, ensure_ascii=False)}\n\n"
        try:
            async for event_data in agent.astream_tokens(query, session_id):
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
        except Exception as exp:
            logger.error(f"[Strimming] ошибка стриминга ответа {exp}")
            yield f"data: {json.dumps({"type": "error", "content": str(exp)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.post(path="/sessions", response_model=GenerateSession)
async def create_session() -> GenerateSession:
    """Сгенерировать ID сессии. Используется для хранения истории Redis."""

    session_id = str(uuid.uuid4())
    return GenerateSession(user_identity=session_id)
