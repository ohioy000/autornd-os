"""Ruling D55: a workflow per request.

A request may name an offered workflow; anything else it names is refused
before the run gate, so a refusal holds no slot and leaves no row. Every run
records which workflow ran. The duplicate guard keys on the workflow too.
engineering-rnd is renamed full-team, with no alias: the old name is refused
in a request and at startup, and no current file names it.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from sqlalchemy import func, select

from autornd.api import routes
from autornd.config import Settings, settings
from autornd.graph.spec import SpecError, load, parse
from autornd.models.workflow import Workflow, WorkflowStatus
from tests.test_api import _wire_file_backed_run
from tests.test_watchdog import REQUEST

ROOT = Path(__file__).resolve().parent.parent
OFFERED = ["answer-and-recompute", "full-team", "lean", "verify-first"]
# sha256 of workflows/engineering-rnd.yaml on main before D55, the file
# full-team.yaml was renamed from.
OLD_FILE_SHA256 = "5815d62f347ff78934f2402c3492f17572d8ad260320f289f45b7bf26b37d153"
OFFERED_LINES = "\n# Ruling D55 (2): a request may name this workflow.\noffered: true\n"


@pytest.fixture(autouse=True)
def _clean_run_gate():
    """The gate is process state; a run admitted by one test must not count
    against the next."""
    routes._run_gate._in_flight.clear()
    yield
    routes._run_gate._in_flight.clear()


def _sha256(name: str) -> str:
    return hashlib.sha256(
        (ROOT / "workflows" / f"{name}.yaml").read_bytes()).hexdigest()


def _record(detail: dict) -> dict:
    """The run's `workflow` phase record."""
    records = [p for p in detail["phases"] if p["phase"] == "workflow"]
    assert len(records) == 1, [p["phase"] for p in detail["phases"]]
    assert records[0]["cost"] == 0.0
    return records[0]["verdict"]


class TestTheRequestChoosesItsWorkflow:
    async def test_a_named_workflow_runs_and_is_recorded(
            self, api_client, tmp_path, monkeypatch):
        await _wire_file_backed_run(tmp_path, monkeypatch)
        named = (await api_client.post("/api/workflows/sync", json={
            "request": REQUEST, "workflow": "verify-first"})).json()["data"]
        unnamed = (await api_client.post("/api/workflows/sync", json={
            "request": REQUEST})).json()["data"]

        assert _record(named) == {"name": "verify-first",
                                  "sha256": _sha256("verify-first")}
        assert _record(unnamed) == {"name": "full-team",
                                    "sha256": _sha256("full-team")}
        # verify-first has no plan; the full team plans.
        assert "plan" not in [p["phase"] for p in named["phases"]]
        assert "plan" in [p["phase"] for p in unnamed["phases"]]

    async def test_an_unnamed_run_uses_the_configured_default(
            self, api_client, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "autornd_workflow", "lean")
        await _wire_file_backed_run(tmp_path, monkeypatch)
        detail = (await api_client.post("/api/workflows/sync", json={
            "request": REQUEST})).json()["data"]
        assert _record(detail) == {"name": "lean", "sha256": _sha256("lean")}

    def test_naming_the_default_is_the_same_run_as_naming_none(self):
        unnamed = routes._requested_workflow(
            routes.WorkflowRequest(request=REQUEST))
        named = routes._requested_workflow(
            routes.WorkflowRequest(request=REQUEST, workflow="full-team"))
        assert unnamed[0] == named[0] == "full-team"


class TestARefusedNameLeavesNothing:
    @pytest.mark.parametrize("endpoint", ["/api/workflows", "/api/workflows/sync"])
    @pytest.mark.parametrize("name", [
        "../workflows/lean", "/etc/passwd", "triage-only", "nonexistent",
        "engineering-rnd"])
    async def test_the_name_is_refused_with_the_offered_names(
            self, api_client, tmp_path, monkeypatch, endpoint, name):
        clients, observer = await _wire_file_backed_run(tmp_path, monkeypatch)
        resp = await api_client.post(endpoint, json={
            "request": REQUEST, "workflow": name})
        assert resp.status_code == 422, resp.text
        detail = resp.json()["detail"]
        assert f"one of: {', '.join(OFFERED)}." in detail
        if name == "engineering-rnd":
            assert "is now named 'full-team'" in detail
        # Refused before the gate: no slot held, no row, no client built.
        assert routes._run_gate.count() == 0
        assert clients == []
        async with observer() as session:
            rows = (await session.execute(
                select(func.count()).select_from(Workflow))).scalar_one()
        assert rows == 0


