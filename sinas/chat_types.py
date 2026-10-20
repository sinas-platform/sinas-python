"""Response shapes of the chat and invoke endpoints.

These are ``TypedDict``s: at runtime every response is still a plain ``dict``,
so code that indexes responses keeps working; the types only tell your editor
and type checker which keys exist. Timestamps are ISO 8601 strings, ids are
UUID strings.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, TypedDict

#: How a synchronously answered turn ended (Sinas 0.5.0+).
#:
#: - ``"completed"``: the turn's final reply is in the response.
#: - ``"input_required"``: the agent asked the user (``ask_user``) and the turn
#:   waits for the answer. ``pending_inputs`` lists the questions; answer with
#:   ``client.chats.answer()``.
#: - ``"in_progress"``: the turn goes on without this request (background work
#:   it waits for outlasted the request's time budget). Follow it with
#:   ``client.chats.follow_channel(chat_id, channel_id)`` or read the chat later.
#: - ``"injected"``: the chat was busy (a turn running, or one parked on a
#:   question or background work), so the message was delivered into that
#:   turn. Nothing was answered by this request; ``pending_inputs`` and
#:   ``channel_id`` say what that turn waits on.
TurnStatus = Literal["completed", "input_required", "in_progress", "injected"]


class TurnUsage(TypedDict):
    """LLM usage of one request: every LLM call made while answering it.

    Covers the reply and its tool rounds, plus a continuation the request
    waited for. Not included: earlier turns of the same chat, delegated
    sub-agents, background compaction.
    """

    calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    #: Cost of the priced calls in USD; None when calls were made but none
    #: could be priced.
    cost_usd: Optional[float]
    unpriced_calls: int
    errors: int


class PendingInput(TypedDict):
    """An ``ask_user`` question a turn is parked on."""

    tool_call_id: str
    question: str
    #: Suggested answers, if the agent gave any. Free text is accepted too.
    options: Optional[List[str]]
    #: When the question expires; the turn then resumes without an answer.
    expires_at: Optional[str]
    created_at: Optional[str]


class TurnState(TypedDict):
    """The fields every synchronous turn result carries (Sinas 0.5.0+).

    Against an older server the SDK fills in the defaults the server would
    have sent: ``status="completed"``, ``pending_inputs=[]``,
    ``channel_id=None``.
    """

    status: TurnStatus
    #: The chat's open ask_user questions (input_required, injected).
    pending_inputs: List[PendingInput]
    #: The stream channel of a turn still going on (in_progress), or of the
    #: parked turn an injected message went to.
    channel_id: Optional[str]


class Message(TypedDict):
    """A stored chat message."""

    id: str
    chat_id: str
    role: str
    content: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]]
    tool_call_id: Optional[str]
    name: Optional[str]
    created_at: str


class InvokeResult(TurnState):
    """Result of ``client.chats.invoke()``."""

    #: The final reply (completed). For input_required / in_progress, what the
    #: agent said before it asked or started waiting (often empty); for
    #: injected, empty.
    reply: str
    chat_id: str
    session_key: Optional[str]
    #: LLM usage of this invoke only; None if it could not be determined.
    usage: Optional[TurnUsage]


class MessageSendResult(Message, TurnState):
    """Result of ``client.chats.send()``.

    The message is the final reply (completed), the assistant message that
    asked or started waiting (input_required / in_progress), or the user
    message as stored (injected).
    """

    #: LLM usage of this send only; None if it could not be determined (or
    #: the server predates per-request usage).
    usage: Optional[TurnUsage]


class PendingInputAnswerAccepted(TypedDict):
    """Result of ``client.chats.answer(..., wait=False)`` (HTTP 202)."""

    status: Literal["answered"]
    tool_call_id: str
    #: The answer was the round's last completion; its resume is queued.
    resumed: bool
    #: The last completion, but the resume could not be queued yet; the
    #: server retries it shortly.
    resume_pending: bool
    #: Where the resumed turn streams (``follow_channel``), when ``resumed``
    #: or ``resume_pending``.
    channel_id: Optional[str]
    message: str


class PendingInputAnswerResult(TurnState):
    """Result of ``client.chats.answer(..., wait=True)`` (HTTP 200): the
    resumed turn's outcome. ``status`` is ``input_required`` again if the
    agent asked another question."""

    tool_call_id: str
    chat_id: str
    reply: str
    #: The message ``reply`` comes from, when there is one.
    message: Optional[Message]
    #: LLM usage of the continuation this answer resumed, as far as the
    #: request waited for it.
    usage: Optional[TurnUsage]


class ToolApprovalResult(TypedDict):
    """Result of ``client.chats.approve_tool()`` (HTTP 202)."""

    status: Literal["approved", "rejected"]
    tool_call_id: str
    #: The channel the round resumes on (``follow_channel``).
    channel_id: str
    #: ``"queued"``: this was the round's last decision and its resume is
    #: queued, follow ``channel_id``. ``"waiting"``: other calls of the same
    #: round still need a decision; nothing resumes yet.
    resume: Literal["waiting", "queued"]
    message: str


@dataclass
class StreamEvent:
    """One server-sent event of a chat stream.

    Attributes:
        event: The SSE event name. ``"message"`` carries content chunks
            (``data["content"]``, ``data["thinking"]``, ...). Typed events:
            ``"tool_start"``, ``"tool_end"``, ``"approval_required"``,
            ``"input_required"`` (an ask_user question: ``tool_call_id``,
            ``question``, ``options``, ``expires_at``), ``"round_suspended"``
            (the round parked: ``tool_call_ids``, ``channel_id``, and
            ``usage`` when it comes from a resumed round). The stream ends
            with ``"done"`` (``data["status"]`` is ``"completed"``, or
            ``"suspended"`` when the round waits on the user alone) or
            ``"error"`` (``data["error"]``).
        data: The event's JSON payload (a dict), or the raw text when it is
            not JSON.
        id: The SSE event id, if the server sent one.
    """

    event: str
    data: Any
    id: Optional[str] = None
