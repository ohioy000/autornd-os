from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import Integer, String, delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from autornd.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    """One row: which numbered migration this database has had applied.

    A database that predates the stamp has tables and no row; it is read as
    version 0 and brought forward, so a 0.1.0 database upgrades in place.
    """

    __tablename__ = "schema_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(String, nullable=False, default="")


class SchemaTooNew(RuntimeError):
    """The database was written by a newer AutoRnD than this one."""


# Numbered, ordered, never edited once released: a database at version N has
# had every step up to N, and a step is only ever added at the end. A step
# must be safe to run on a database that already has its change, because a
# database from before the stamp existed is run through all of them.
MIGRATIONS: dict[int, Callable] = {}


def migration(version: int) -> Callable[[Callable], Callable]:
    def register(step: Callable) -> Callable:
        if version in MIGRATIONS:
            raise ValueError(f"migration {version} is registered twice")
        MIGRATIONS[version] = step
        return step
    return register


@migration(1)
def _add_missing_columns(conn) -> None:
    """Add columns that exist on the models but not yet in the database.

    `create_all` only creates missing tables — it never alters an existing
    one. Without this, upgrading a live database leaves it a column short and
    every query against that table fails. Only additive columns belong in
    this step; a later change is a later numbered migration.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    # `unreconciled_liability` is additive with a default: SQLite
    # fills every existing row from it, so the column is safe to
    # add to a live database the way a nullable one is.
    additive = {"workflows": {
        "error": "TEXT",
        "unreconciled_liability": "FLOAT NOT NULL DEFAULT 0.0",
    }}

    for table, columns in additive.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name, sql_type in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))
                logger.info("Added missing column %s.%s", table, name)


def _migrate(conn) -> None:
    """Bring the database to the newest numbered migration and stamp it."""
    newest = max(MIGRATIONS)
    row = conn.execute(select(SchemaVersion).limit(1)).first()
    stored = row.version if row else 0
    if stored > newest:
        raise SchemaTooNew(
            f"This database is at schema {stored} and this AutoRnD only knows "
            f"schema {newest}. It was written by a newer version. Upgrade "
            f"AutoRnD, or point DATABASE_URL at a fresh database.")
    for version in sorted(v for v in MIGRATIONS if v > stored):
        MIGRATIONS[version](conn)
        conn.execute(delete(SchemaVersion))
        conn.execute(insert(SchemaVersion).values(
            id=1, version=version, note=MIGRATIONS[version].__name__))
        logger.info("Applied schema migration %d", version)


async def init_db(target=None):
    target = target or engine
    async with target.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate)


async def get_session():
    async with async_session() as session:
        yield session
