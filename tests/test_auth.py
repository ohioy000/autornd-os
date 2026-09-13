"""Tests for authentication — registration, login, JWT, per-user filtering."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
class TestRegistration:
    async def test_register_creates_user(self, api_client):
        resp = await api_client.post("/api/auth/register", json={
            "username": "alice", "email": "alice@test.com", "password": "testpass123"
        })
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["username"] == "alice"
        assert "token" in data

    async def test_register_duplicate_username(self, api_client):
        await api_client.post("/api/auth/register", json={
            "username": "bob", "email": "bob@test.com", "password": "testpass123"
        })
        resp = await api_client.post("/api/auth/register", json={
            "username": "bob", "email": "bob2@test.com", "password": "testpass123"
        })
        assert resp.status_code == 409

    async def test_register_disabled(self, api_client, monkeypatch):
        from autornd import config
        monkeypatch.setattr(config.settings, "registration_enabled", False)
        resp = await api_client.post("/api/auth/register", json={
            "username": "carol", "email": "carol@test.com", "password": "testpass123"
        })
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, api_client):
        await api_client.post("/api/auth/register", json={
            "username": "dave", "email": "dave@test.com", "password": "testpass123"
        })
        resp = await api_client.post("/api/auth/login", json={
            "username": "dave", "password": "testpass123"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["username"] == "dave"
        assert "token" in data

    async def test_login_wrong_password(self, api_client):
        await api_client.post("/api/auth/register", json={
            "username": "eve", "email": "eve@test.com", "password": "testpass123"
        })
        resp = await api_client.post("/api/auth/login", json={
            "username": "eve", "password": "wrong"
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, api_client):
        resp = await api_client.post("/api/auth/login", json={
            "username": "nobody", "password": "testpass123"
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestJWT:
    async def test_me_anonymous(self, api_client):
        resp = await api_client.get("/api/auth/me")
        data = resp.json()["data"]
        assert data["anonymous"] is True

    async def test_me_authenticated(self, api_client):
        reg = await api_client.post("/api/auth/register", json={
            "username": "frank", "email": "frank@test.com", "password": "testpass123"
        })
        token = reg.json()["data"]["token"]
        resp = await api_client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        data = resp.json()["data"]
        assert data["anonymous"] is False
        assert data["username"] == "frank"


@pytest.mark.asyncio
class TestPerUserWorkflows:
    async def test_workflows_filtered_by_user(self, api_client):
        r1 = await api_client.post("/api/auth/register", json={
            "username": "user1", "email": "u1@test.com", "password": "testpass123"
        })
        t1 = r1.json()["data"]["token"]
        r2 = await api_client.post("/api/auth/register", json={
            "username": "user2", "email": "u2@test.com", "password": "testpass123"
        })
        t2 = r2.json()["data"]["token"]

        # user1 won't see user2's workflows (and vice versa)
        resp1 = await api_client.get("/api/workflows", headers={"Authorization": f"Bearer {t1}"})
        resp2 = await api_client.get("/api/workflows", headers={"Authorization": f"Bearer {t2}"})
        assert resp1.json()["data"] == []
        assert resp2.json()["data"] == []

    async def test_workflow_detail_is_scoped_to_owner(self, api_client, db_session):
        """Regression: /api/workflows/{id} selected on id alone, so any account
        could read (and bill Double Check against) any other account's workflow."""
        from autornd.models.workflow import Workflow, WorkflowStatus

        owner = await api_client.post("/api/auth/register", json={
            "username": "owner", "email": "owner@test.com", "password": "testpass123"
        })
        owner_id = owner.json()["data"]["id"]
        owner_token = owner.json()["data"]["token"]

        other = await api_client.post("/api/auth/register", json={
            "username": "other", "email": "other@test.com", "password": "testpass123"
        })
        other_token = other.json()["data"]["token"]

        wf = Workflow(
            request="private to owner",
            status=WorkflowStatus.COMPLETED,
            user_id=owner_id,
        )
        db_session.add(wf)
        await db_session.commit()

        mine = await api_client.get(
            f"/api/workflows/{wf.id}", headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert mine.status_code == 200
        assert mine.json()["data"]["request"] == "private to owner"

        theirs = await api_client.get(
            f"/api/workflows/{wf.id}", headers={"Authorization": f"Bearer {other_token}"}
        )
        assert theirs.status_code == 404, "another user's workflow must not be readable"

    async def test_doublecheck_routes_are_scoped_to_owner(self, api_client, db_session, monkeypatch):
        from autornd import config
        from autornd.models.workflow import Workflow, WorkflowStatus

        monkeypatch.setattr(config.settings, "model_premium", "vendor/premium")

        owner = await api_client.post("/api/auth/register", json={
            "username": "dcowner", "email": "dco@test.com", "password": "testpass123"
        })
        intruder = await api_client.post("/api/auth/register", json={
            "username": "dcother", "email": "dcx@test.com", "password": "testpass123"
        })
        intruder_token = intruder.json()["data"]["token"]

        wf = Workflow(
            request="premium spend target",
            status=WorkflowStatus.COMPLETED,
            user_id=owner.json()["data"]["id"],
        )
        db_session.add(wf)
        await db_session.commit()

        for path in (f"/api/workflows/{wf.id}/doublecheck/estimate",
                     f"/api/workflows/{wf.id}/doublecheck"):
            method = api_client.get if path.endswith("estimate") else api_client.post
            resp = await method(path, headers={"Authorization": f"Bearer {intruder_token}"})
            assert resp.status_code == 404, f"{path} leaked another user's workflow"


@pytest.mark.asyncio
class TestRegistrationInputContract:
    """Regression: username/email/password were bare `str` with no constraints,
    so an account could be created — and logged into — with an empty password."""

    @pytest.mark.parametrize("password", ["", "a", "short7c"])
    async def test_weak_passwords_rejected(self, api_client, password):
        resp = await api_client.post("/api/auth/register", json={
            "username": "weakpw", "email": "weak@test.com", "password": password
        })
        assert resp.status_code == 422

    async def test_malformed_email_rejected(self, api_client):
        resp = await api_client.post("/api/auth/register", json={
            "username": "bademail", "email": "not-an-email", "password": "testpass123"
        })
        assert resp.status_code == 422

    async def test_short_username_rejected(self, api_client):
        resp = await api_client.post("/api/auth/register", json={
            "username": "ab", "email": "ab@test.com", "password": "testpass123"
        })
        assert resp.status_code == 422
