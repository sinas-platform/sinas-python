"""Ambient credentials (SINAS_API_KEY / SINAS_TOKEN) and SinasClient(use_env=...).

A process that sets SINAS_API_KEY for its own background work must not have
the clients the FastAPI integration builds per request pick that key up: an
anonymous caller of GET /auth/me would be answered as the service account.
"""

import types

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import sinas.client
from sinas import SinasClient
from sinas.integrations.fastapi import SinasAuth

BASE = "http://sinas.test"
SERVICE_KEY = "service-key"
SERVICE = {"id": "service", "email": "service@example.com"}
USER = {"id": "user", "email": "user@example.com"}


@pytest.fixture
def ambient_service_key(monkeypatch):
    monkeypatch.setenv("SINAS_API_KEY", SERVICE_KEY)
    monkeypatch.setenv("SINAS_TOKEN", "service-token")


@pytest.fixture
def backend(monkeypatch):
    """Route every SinasClient's HTTP calls to a fake Sinas; returns the
    Authorization header of each request it received."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("authorization")
        seen.append((request.url.path, auth))
        if request.url.path == "/auth/me":
            if auth is None:
                return httpx.Response(401, json={"detail": "Not authenticated"})
            if auth in (f"Bearer {SERVICE_KEY}", "Bearer service-token"):
                return httpx.Response(200, json=SERVICE)
            return httpx.Response(200, json=USER)
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"session_id": "s"})
        return httpx.Response(404, json={"detail": "not found"})

    fake_httpx = types.SimpleNamespace(
        **{name: getattr(httpx, name) for name in dir(httpx) if not name.startswith("_")}
    )
    fake_httpx.Client = lambda **kw: httpx.Client(transport=httpx.MockTransport(handler), **kw)
    monkeypatch.setattr(sinas.client, "httpx", fake_httpx)
    return seen


def _headers(client):
    return client._get_headers().get("Authorization")


def test_use_env_defaults_to_true_and_keeps_the_env_fallback(ambient_service_key):
    assert _headers(SinasClient(base_url=BASE)) == "Bearer service-token"


def test_use_env_false_ignores_ambient_credentials(ambient_service_key):
    assert _headers(SinasClient(base_url=BASE, use_env=False)) is None


def test_explicit_credentials_win_either_way(ambient_service_key):
    assert _headers(SinasClient(base_url=BASE, token="t", use_env=False)) == "Bearer t"
    assert _headers(SinasClient(base_url=BASE, api_key="k", use_env=False)) == "Bearer k"
    assert _headers(SinasClient(base_url=BASE, token="t")) == "Bearer t"


def _app(auto_error=False):
    auth = SinasAuth(base_url=BASE, auto_error=auto_error)
    app = FastAPI()
    app.include_router(auth.router, prefix="/auth")
    return TestClient(app)


def test_anonymous_me_is_not_answered_as_the_service_account(ambient_service_key, backend):
    r = _app().get("/auth/me")
    assert r.status_code == 401
    assert backend == [("/auth/me", None)]


def test_user_request_carries_only_the_callers_token(ambient_service_key, backend):
    r = _app().get("/auth/me", headers={"Authorization": "Bearer user-token"})
    assert r.status_code == 200
    assert r.json() == USER
    assert backend and all(auth == "Bearer user-token" for _, auth in backend)


def test_pre_auth_login_sends_no_credentials(ambient_service_key, backend):
    r = _app().post("/auth/login", json={"email": "user@example.com"})
    assert r.status_code == 200
    assert backend == [("/auth/login", None)]
