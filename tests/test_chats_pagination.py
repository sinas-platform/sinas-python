"""client.chats: list/list_page/iter_all against a fake GET /chats."""

import warnings

import httpx
import pytest

from sinas import ChatPage, SinasClient
from sinas.exceptions import SinasAPIError

CHATS = [{"id": f"c{i}", "title": f"chat {i}"} for i in range(7)]


def _client(handler):
    client = SinasClient(base_url="http://sinas.test", token="t", use_env=False)
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


def paginating_server(requests, chats=CHATS, cap=None):
    """A server with keyset pagination (the cursor is the next chat's index).

    With `cap`, an unpaginated list is cut there, with X-Truncated and a cursor.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(dict(request.url.params))
        params = request.url.params
        paginated = "limit" in params or "cursor" in params
        start = int(params.get("cursor", 0))
        size = int(params.get("limit", 50)) if paginated else (cap or len(chats))
        body = chats[start : start + size]
        headers = {}
        if start + size < len(chats):
            headers["X-Next-Cursor"] = str(start + size)
            if not paginated:
                headers["X-Truncated"] = "true"
        return httpx.Response(200, json=body, headers=headers)

    return handler


def old_server(requests, chats=CHATS):
    """A server from before pagination: ignores limit/cursor, returns everything."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(dict(request.url.params))
        return httpx.Response(200, json=chats)

    return handler


def test_iter_all_follows_the_cursor_to_the_end():
    requests = []
    client = _client(paginating_server(requests))
    assert list(client.chats.iter_all(page_size=3)) == CHATS
    assert requests == [
        {"limit": "3"},
        {"limit": "3", "cursor": "3"},
        {"limit": "3", "cursor": "6"},
    ]


def test_iter_all_passes_filters_on_every_page():
    requests = []
    client = _client(paginating_server(requests))
    list(client.chats.iter_all(include_archived=True, q="report", page_size=4))
    assert all(r["include_archived"] == "true" and r["q"] == "report" for r in requests)
    assert len(requests) == 2


def test_iter_all_against_a_server_without_pagination_yields_everything_once():
    requests = []
    client = _client(old_server(requests))
    assert list(client.chats.iter_all(page_size=3)) == CHATS
    assert len(requests) == 1


def test_iter_all_is_lazy():
    requests = []
    client = _client(paginating_server(requests))
    it = client.chats.iter_all(page_size=2)
    assert next(it) == CHATS[0]
    assert len(requests) == 1


def test_iter_all_stops_on_a_repeated_cursor():
    def handler(request):
        return httpx.Response(200, json=[{"id": "x"}], headers={"X-Next-Cursor": "same"})

    client = _client(handler)
    with pytest.raises(SinasAPIError, match="same cursor"):
        list(client.chats.iter_all())


def test_list_page_returns_the_cursor():
    requests = []
    client = _client(paginating_server(requests))
    page = client.chats.list_page(limit=5)
    assert page == ChatPage(chats=CHATS[:5], next_cursor="5", truncated=False)
    last = client.chats.list_page(limit=5, cursor=page.next_cursor)
    assert last == ChatPage(chats=CHATS[5:], next_cursor=None, truncated=False)
    assert requests[0] == {"limit": "5"}


def test_list_without_params_is_unchanged_under_the_cap():
    requests = []
    client = _client(paginating_server(requests, cap=10))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert client.chats.list() == CHATS
        assert client.chats.list(True) == CHATS
    assert requests == [{}, {"include_archived": "true"}]


def test_list_warns_when_the_server_truncated_it():
    requests = []
    client = _client(paginating_server(requests, cap=4))
    with pytest.warns(UserWarning, match="iter_all"):
        assert client.chats.list() == CHATS[:4]


def test_list_with_limit_and_cursor_returns_one_page():
    requests = []
    client = _client(paginating_server(requests))
    assert client.chats.list(limit=2, cursor="2") == CHATS[2:4]
    assert requests == [{"limit": "2", "cursor": "2"}]
