"""Runtime dependency contracts exercised by clean installs."""

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


class TestRuntimeDependencies:
    def test_sqlalchemy_declares_asyncio_extra(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text())
        dependencies = data["project"]["dependencies"]
        sqlalchemy = [
            dependency
            for dependency in dependencies
            if dependency.lower().startswith("sqlalchemy")
        ]

        assert sqlalchemy, "runtime dependencies do not declare SQLAlchemy"
        assert len(sqlalchemy) == 1, sqlalchemy
        assert sqlalchemy[0].lower().startswith("sqlalchemy[asyncio]"), sqlalchemy[0]
