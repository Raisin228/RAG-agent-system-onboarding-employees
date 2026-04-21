"""Ручки для получения чата. Атрошенко Б. С."""
import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from service.api.chat.dependensies import require_session_id
from service.bot import agent
from service.api.chat.models import InsightResponse, InsightRequest, SourceDocument, GenerateSession

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
        try:
            async for event_data in agent.astream_tokens(request.query, session_id):
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
        except Exception as ex:
            logger.error(f"[stream] ошибка стриминга {ex}")
            yield f"data: {json.dumps({"type": "error", "content": str(ex)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.post(path="/chat/sessions", response_model=GenerateSession)
async def create_session() -> GenerateSession:
    """Сгенерировать ID сессии. Используется для хранения истории Redis."""

    session_id = str(uuid.uuid4())
    return GenerateSession(user_identity=session_id)
