"""Admin introspection routes."""

from fastapi import APIRouter, Depends

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import settings

router = APIRouter()


@router.get('/versions')
async def get_versions(_user: AuthenticatedUser = Depends(get_current_user)) -> dict:
    """Return active model/prompt/retriever/policy versions from live config."""
    return {
        'model_version': settings.default_model,
        'prompt_version': settings.prompt_version,
        'retriever_version': settings.retriever_version,
        'policy_version': settings.policy_version,
        'generation_backend': settings.generation_backend,
        'reranker_backend': settings.reranker_backend,
        'embedding_model': settings.embedding_model,
    }


@router.get('/config')
async def get_config(_user: AuthenticatedUser = Depends(get_current_user)) -> dict:
    """Return non-sensitive configuration for debugging."""
    return {
        'env': settings.env,
        'chroma_collection': settings.chroma_collection_name,
        'generation_backend': settings.generation_backend,
        'reranker_backend': settings.reranker_backend,
        'grounding_threshold': settings.grounding_threshold,
    }
