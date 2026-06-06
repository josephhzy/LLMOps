"""Main query endpoint — the core RAG interface."""

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_rag_service
from app.core.auth import AuthenticatedUser, get_current_user
from app.models.api import QueryRequest, QueryResponse
from app.services.rag_service import RAGService

router = APIRouter()


@router.post('/query', response_model=QueryResponse)
async def query_rag(
    http_request: Request,
    request: QueryRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
) -> QueryResponse:
    """Main online QA endpoint.

    Role comes from the Bearer middleware (request.state.role) if it set one,
    otherwise it falls back to the X-API-Key user.role. It is never taken from
    the request body.
    """
    role = getattr(http_request.state, 'role', None) or user.role
    return await rag_service.answer(request, role=role, user_id=user.user_id)
