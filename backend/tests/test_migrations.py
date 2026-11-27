from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401
from app.infrastructure.database import Base
from tests.conftest import TEST_DATABASE_URL


async def test_models_match_migrated_schema():
    """Fails if a model change is made without a matching Alembic migration."""
    engine = create_async_engine(TEST_DATABASE_URL)

    def diff(sync_conn):
        ctx = MigrationContext.configure(
            sync_conn,
            opts={"compare_type": True,
                  "include_object": lambda o, n, t, r, c: not (t == "table" and r and n == "spatial_ref_sys")},
        )
        return compare_metadata(ctx, Base.metadata)

    async with engine.connect() as conn:
        assert await conn.run_sync(diff) == []
    await engine.dispose()
