"""The database is versioned, and an old one is brought forward in place.

Before this, `init_db` added two known columns at startup and nothing recorded
what a database had had done to it, so there was no safe way to say a later
release would open an earlier one, and a database written by a newer release
was opened by an older one without a word.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from autornd import database
from autornd.database import MIGRATIONS, SchemaTooNew, init_db


def _engine(tmp_path, name="m.db"):
    return create_async_engine(f"sqlite+aiosqlite:///{tmp_path / name}")


async def _version(eng):
    async with eng.begin() as conn:
        rows = (await conn.execute(text("SELECT version FROM schema_version"))).all()
    return [r[0] for r in rows]


class TestTheRegistry:
    def test_steps_are_numbered_from_one_without_gaps(self):
        assert sorted(MIGRATIONS) == list(range(1, max(MIGRATIONS) + 1))

    def test_a_number_cannot_be_registered_twice(self):
        with pytest.raises(ValueError):
            database.migration(1)(lambda conn: None)


@pytest.mark.asyncio
class TestAFreshDatabase:
    async def test_is_stamped_at_the_newest_step(self, tmp_path):
        eng = _engine(tmp_path)
        await init_db(eng)
        assert await _version(eng) == [max(MIGRATIONS)]
        await eng.dispose()

    async def test_starting_twice_changes_nothing(self, tmp_path):
        eng = _engine(tmp_path)
        await init_db(eng)
        await init_db(eng)
        assert await _version(eng) == [max(MIGRATIONS)]
        await eng.dispose()


@pytest.mark.asyncio
class TestADatabaseFromBeforeTheStamp:
    async def test_is_brought_forward_and_keeps_its_rows(self, tmp_path):
        """A 0.1.0 database: a workflows table without the later columns,
        a row in it, and no schema_version table."""
        eng = _engine(tmp_path)
        async with eng.begin() as conn:
            await conn.execute(text(
                "CREATE TABLE workflows (id INTEGER PRIMARY KEY, request TEXT)"))
            await conn.execute(text(
                "INSERT INTO workflows (id, request) VALUES (7, 'kept')"))
        await init_db(eng)
        async with eng.begin() as conn:
            cols = [r[1] for r in await conn.execute(text("PRAGMA table_info(workflows)"))]
            kept = (await conn.execute(text("SELECT request FROM workflows WHERE id = 7"))).all()
        assert {"error", "unreconciled_liability"} <= set(cols)
        assert kept == [("kept",)]
        assert await _version(eng) == [max(MIGRATIONS)]
        await eng.dispose()


@pytest.mark.asyncio
class TestADatabaseFromANewerRelease:
    async def test_is_refused_with_a_sentence_and_left_untouched(self, tmp_path):
        eng = _engine(tmp_path)
        await init_db(eng)
        newer = max(MIGRATIONS) + 5
        async with eng.begin() as conn:
            await conn.execute(text(f"UPDATE schema_version SET version = {newer}"))
        with pytest.raises(SchemaTooNew) as raised:
            await init_db(eng)
        assert f"schema {newer}" in str(raised.value)
        assert "Upgrade AutoRnD" in str(raised.value)
        assert await _version(eng) == [newer]
        await eng.dispose()

    async def test_the_server_start_does_not_swallow_it(self, tmp_path, monkeypatch):
        """init_db is the one place that opens the database at startup."""
        eng = _engine(tmp_path)
        await init_db(eng)
        async with eng.begin() as conn:
            await conn.execute(text("UPDATE schema_version SET version = 999"))
        monkeypatch.setattr(database, "engine", eng)
        with pytest.raises(SchemaTooNew):
            await init_db()
        await eng.dispose()


@pytest.mark.asyncio
class TestANewStepRunsOnceAndInOrder:
    async def test_a_later_step_is_applied_to_a_database_at_the_earlier_one(
            self, tmp_path, monkeypatch):
        eng = _engine(tmp_path)
        await init_db(eng)
        ran: list[int] = []
        newest = max(MIGRATIONS)

        def step(conn):
            ran.append(newest + 1)
            conn.execute(text("CREATE TABLE added_later (x INTEGER)"))

        monkeypatch.setitem(MIGRATIONS, newest + 1, step)
        await init_db(eng)
        await init_db(eng)
        assert ran == [newest + 1]
        assert await _version(eng) == [newest + 1]
        await eng.dispose()
