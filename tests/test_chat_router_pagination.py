"""The FastAPI chat router's list endpoint, mounted in an app, against a fake GET /chats."""

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sinas import SinasClient
from sinas.integrations.fastapi import SinasAuth
from sinas.integrations.routers import create_chat_router

CHATS = [{"id": f"c{i}", "title": f"chat {i}"} for i in range(7)]


def _backend(requests, cap=None):
    """Sinas's GET /chats with keyset pagination (the cursor is the next chat's index).

    With `cap`, an unpaginated list is cut there, with X-Truncated and a cursor.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/chats"
        requests.append(dict(request.url.params))
        params = request.url.params
        paginated = "limit" in params or "cursor" in params
        start = int(params.get("cursor", 0))
        size = int(params.get("limit", 50)) if paginated else (cap or len(CHATS))
        headers = {}
        if start + size < len(CHATS):
            headers["X-Next-Cursor"] = str(start + size)
            if not paginated:
                headers["X-Truncated"] = "true"
        return httpx.Response(200, json=CHATS[start : start + size], headers=headers)

    return handler


def _app(requests, cap=None):
    """An app with the chat router mounted, its auth dependency yielding a client
    whose HTTP calls go to the fake backend."""
    sinas = SinasClient(base_url="http://sinas.test", token="t", use_env=False)
    sinas._client = httpx.Client(transport=httpx.MockTransport(_backend(requests, cap)))

    router = create_chat_router("http://sinas.test")
    auth = next(
        dep.call
        for route in router.routes
        for dep in route.dependant.dependencies
        if isinstance(dep.call, SinasAuth)
    )
    app = FastAPI()
    app.include_router(router, prefix="/chats")
    app.dependency_overrides[auth] = lambda: sinas
    return TestClient(app)


def test_router_forwards_pagination_and_filters_and_returns_the_cursor():
    requests = []
    http = _app(requests)
    r = http.get(
        "/chats", params={"include_archived": "true", "q": "report", "limit": 3, "cursor": "3"}
    )
    assert r.status_code == 200
    assert r.json() == CHATS[3:6]
    assert r.headers["X-Next-Cursor"] == "6"
    assert "X-Truncated" not in r.headers
    assert requests == [{"include_archived": "true", "q": "report", "limit": "3", "cursor": "3"}]


def test_router_omits_the_cursor_on_the_last_page():
    requests = []
    http = _app(requests)
    r = http.get("/chats", params={"limit": 3, "cursor": "6"})
    assert r.json() == CHATS[6:]
    assert "X-Next-Cursor" not in r.headers
    assert "X-Truncated" not in r.headers


def test_router_without_pagination_args_forwards_none_and_passes_truncation_through():
    requests = []
    http = _app(requests, cap=4)
    r = http.get("/chats")
    assert r.status_code == 200
    assert r.json() == CHATS[:4]
    assert r.headers["X-Truncated"] == "true"
    assert r.headers["X-Next-Cursor"] == "4"
    assert requests == [{}]

    # A client can continue the truncated list from the cursor it was given.
    r = http.get("/chats", params={"limit": 50, "cursor": r.headers["X-Next-Cursor"]})
    assert r.json() == CHATS[4:]
    assert "X-Next-Cursor" not in r.headers
    assert requests[1] == {"limit": "50", "cursor": "4"}


def test_router_without_pagination_args_under_the_cap_returns_everything_plainly():
    requests = []
    http = _app(requests, cap=10)
    r = http.get("/chats")
    assert r.json() == CHATS
    assert "X-Next-Cursor" not in r.headers
    assert "X-Truncated" not in r.headers
    assert requests == [{}]
