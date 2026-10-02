import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


def make_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Create a session factory suited to the process hosting the app.

    Vercel functions can be suspended between invocations.  Keeping an
    asyncpg socket in a process-local pool makes those stale connections show
    up as intermittent connection failures, and a pool per function instance
    can exhaust the database connection limit.  Let the database provider's
    pooler manage connections in that environment instead.
    """
    options: dict[str, object] = {"pool_pre_ping": True}
    if os.getenv("VERCEL") == "1":
        options["poolclass"] = NullPool
    elif not database_url.startswith("sqlite"):
        options.update(pool_size=5, max_overflow=10)
    return async_sessionmaker(create_async_engine(database_url, **options), expire_on_commit=False)
