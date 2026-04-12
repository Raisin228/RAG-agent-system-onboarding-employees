"""Ручки для получения чата. Атрошенко Б. С."""

from fastapi import APIRouter
from langchain_core.messages import AIMessage, ToolMessage

from agent.rag_agent import agent
from application.chat.models import InsightResponse, InsightRequest, SourceDocument

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(path="/create_insight", response_model=InsightResponse)
def create_insight(request: InsightRequest) -> InsightResponse:
    """Задать вопрос агенту — агент ищет релевантные документы и формирует ответ."""
    result = agent.invoke({"messages": [{"role": "user", "content": request.query}]})

    # Финальный текстовый ответ — AIMessage в цепочке
    final_message = next(
        msg for msg in reversed(result["messages"])
        if isinstance(msg, AIMessage)
    )

    # Документы-источники из ToolMessage (артефакты retrieve_context)
    sources: list[SourceDocument] = []
    for msg in result["messages"]:
        if isinstance(msg, ToolMessage) and msg.artifact:
            for doc in msg.artifact:
                sources.append(
                    SourceDocument(
                        content=doc.page_content,
                        metadata=doc.metadata,
                    )
                )

    return InsightResponse(answer=final_message.content, sources=sources)
