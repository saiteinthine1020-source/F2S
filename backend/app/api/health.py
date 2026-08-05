"""Minimal operational liveness behavior."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter()


class HealthResponse(BaseModel):
    """Non-sensitive liveness response."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]


@router.get("/health/live", response_model=HealthResponse, include_in_schema=False)
async def liveness() -> HealthResponse:
    """Confirm that the ASGI process can serve requests."""
    return HealthResponse(status="ok")
