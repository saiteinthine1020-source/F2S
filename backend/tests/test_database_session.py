"""PostgreSQL transaction boundary tests."""

import asyncio

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.infrastructure.database.models.identity import BootstrapState
from app.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
    transactional_session,
)


@pytest.mark.postgres
def test_transaction_rolls_back_on_exception(migrated_database: Settings) -> None:
    """An exception must leave no partially committed database state."""

    async def exercise() -> None:
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        try:
            with pytest.raises(RuntimeError, match="force rollback"):
                async with transactional_session(sessions) as session:
                    session.add(BootstrapState(singleton_key="INSTALLATION"))
                    await session.flush()
                    raise RuntimeError("force rollback")

            async with sessions() as session:
                count = await session.scalar(select(func.count()).select_from(BootstrapState))
            assert count == 0
        finally:
            await engine.dispose()

    asyncio.run(exercise())
