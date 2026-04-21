"""Ручки для получения чата. Атрошенко Б. С."""
import logging
import uuid

from fastapi import APIRouter, Depends

from service.api.chat.dependensies import require_session_id
from service.bot import agent
from service.api.chat.models import InsightResponse, InsightRequest, SourceDocument, GenerateSession

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


@router.post(path="/create_insight", response_model=InsightResponse)
async def create_insight(request: InsightRequest, session_id: str = Depends(require_session_id)) -> InsightResponse:
    """Задать вопрос агенту — цепочка сама извлекает контекст из RAG и формирует ответ."""

    logger.info(f"->$ ID сессии чата, Backend: {session_id}")
    result = agent.answer(request.query, session_id)
    # result["answer"] — AIMessage от LLM
    # result["docs"]   — list[Document] из Qdrant

    sources = [
        SourceDocument(content=doc.page_content, metadata=doc.metadata)
        for doc in result["docs"]
    ]

    return InsightResponse(answer=result["answer"], sources=sources)


@router.post(path="/chat/sessions", response_model=GenerateSession)
async def create_session() -> GenerateSession:
    """Сгенерировать ID сессии. Используется для хранения истории Redis."""

    session_id = str(uuid.uuid4())
    return GenerateSession(user_identity=session_id)
