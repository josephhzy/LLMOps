"""Corpus governance API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_corpus_service
from app.core.audit import audit
from app.core.auth import AuthenticatedUser, require_admin
from app.services.corpus_service import CorpusService

router = APIRouter()


class RevokeRequest(BaseModel):
    doc_id: str
    reason: str


@router.get('/corpus/status')
async def corpus_status(corpus_service: CorpusService = Depends(get_corpus_service)) -> dict:
    """Get corpus-level statistics.

    Intentionally public (no auth) in demo mode — read-only, no PII exposed.
    Add Depends(get_current_user) here before any production deployment.
    """
    return corpus_service.get_corpus_status()


@router.get('/corpus/documents')
async def list_documents(
    status: str | None = None,
    corpus_service: CorpusService = Depends(get_corpus_service),
) -> dict:
    """List documents with optional status filter.

    Intentionally public (no auth) in demo mode — read-only, no PII exposed.
    Add Depends(get_current_user) here before any production deployment.
    """
    docs = corpus_service.list_documents(status_filter=status)
    return {'documents': docs, 'total': len(docs)}


@router.post('/corpus/revoke')
async def revoke_document(
    request: RevokeRequest,
    user: AuthenticatedUser = Depends(require_admin),
    corpus_service: CorpusService = Depends(get_corpus_service),
) -> dict:
    """Revoke a document from the active corpus."""
    success = corpus_service.revoke_document(request.doc_id, request.reason)
    if not success:
        raise HTTPException(status_code=404, detail=f'Document not found: {request.doc_id}')
    audit.log_event('corpus', user.user_id, 'revoke', target=request.doc_id, details={'reason': request.reason})
    return {'status': 'revoked', 'doc_id': request.doc_id, 'reason': request.reason}


@router.get('/corpus/documents/{doc_id}')
async def get_document(doc_id: str, corpus_service: CorpusService = Depends(get_corpus_service)) -> dict:
    """Get a specific document's metadata and status."""
    doc = corpus_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f'Document not found: {doc_id}')
    return doc
