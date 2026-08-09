"""SQLAlchemy repository adapters with explicit workspace scope."""

from app.infrastructure.database.repositories.workspace_access import (
    SqlAlchemyWorkspaceAccessRepository,
)

__all__ = ["SqlAlchemyWorkspaceAccessRepository"]
