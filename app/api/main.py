"""FastAPI application factory.

Central bootstrap point: configures logging, middleware, and routes.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware import AuthMiddleware, ErrorHandlerMiddleware
from app.api.routes.admin import router as admin_router
from app.api.routes.corpus import router as corpus_router
from app.api.routes.health import router as health_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.query import router as query_router
from app.api.routes.registry import router as registry_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.metrics import BUILD_INFO


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    BUILD_INFO.info(
        {
            'version': '0.1.0',
            'env': settings.env,
            'generation_backend': settings.generation_backend,
        }
    )
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    configure_logging(
        log_level=settings.log_level,
        json_output=(settings.env != 'dev'),
    )

    app = FastAPI(
        title='LLM Ops Platform',
        version='0.1.0',
        description='RAG platform with policy guardrails, corpus governance, and MLOps pipelines.',
        lifespan=lifespan,
    )

    # Middleware order matters: AuthMiddleware is outermost (runs first);
    # ErrorHandlerMiddleware is inner and catches exceptions from the route handlers.
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(AuthMiddleware)

    # Routes
    app.include_router(health_router, tags=['health'])
    app.include_router(query_router, prefix='/v1', tags=['query'])
    app.include_router(ingest_router, prefix='/v1', tags=['ingest'])
    app.include_router(jobs_router, prefix='/v1', tags=['jobs'])
    app.include_router(corpus_router, prefix='/v1/admin', tags=['corpus'])
    app.include_router(registry_router, prefix='/v1/admin', tags=['registry'])
    app.include_router(metrics_router, tags=['observability'])

    app.include_router(admin_router, prefix='/v1/admin', tags=['admin'])

    return app
