"""Fail-closed authentication dependency awaiting the Issue #50 session adapter."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends


class Unauthenticated(Exception):
    """A safe authentication-boundary failure."""


async def authenticated_account_id() -> UUID:
    """Reject protected routes until server-derived authentication is installed."""
    raise Unauthenticated


AuthenticatedAccountId = Annotated[UUID, Depends(authenticated_account_id)]