class TestTheOfferedList:
    async def test_the_four_are_listed_with_their_descriptions(self, api_client):
        resp = await api_client.get("/api/workflows/offered")
        assert resp.status_code == 200
        listed = resp.json()["data"]
        assert [w["name"] for w in listed] == OFFERED
        for entry in listed:
            spec = load(ROOT / "workflows" / f"{entry['name']}.yaml")
            assert entry["description"] == spec.description.strip() != ""

    def test_every_file_that_declares_offered_loads(self):
        declared = []
        for path in sorted((ROOT / "workflows").glob("*.yaml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if raw.get("offered") is True:
                assert load(path).offered is True
                declared.append(path.stem)
        assert declared == OFFERED

    async def test_a_run_is_still_read_by_its_id(self, api_client, db_session):
        row = Workflow(request=REQUEST, status=WorkflowStatus.COMPLETED)
        db_session.add(row)
        await db_session.commit()
        resp = await api_client.get(f"/api/workflows/{row.id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == row.id

    def test_offered_must_be_true_or_false(self):
        nodes = [{"id": "a", "kind": "ai", "tier": "t", "prompt": "p"}]
        assert parse({"name": "w", "nodes": nodes}).offered is False
        assert parse({"name": "w", "offered": True, "nodes": nodes}).offered is True
        with pytest.raises(SpecError, match="must be true or false"):
            parse({"name": "w", "offered": "yes", "nodes": nodes})


class TestTheDuplicateNamesTheWorkflow:
    def test_the_gate_keys_on_the_workflow(self):
        gate, caller = routes._RunGate(), ("host", "127.0.0.1")
        assert gate.admit(caller, "the same request", "lean") is None
        assert gate.admit(caller, "the same request", "full-team") is None
        assert gate.admit(caller, "the same request", "lean") == "duplicate"
        gate.release(caller, "the same request", "lean")
        assert gate.admit(caller, "the same request", "lean") is None
        assert gate.count() == 2

    async def test_the_same_request_runs_under_two_workflows_at_once(
            self, api_client, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "max_concurrent_runs", 4)
        await _wire_file_backed_run(tmp_path, monkeypatch,
                                    delays={"default": 0.3})
        first = asyncio.create_task(api_client.post("/api/workflows", json={
            "request": REQUEST, "workflow": "lean"}))
        await asyncio.sleep(0.1)
        other = await api_client.post("/api/workflows", json={
            "request": REQUEST, "workflow": "verify-first"})
        again = await api_client.post("/api/workflows", json={
            "request": REQUEST, "workflow": "lean"})
        # Every request is awaited before any assert, so a failing assert
        # never leaves a run in flight past the test.
        first = await first
        assert other.status_code == 202
        assert again.status_code == 409
        assert first.status_code == 202


class TestTheRename:
    def test_full_team_is_the_old_file_under_its_new_name(self):
        """Every byte is the old file's except the name line and the
        offered lines D55 (2) adds, so the graph is the one arm E ran."""
        text = (ROOT / "workflows" / "full-team.yaml").read_text(encoding="utf-8")
        assert text.startswith("name: full-team\n")
        assert text.count(OFFERED_LINES) == 1
        old = ("name: engineering-rnd\n"
               + text.removeprefix("name: full-team\n").replace(OFFERED_LINES, ""))
        assert hashlib.sha256(old.encode("utf-8")).hexdigest() == OLD_FILE_SHA256
        assert not (ROOT / "workflows" / "engineering-rnd.yaml").exists()

    @pytest.mark.parametrize("value", ["engineering-rnd",
                                       "workflows/engineering-rnd.yaml"])
    def test_the_old_name_is_refused_at_startup(self, value):
        with pytest.raises(ValidationError, match="now named 'full-team'"):
            Settings(autornd_workflow=value)
        assert Settings(autornd_workflow="full-team").autornd_workflow == "full-team"

    def test_no_current_file_names_the_old_name(self):
        """D55 §3 (5): the old name stays only in historical records and in
        the refusal. Records keep the name they were written with."""
        history = ("docs/reviews/", "docs/traces/", "docs/probes/",
                   "docs/provenance/", "docs/preregistration-",
                   "docs/handover-review.md", "evals/tier3/manifest.json",
                   "evals/tier3/README.md")
        refusal = ("autornd/config.py", "tests/test_workflow_choice.py")
        # Git-ignored: local run records and private corpora.
        ignored = ("evals/results/", "evals/private", "docs/milkhouse/",
                   "docs/private", "profiles/milkhouse.yaml", "profiles/private")
        roots = ["autornd", "tests", "workflows", "profiles", "evals", "docs",
                 ".claude/context", ".github"]
        files = [ROOT / name for name in ("README.md", "AGENTS.md", "CLAUDE.md",
                                          ".env.example", "Dockerfile",
                                          "pyproject.toml")]
        for root in roots:
            files += [p for p in (ROOT / root).rglob("*") if p.is_file()]
        found = []
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith(history + refusal + ignored) or "__pycache__" in rel:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "engineering-rnd" in text:
                found.append(rel)
        handover = (ROOT / "HANDOVER.md").read_text(encoding="utf-8")
        before, _, rest = handover.partition("\n## 6. ")
        _, _, after = rest.partition("\n## 7. ")
        if "engineering-rnd" in before + after:
            found.append("HANDOVER.md, outside §6")
        assert not found, f"these name engineering-rnd: {found}"
