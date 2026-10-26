"""Profile-framing tests for Ruling D54 (command ARCH-20261021-125, TASK 1)."""

import json
import os
from pathlib import Path

import pytest

from autornd.config import settings
from autornd.knowledge.context import reset_rerank_mode
from tests.prompt_capture import capture_all


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "prompts"
PROFILES = ("engineering", "example", "cupline", "tier4")
WRITE_GOLDEN = os.environ.get("WRITE_GOLDEN") == "1"


async def _capture_for(name: str) -> dict[str, dict[str, str]]:
    from autornd.profiles import DEFAULT_PROFILE, load_profile, reset_profile, set_profile
    from autornd.specialists import registry as specialists_registry

    if name == "engineering":
        set_profile(DEFAULT_PROFILE)
    else:
        set_profile(load_profile(name))
    specialists_registry.reload_specialists()
    try:
        return await capture_all()
    finally:
        reset_profile()
        specialists_registry.reload_specialists()


async def test_write_golden_fixture(monkeypatch) -> None:
    """WRITE_GOLDEN=1 writes the four fixtures, one per profile, from today's code."""
    if os.environ.get("WRITE_GOLDEN") != "1":
        pytest.skip("WRITE_GOLDEN is not set")
    monkeypatch.setattr(settings, "model_research", "test-provider/test-research")
    monkeypatch.setattr(settings, "model_ranker", "test-provider/test-rank")

    for name in PROFILES:
        reset_rerank_mode()
        captured = await _capture_for(name)
        text = json.dumps(captured, indent=1, ensure_ascii=False, sort_keys=True)
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        (FIXTURE_DIR / f"{name}.json").write_text(text, encoding="utf-8")
