"""The version is stated in three places and they must agree.

`pyproject.toml` is what pip and the wheel carry, `autornd/main.py` is what
the API reports at /openapi.json, and the changelog's newest release heading
is what a reader of the release notes sees. Found 2026-11-17 at the 0.2.0
release: the version had stood at 0.1.0 in the first two through the whole
rebuild, and nothing would have said so if only one had been bumped.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _project_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


class TestTheVersionIsOneNumber:
    def test_the_api_reports_the_version_pyproject_carries(self):
        from autornd.main import app
        assert app.version == _project_version()

    def test_the_changelogs_newest_release_is_that_version(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        headings = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", text, re.M)
        assert headings and headings[0] == _project_version()
