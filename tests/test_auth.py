"""Tests for authentication — registration, login, JWT, per-user filtering."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
class TestRegistration:
    async def test_register_creates_user(self, api_client):
        resp = await api_client.post("/api/auth/register", json={
            "username": "alice", "email": "alice@test.com", "password": "pass123"
        })
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["username"] == "alice"
        assert "token" in data

    async def test_register_duplicate_username(self, api_client):
        await api_client.post("/api/auth/register", json={
            "username": "bob", "email": "bob@test.com", "password": "pass123"
        })
        resp = await api_client.post("/api/auth/register", json={
            "username": "bob", "email": "bob2@test.com", "password": "pass123"
        })
        assert resp.status_code == 409

    async def test_register_disabled(self, api_client, monkeypatch):
        from autornd import config
        monkeypatch.setattr(config.settings, "registration_enabled", False)
        resp = await api_client.post("/api/auth/register", json={
            "username": "carol", "email": "carol@test.com", "password": "pass123"
        })
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, api_client):
        await api_client.post("/api/auth/register", json={
            "username": "dave", "email": "dave@test.com", "password": "pass123"
        })
        resp = await api_client.post("/api/auth/login", json={
            "username": "dave", "password": "pass123"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["username"] == "dave"
        assert "token" in data

    async def test_login_wrong_password(self, api_client):
        await api_client.post("/api/auth/register", json={
            "username": "eve", "email": "eve@test.com", "password": "pass123"
        })
        resp = await api_client.post("/api/auth/login", json={
            "username": "eve", "password": "wrong"
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, api_client):
        resp = await api_client.post("/api/auth/login", json={
            "username": "nobody", "password": "pass123"
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
            "username": "frank", "email": "frank@test.com", "password": "pass123"
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
            "username": "user1", "email": "u1@test.com", "password": "pass123"
        })
        t1 = r1.json()["data"]["token"]
        r2 = await api_client.post("/api/auth/register", json={
            "username": "user2", "email": "u2@test.com", "password": "pass123"
        })
        t2 = r2.json()["data"]["token"]

        # user1 won't see user2's workflows (and vice versa)
        resp1 = await api_client.get("/api/workflows", headers={"Authorization": f"Bearer {t1}"})
        resp2 = await api_client.get("/api/workflows", headers={"Authorization": f"Bearer {t2}"})
        assert resp1.json()["data"] == []
        assert resp2.json()["data"] == []
