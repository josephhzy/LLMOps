"""Prometheus metrics endpoint."""

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest

from app.core.auth import AuthenticatedUser, get_current_user

router = APIRouter()


@router.get('/metrics', response_class=PlainTextResponse)
async def metrics(_user: AuthenticatedUser = Depends(get_current_user)):
    """Expose Prometheus metrics for scraping."""
    return generate_latest().decode()
