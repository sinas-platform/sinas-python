"""Deferred rounds (Sinas 0.5.0): turn status on invoke/send, answering
ask_user questions, tool approvals and stream events, against a fake server."""

import json

import httpx
import pytest

from sinas import SinasClient, StreamEvent
from sinas.client import ServerSentEvent, iter_sse
from sinas.exceptions import SinasAPIError, SinasNotFoundError

CHAT_ID = "11111111-1111-1111-1111-111111111111"

USAGE = {
    "calls": 1,
    "prompt_tokens": 120,
    "completion_tokens": 8,
    "total_tokens": 128,
    "cache_read_tokens": 0,
    "cache_write_tokens": 0,
    "cost_usd": 0.0004,
    "unpriced_calls": 0,
    "errors": 0,
}

QUESTION = {
    "tool_call_id": "call_ask",
    "question": "Which order number?",
    "options": ["123", "456"],
    "expires_at": "2026-10-21T10:00:00Z",
    "created_at": "2026-10-20T10:00:00Z",
}

MESSAGE = {
    "id": "22222222-2222-2222-2222-222222222222",
    "chat_id": CHAT_ID,
    "role": "assistant",
    "content": "Order 123 shipped yesterday.",
    "tool_calls": None,
    "tool_call_id": None,
    "name": None,
    "created_at": "2026-10-20T10:01:00Z",
}


