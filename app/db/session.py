from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
def make_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    options: dict[str, object] = {"pool_pre_ping": True}
    if not database_url.startswith("sqlite"):
        options.update(pool_size=5, max_overflow=10)
    return async_sessionmaker(create_async_engine(database_url, **options), expire_on_commit=False)
