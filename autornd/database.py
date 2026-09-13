import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from autornd.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _add_missing_columns(conn) -> None:
    """Add columns that exist on the models but not yet in the database.

    There is no migration tool here, and `create_all` only creates missing
    tables — it never alters an existing one. Without this, upgrading a live
    database leaves it a column short and every query against that table
    fails. Only additive, nullable columns belong here; anything more than
    that needs a real migration.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    additive = {"workflows": {"error": "TEXT"}}

    for table, columns in additive.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name, sql_type in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))
                logger.info("Added missing column %s.%s", table, name)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


async def get_session():
    async with async_session() as session:
        yield session
