"""Ручки для получения чата. Атрошенко Б. С."""

from fastapi import APIRouter

from service.bot import agent
from service.api.models import InsightResponse, InsightRequest, SourceDocument

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(path="/create_insight", response_model=InsightResponse)
def create_insight(request: InsightRequest) -> InsightResponse:
    """Задать вопрос агенту — цепочка сама извлекает контекст из RAG и формирует ответ."""
    result = agent.answer(request.query)
    # result["answer"] — AIMessage от LLM
    # result["docs"]   — list[Document] из Qdrant

    sources = [
        SourceDocument(content=doc.page_content, metadata=doc.metadata)
        for doc in result["docs"]
    ]

    return InsightResponse(answer=result["answer"], sources=sources)
