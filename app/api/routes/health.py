"""Health check endpoints for liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings

router = APIRouter()


@router.get('/health/live')
async def healthcheck() -> dict:
    """Liveness probe. Confirms the process is running."""
    return {'status': 'alive'}


@router.get('/health/ready')
async def readycheck():
    """Readiness probe. Checks dependency availability.

    Returns HTTP 503 when degraded so Kubernetes won't route traffic.
    """
    checks = {}

    # Check ChromaDB
    try:
        from app.services.vector_store import ChromaVectorStore

        store = ChromaVectorStore()
        if store.heartbeat():
            checks['chromadb'] = 'ok'
            checks['chromadb_chunks'] = store.count()
        else:
            checks['chromadb'] = 'unavailable'
    except Exception:
        checks['chromadb'] = 'unavailable'

    # Check corpus state
    try:
        from app.services.corpus_service import CorpusService

        corpus = CorpusService()
        status = corpus.get_corpus_status()
        checks['corpus_version'] = status.get('current_version') or 'none'
        checks['corpus_documents'] = status.get('total_documents', 0)
    except Exception:
        checks['corpus_version'] = 'unknown'

    all_ok = checks.get('chromadb') == 'ok'
    status = 'ready' if all_ok else 'degraded'
    body = {
        'status': status,
        'checks': checks,
        'generation_backend': settings.generation_backend,
    }

    if status == 'degraded':
        return JSONResponse(status_code=503, content=body)

    return body
