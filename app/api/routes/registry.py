"""Model registry API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_model_registry
from app.core.audit import audit
from app.core.auth import AuthenticatedUser, require_admin
from app.services.model_registry import ModelRegistry

router = APIRouter()


class PromoteRequest(BaseModel):
    model_id: str
    new_status: str
    eval_metrics: dict | None = None


class RegisterRequest(BaseModel):
    model_id: str
    backend: str
    prompt_version: str
    embedding_model: str
    eval_snapshot: dict = {}
    notes: str = ''


@router.get('/registry')
async def list_models(registry: ModelRegistry = Depends(get_model_registry)) -> dict:
    """List all registered model bundles."""
    history = registry.get_history()
    return {'models': history, 'total': len(history)}


@router.get('/registry/active')
async def get_active_model(registry: ModelRegistry = Depends(get_model_registry)) -> dict:
    """Get the current production model bundle."""
    active = registry.get_active()
    if not active:
        return {'status': 'no_production_model', 'message': 'No model is currently in production'}
    return active


@router.post('/registry/register')
async def register_model(
    request: RegisterRequest,
    user: AuthenticatedUser = Depends(require_admin),
    registry: ModelRegistry = Depends(get_model_registry),
) -> dict:
    """Register a new model bundle as candidate."""
    from app.domain.models import ModelRegistryEntry

    entry = ModelRegistryEntry(
        model_id=request.model_id,
        backend=request.backend,
        prompt_version=request.prompt_version,
        embedding_model=request.embedding_model,
        eval_snapshot=request.eval_snapshot,
        notes=request.notes,
    )
    model_id = registry.register(entry)
    audit.log_event('model', user.user_id, 'register', target=model_id)
    return {'model_id': model_id, 'status': 'candidate'}


@router.post('/registry/promote')
async def promote_model(
    request: PromoteRequest,
    user: AuthenticatedUser = Depends(require_admin),
    registry: ModelRegistry = Depends(get_model_registry),
) -> dict:
    """Promote a model to a new status. Production promotion requires eval metrics."""
    success = registry.promote(request.model_id, request.new_status, request.eval_metrics)
    if not success:
        raise HTTPException(
            status_code=400,
            detail='Promotion failed: model not found or evaluation gate not met',
        )
    return {'model_id': request.model_id, 'new_status': request.new_status}