class FakeServer:
    """Answers each (method, path) with a canned response; records requests."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.requests.append((request.method, request.url.path, dict(request.url.params), body))
        route = self.routes[(request.method, request.url.path)]
        return route(request) if callable(route) else route


def _client(server):
    client = SinasClient(base_url="http://sinas.test", token="t", use_env=False)
    client._client = httpx.Client(transport=httpx.MockTransport(server))
    return client


def sse(*events):
    """A text/event-stream body the way sse-starlette writes it."""
    out = []
    for event, data in events:
        payload = data if isinstance(data, str) else json.dumps(data)
        out.append(f"event: {event}\r\ndata: {payload}\r\n\r\n")
    return httpx.Response(
        200, content="".join(out).encode(), headers={"content-type": "text/event-stream"}
    )


# --- invoke / send -------------------------------------------------------


def test_invoke_returns_the_question_it_parked_on():
    server = FakeServer(
        {
            ("POST", "/agents/support/triage/invoke"): httpx.Response(
                200,
                json={
                    "status": "input_required",
                    "reply": "",
                    "chat_id": CHAT_ID,
                    "session_key": "slack:U1",
                    "pending_inputs": [QUESTION],
                    "channel_id": None,
                    "usage": USAGE,
                },
            ),
        }
    )
    result = _client(server).chats.invoke(
        "support", "triage", "Where is my order?", session_key="slack:U1"
    )
    assert result["status"] == "input_required"
    assert result["pending_inputs"] == [QUESTION]
    assert result["usage"] == USAGE
    assert server.requests[0][3] == {"message": "Where is my order?", "session_key": "slack:U1"}


def test_invoke_against_a_server_before_0_5_gets_the_defaults():
    server = FakeServer(
        {
            ("POST", "/agents/support/triage/invoke"): httpx.Response(
                200,
                json={
                    "reply": "Hi",
                    "chat_id": CHAT_ID,
                    "session_key": None,
                    "usage": None,
                },
            ),
        }
    )
    result = _client(server).chats.invoke("support", "triage", "Hello")
    assert result == {
        "reply": "Hi",
        "chat_id": CHAT_ID,
        "session_key": None,
        "usage": None,
        "status": "completed",
        "pending_inputs": [],
        "channel_id": None,
    }


def test_invoke_keeps_the_servers_turn_state():
    server = FakeServer(
        {
            ("POST", "/agents/support/triage/invoke"): httpx.Response(
                200,
                json={
                    "status": "in_progress",
                    "reply": "",
                    "chat_id": CHAT_ID,
                    "session_key": None,
                    "pending_inputs": [],
                    "channel_id": "chan-1",
                    "usage": USAGE,
                },
            ),
        }
    )
    result = _client(server).chats.invoke("support", "triage", "Run the report")
    assert (result["status"], result["channel_id"]) == ("in_progress", "chan-1")


def test_send_returns_usage_and_turn_state():
    server = FakeServer(
        {
            ("POST", f"/chats/{CHAT_ID}/messages"): httpx.Response(
                200,
                json={
                    **MESSAGE,
                    "content": "",
                    "status": "input_required",
                    "pending_inputs": [QUESTION],
                    "channel_id": None,
                    "usage": USAGE,
                },
            ),
        }
    )
    result = _client(server).chats.send(CHAT_ID, "Where is my order?")
    assert result["status"] == "input_required"
    assert result["pending_inputs"][0]["tool_call_id"] == "call_ask"
    assert result["usage"] == USAGE
    assert result["id"] == MESSAGE["id"]


def test_send_against_an_old_server_gets_the_defaults():
    server = FakeServer({("POST", f"/chats/{CHAT_ID}/messages"): httpx.Response(200, json=MESSAGE)})
    result = _client(server).chats.send(CHAT_ID, "Hi")
    assert result["status"] == "completed"
    assert result["pending_inputs"] == []
    assert result["channel_id"] is None
    assert result["usage"] is None


# --- pending input -------------------------------------------------------


def test_list_pending_inputs():
    server = FakeServer(
        {
            ("GET", f"/chats/{CHAT_ID}/pending-input"): httpx.Response(200, json=[QUESTION]),
        }
    )
    assert _client(server).chats.list_pending_inputs(CHAT_ID) == [QUESTION]


def test_answer_without_wait_returns_the_channel():
    accepted = {
        "status": "answered",
        "tool_call_id": "call_ask",
        "resumed": True,
        "resume_pending": False,
        "channel_id": "chan-2",
        "message": "Resume job enqueued.",
    }
    server = FakeServer(
        {
            ("POST", f"/chats/{CHAT_ID}/pending-input/call_ask"): httpx.Response(
                202, json=accepted
            ),
        }
    )
    result = _client(server).chats.answer(CHAT_ID, "call_ask", "123")
    assert result == accepted
    assert server.requests[0][3] == {"answer": "123"}


def test_answer_with_wait_returns_the_resumed_turn():
    resumed = {
        "status": "completed",
        "tool_call_id": "call_ask",
        "chat_id": CHAT_ID,
        "reply": MESSAGE["content"],
        "message": MESSAGE,
        "pending_inputs": [],
        "channel_id": None,
        "usage": USAGE,
    }
    server = FakeServer(
        {
            ("POST", f"/chats/{CHAT_ID}/pending-input/call_ask"): httpx.Response(200, json=resumed),
        }
    )
    result = _client(server).chats.answer(CHAT_ID, "call_ask", "123", wait=True)
    assert result == resumed
    assert server.requests[0][3] == {"answer": "123", "wait": True}


def test_answer_with_wait_can_be_asked_again():
    again = {
        "status": "input_required",
        "tool_call_id": "call_ask",
        "chat_id": CHAT_ID,
        "reply": "",
        "message": None,
        "channel_id": None,
        "usage": USAGE,
        "pending_inputs": [{**QUESTION, "tool_call_id": "call_ask2", "question": "Which item?"}],
    }
    server = FakeServer(
        {
            ("POST", f"/chats/{CHAT_ID}/pending-input/call_ask"): httpx.Response(200, json=again),
        }
    )
    result = _client(server).chats.answer(CHAT_ID, "call_ask", "123", wait=True)
    assert result["status"] == "input_required"
    assert result["pending_inputs"][0]["tool_call_id"] == "call_ask2"


def test_answer_to_an_unknown_question_raises():
    server = FakeServer(
        {
            ("POST", f"/chats/{CHAT_ID}/pending-input/nope"): httpx.Response(
                404, json={"detail": "Pending input not found or already answered"}
            ),
        }
    )
    with pytest.raises(SinasNotFoundError, match="already answered"):
        _client(server).chats.answer(CHAT_ID, "nope", "123")


# --- approvals -----------------------------------------------------------


def _approval(resume):
    return httpx.Response(
        202,
        json={
            "status": "approved",
            "tool_call_id": "call_fn",
            "channel_id": "chan-3",
            "resume": resume,
            "message": "…",
        },
    )


def test_approve_tool_with_always_allow():
    server = FakeServer(
        {
            ("POST", f"/chats/{CHAT_ID}/approve-tool/call_fn"): _approval("waiting"),
        }
    )
    result = _client(server).chats.approve_tool(CHAT_ID, "call_fn", True, always_allow=True)
    assert result["resume"] == "waiting"
    assert server.requests[0][3] == {"approved": True, "always_allow": True}


def test_reject_tool_sends_no_always_allow():
    server = FakeServer(
        {
            ("POST", f"/chats/{CHAT_ID}/approve-tool/call_fn"): _approval("queued"),
        }
    )
    result = _client(server).chats.approve_tool(CHAT_ID, "call_fn", False)
    assert (result["resume"], result["channel_id"]) == ("queued", "chan-3")
    assert server.requests[0][3] == {"approved": False}


def test_approve_tool_on_an_old_server_reads_as_queued():
    server = FakeServer(
        {
            ("POST", f"/chats/{CHAT_ID}/approve-tool/call_fn"): httpx.Response(
                202,
                json={
                    "status": "approved",
                    "tool_call_id": "call_fn",
                    "channel_id": "chan-3",
                    "message": "Resume job enqueued.",
                },
            ),
        }
    )
    assert _client(server).chats.approve_tool(CHAT_ID, "call_fn", True)["resume"] == "queued"


# --- streams -------------------------------------------------------------


def test_stream_events_surfaces_a_parked_round():
    server = FakeServer(
        {
            ("POST", f"/chats/{CHAT_ID}/messages/stream"): sse(
                ("message", {"content": "Let me check. "}),
                ("ping", ""),
                ("input_required", {"type": "input_required", **QUESTION}),
                (
                    "round_suspended",
                    {
                        "type": "round_suspended",
                        "tool_call_ids": ["call_ask"],
                        "channel_id": "chan-4",
                        "pending_completion_id": "pc",
                    },
                ),
                ("done", {"status": "suspended"}),
            ),
        }
    )
    events = list(_client(server).chats.stream_events(CHAT_ID, "Where is my order?"))
    assert [e.event for e in events] == ["message", "input_required", "round_suspended", "done"]
    assert events[1].data["question"] == "Which order number?"
    assert events[2].data["channel_id"] == "chan-4"
    assert events[3] == StreamEvent(event="done", data={"status": "suspended"})
    assert server.requests[0][3] == {"content": "Where is my order?"}


def test_stream_events_passes_include_thinking():
    server = FakeServer(
        {
            ("POST", f"/chats/{CHAT_ID}/messages/stream"): sse(("done", {"status": "completed"})),
        }
    )
    list(_client(server).chats.stream_events(CHAT_ID, "Hi", include_thinking=True))
    assert server.requests[0][3] == {"content": "Hi", "include_thinking": True}


def test_follow_channel_streams_the_resumed_turn():
    server = FakeServer(
        {
            ("GET", f"/chats/{CHAT_ID}/stream/chan-2"): sse(
                ("tool_start", {"type": "tool_start", "tool_call_id": "call_fn", "name": "lookup"}),
                ("message", {"content": "Shipped."}),
                ("done", {"status": "completed"}),
            ),
        }
    )
    events = list(_client(server).chats.follow_channel(CHAT_ID, "chan-2", include_thinking=True))
    assert [e.event for e in events] == ["tool_start", "message", "done"]
    assert server.requests[0][2] == {"last_id": "0", "include_thinking": "true"}


def test_follow_channel_raises_the_servers_error():
    server = FakeServer(
        {
            ("GET", f"/chats/{CHAT_ID}/stream/chan-x"): httpx.Response(
                403, json={"detail": "Not authorized"}
            ),
        }
    )
    with pytest.raises(SinasAPIError, match="Not authorized") as e:
        list(_client(server).chats.follow_channel(CHAT_ID, "chan-x"))
    assert e.value.status_code == 403


def test_the_old_stream_still_yields_data_only():
    server = FakeServer(
        {
            ("POST", f"/chats/{CHAT_ID}/messages/stream"): sse(
                ("message", {"content": "Hi"}), ("done", {"status": "completed"})
            ),
        }
    )
    chunks = list(_client(server).chats.stream(CHAT_ID, "Hi"))
    assert [json.loads(c) for c in chunks] == [{"content": "Hi"}, {"status": "completed"}]


def test_iter_sse_follows_the_format():
    lines = [
        ": keep-alive comment",
        "data: plain",
        "",
        "event: multi",
        "id: 7",
        "data: line one",
        "data:line two",
        "",
        "",
        "event: no-data",
        "",
        "event: cut-off",
        "data: {}",
    ]
    assert list(iter_sse(lines)) == [
        ServerSentEvent("message", "plain", None),
        ServerSentEvent("multi", "line one\nline two", "7"),
        ServerSentEvent("cut-off", "{}", None),
    ]


def test_non_json_event_data_is_kept_as_text():
    server = FakeServer(
        {
            ("GET", f"/chats/{CHAT_ID}/stream/chan-5"): sse(("message", "not json")),
        }
    )
    events = list(_client(server).chats.follow_channel(CHAT_ID, "chan-5"))
    assert events == [StreamEvent(event="message", data="not json")]
