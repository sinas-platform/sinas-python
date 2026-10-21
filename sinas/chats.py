"""Runtime Chats API."""

import json
import warnings
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    List,
    Literal,
    Optional,
    Set,
    Union,
    cast,
    overload,
)

from sinas.chat_types import (
    InvokeResult,
    MessageSendResult,
    PendingInput,
    PendingInputAnswerAccepted,
    PendingInputAnswerResult,
    StreamEvent,
    ToolApprovalResult,
)
from sinas.exceptions import SinasAPIError

if TYPE_CHECKING:
    from sinas.client import ServerSentEvent, SinasClient

# The largest page GET /chats serves.
CHATS_PAGE_MAX = 200


def _with_turn_state(data: Dict[str, Any]) -> Dict[str, Any]:
    """Fill in the turn-state fields a server before Sinas 0.5.0 leaves out,
    with the values a 0.5.0 server sends for a turn that simply completed."""
    data.setdefault("status", "completed")
    data.setdefault("pending_inputs", [])
    data.setdefault("channel_id", None)
    data.setdefault("usage", None)
    return data


def _stream_event(sse: "ServerSentEvent") -> StreamEvent:
    try:
        data: Any = json.loads(sse.data)
    except ValueError:
        data = sse.data
    return StreamEvent(event=sse.event, data=data, id=sse.id)


@dataclass
class ChatPage:
    """One response of GET /chats.

    Attributes:
        chats: The chats, most recently updated first.
        next_cursor: Pass as ``cursor`` to get the chats after these; None on
            the last page (and from servers that do not paginate).
        truncated: The server cut an unpaginated list short (more chats than
            its CHATS_UNPAGINATED_MAX); ``next_cursor`` continues it.
    """

    chats: List[Dict[str, Any]] = field(default_factory=list)
    next_cursor: Optional[str] = None
    truncated: bool = False


class ChatsAPI:
    """Runtime Chats API methods."""

    def __init__(self, client: "SinasClient") -> None:
        self._client = client

    def invoke(
        self,
        namespace: str,
        agent_name: str,
        message: Union[str, List[Dict[str, Any]]],
        session_key: Optional[str] = None,
        reset: bool = False,
        input: Optional[Dict[str, Any]] = None,
    ) -> InvokeResult:
        """Invoke an agent synchronously — send a message, get a reply.

        Combines chat creation and message sending into a single request/response.
        Use session_key for conversation continuity across multiple calls.

        Check ``status`` before using ``reply``: a turn can end without a
        final reply. ``"input_required"`` means the agent asked a question
        (``pending_inputs``; answer it with ``answer()``), ``"in_progress"``
        that background work outlasted the request (follow ``channel_id``
        with ``follow_channel()``), and ``"injected"`` that the session's
        chat was busy, so the message went into the turn already there.

        Args:
            namespace: Agent namespace.
            agent_name: Agent name.
            message: Message to send (string or list of content blocks).
            session_key: Optional key for conversation continuity (e.g., Slack channel ID).
            reset: If True, archive the existing session and start fresh.
            input: Optional agent input variables (only used when creating a new chat).

        Returns:
            An InvokeResult: reply, chat_id, session_key, usage (the LLM
            usage of this invoke), status, pending_inputs and channel_id.
        """
        data: Dict[str, Any] = {"message": message}
        if session_key is not None:
            data["session_key"] = session_key
        if reset:
            data["reset"] = True
        if input is not None:
            data["input"] = input

        result = self._client._request(
            "POST",
            f"/agents/{namespace}/{agent_name}/invoke",
            json=data,
        )
        return cast(InvokeResult, _with_turn_state(result))

    def create(
        self,
        namespace: str,
        agent_name: str,
        input: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
        expires_in: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new chat with an agent.

        Args:
            namespace: Agent namespace.
            agent_name: Agent name.
            input: Optional input data validated against agent's input_schema.
            title: Optional chat title.
            expires_in: Optional TTL in seconds. Chat will be hard-deleted after this duration.

        Returns:
            Created chat information.
        """
        data: Dict[str, Any] = {}
        if input is not None:
            data["input"] = input
        if title is not None:
            data["title"] = title
        if expires_in is not None:
            data["expires_in"] = expires_in

        return self._client._request(
            "POST",
            f"/agents/{namespace}/{agent_name}/chats",
            json=data
        )

    def send(
        self,
        chat_id: str,
        content: Union[str, List[Dict[str, Any]]],
    ) -> MessageSendResult:
        """Send message to chat and get response (blocking).

        A turn that waits on background work is followed to its reply within
        the chat's job timeout. Check ``status``: with ``"input_required"``
        the returned message is the assistant message that asked, and
        ``pending_inputs`` holds the questions (answer with ``answer()``);
        see ``invoke()`` for the other statuses.

        Args:
            chat_id: Chat ID (UUID).
            content: Message content (string or list of content blocks).

        Returns:
            A MessageSendResult: the message's fields plus usage, status,
            pending_inputs and channel_id.
        """
        result = self._client._request(
            "POST",
            f"/chats/{chat_id}/messages",
            json={"content": content}
        )
        return cast(MessageSendResult, _with_turn_state(result))

    def stream(
        self,
        chat_id: str,
        content: Union[str, List[Dict[str, Any]]],
    ) -> Iterator[str]:
        """Send message to chat and stream response via SSE.

        Args:
            chat_id: Chat ID (UUID).
            content: Message content (string or list of content blocks).

        Yields:
            Server-sent event data chunks. Event names are not included; use
            ``stream_events()`` to tell ``input_required``, ``done`` and the
            other events apart.
        """
        return self._client._stream(
            "POST",
            f"/chats/{chat_id}/messages/stream",
            json={"content": content}
        )

    def stream_events(
        self,
        chat_id: str,
        content: Union[str, List[Dict[str, Any]]],
        *,
        include_thinking: bool = False,
    ) -> Iterator[StreamEvent]:
        """Send a message to a chat and stream the turn as parsed events.

        Each StreamEvent has the SSE event name and its decoded JSON data.
        Content arrives in ``"message"`` events. When the agent asks the user
        something, the stream sends ``"input_required"`` (the question),
        then ``"round_suspended"`` (with the round's ``channel_id``), and
        ends with ``"done"`` ``{"status": "suspended"}``: answer with
        ``answer()``, and follow the channel it returns. A round waiting on a
        background run keeps the stream open until the run's continuation
        is done. Heartbeat pings are skipped.

        Args:
            chat_id: Chat ID (UUID).
            content: Message content (string or list of content blocks).
            include_thinking: Send the model's thinking text in
                ``data["thinking"]`` (otherwise only an empty ``thinking``
                when the model starts thinking).

        Yields:
            StreamEvents, until ``"done"`` or ``"error"``.
        """
        body: Dict[str, Any] = {"content": content}
        if include_thinking:
            body["include_thinking"] = True
        return self._events(
            self._client._stream_sse("POST", f"/chats/{chat_id}/messages/stream", json=body)
        )

    def follow_channel(
        self,
        chat_id: str,
        channel_id: str,
        *,
        last_id: str = "0",
        include_thinking: bool = False,
    ) -> Iterator[StreamEvent]:
        """Stream a turn from its channel (GET /chats/{id}/stream/{channel_id}).

        Use it for the ``channel_id`` of an ``in_progress`` result, of an
        answer (``answer()`` without ``wait``), of a tool approval, or of a
        ``round_suspended`` event. When the round moves to another channel
        while you follow it (its question answered elsewhere), the server
        follows it there; the stream ends with ``"done"`` or ``"error"``,
        or ``"done"`` ``{"status": "suspended"}`` when the round parks on a
        question.

        Args:
            chat_id: Chat ID (UUID).
            channel_id: The stream channel to follow.
            last_id: Redis stream entry ID to resume after; ``"0"`` replays
                the channel from its start.
            include_thinking: Stream the model's thinking text.

        Yields:
            StreamEvents, as ``stream_events()``.
        """
        params: Dict[str, Any] = {"last_id": last_id}
        if include_thinking:
            params["include_thinking"] = "true"
        return self._events(
            self._client._stream_sse(
                "GET", f"/chats/{chat_id}/stream/{channel_id}", params=params
            )
        )

    @staticmethod
    def _events(stream: Iterator["ServerSentEvent"]) -> Iterator[StreamEvent]:
        for sse in stream:
            if sse.event == "ping":
                continue
            yield _stream_event(sse)

    def list_pending_inputs(self, chat_id: str) -> List[PendingInput]:
        """List the ask_user questions a chat's turn is parked on.

        Args:
            chat_id: Chat ID (UUID).

        Returns:
            The open questions: tool_call_id, question, options, expires_at,
            created_at. Empty when the chat waits on nothing.
        """
        return cast(
            List[PendingInput], self._client._request("GET", f"/chats/{chat_id}/pending-input")
        )

    @overload
    def answer(
        self,
        chat_id: str,
        tool_call_id: str,
        answer: str,
        wait: Literal[False] = False,
    ) -> PendingInputAnswerAccepted: ...

    @overload
    def answer(
        self,
        chat_id: str,
        tool_call_id: str,
        answer: str,
        wait: Literal[True],
    ) -> PendingInputAnswerResult: ...

    @overload
    def answer(
        self,
        chat_id: str,
        tool_call_id: str,
        answer: str,
        wait: bool = False,
    ) -> Union[PendingInputAnswerAccepted, PendingInputAnswerResult]: ...

    def answer(
        self,
        chat_id: str,
        tool_call_id: str,
        answer: str,
        wait: bool = False,
    ) -> Union[PendingInputAnswerAccepted, PendingInputAnswerResult]:
        """Answer an ask_user question; the answer becomes its tool result.

        Works however the turn was started (invoke, send, a stream, a
        queued turn).

        Args:
            chat_id: Chat ID (UUID).
            tool_call_id: The question's ``tool_call_id`` (from
                ``pending_inputs``, ``list_pending_inputs()`` or an
                ``input_required`` event).
            answer: The answer text.
            wait: Wait for the resumed turn and return its result (Sinas
                0.5.0+), instead of a channel to stream it from.

        Returns:
            Without ``wait``, a PendingInputAnswerAccepted: ``resumed`` (the
            turn resumes; follow ``channel_id`` with ``follow_channel()``)
            or not (the round still waits on other completions).

            With ``wait``, a PendingInputAnswerResult shaped like an invoke
            result: ``status``, ``reply``, ``message``, ``pending_inputs``
            (the next question if the agent asks again), ``channel_id`` and
            ``usage`` of the resumed turn.

        Raises:
            SinasNotFoundError: No open question with that id.
            SinasAPIError: 409 when the question was already resolved.
        """
        body: Dict[str, Any] = {"answer": answer}
        if wait:
            body["wait"] = True
        result = self._client._request(
            "POST", f"/chats/{chat_id}/pending-input/{tool_call_id}", json=body
        )
        if wait:
            return cast(PendingInputAnswerResult, _with_turn_state(result))
        return cast(PendingInputAnswerAccepted, result)

    def approve_tool(
        self,
        chat_id: str,
        tool_call_id: str,
        approved: bool,
        *,
        always_allow: bool = False,
    ) -> ToolApprovalResult:
        """Approve or reject a tool call that waits for approval.

        The calls to decide on come from ``"approval_required"`` stream
        events, or the chat's ``pending_approvals`` (``get()``).

        Args:
            chat_id: Chat ID (UUID).
            tool_call_id: The tool call to decide on.
            approved: True to run the call, False to reject it (the model
                gets a rejection result).
            always_allow: With ``approved``, also allow this tool for the
                rest of the chat without asking again. Ignored when
                rejecting.

        Returns:
            A ToolApprovalResult. ``resume == "queued"``: this was the
            round's last decision; follow ``channel_id`` with
            ``follow_channel()``. ``resume == "waiting"``: other calls of
            the round still need a decision.
        """
        body: Dict[str, Any] = {"approved": approved}
        if always_allow:
            body["always_allow"] = True
        result = self._client._request(
            "POST", f"/chats/{chat_id}/approve-tool/{tool_call_id}", json=body
        )
        result.setdefault("resume", "queued")  # servers before 0.5.0 resumed on every decision
        return cast(ToolApprovalResult, result)

    def get(self, chat_id: str) -> Dict[str, Any]:
        """Get a chat with all messages.

        Args:
            chat_id: Chat ID (UUID).

        Returns:
            Chat information with messages.
        """
        return self._client._request("GET", f"/chats/{chat_id}")

    def list(
        self,
        include_archived: bool = False,
        *,
        q: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List the current user's chats, most recently updated first.

        Without ``limit`` or ``cursor`` this asks for every chat in one
        response, as before. Servers cap that list (CHATS_UNPAGINATED_MAX,
        10,000 by default): past the cap you get the first ones and a
        ``UserWarning``. Use ``iter_all()`` to go through every chat, or
        ``list_page()`` to page yourself.

        Args:
            include_archived: If True, include archived (soft-deleted) chats.
            q: Only chats whose title contains this text (case-insensitive).
            limit: Page size (1-200). Giving ``limit`` or ``cursor`` returns
                one page.
            cursor: A page's ``next_cursor``, to get the chats after it.

        Returns:
            List of chats.
        """
        page = self._get_page(include_archived, q, limit, cursor)
        if page.truncated:
            warnings.warn(
                "GET /chats returned only the first "
                f"{len(page.chats)} chats (the server's cap on an unpaginated list); "
                "use client.chats.iter_all() to get them all",
                UserWarning,
                stacklevel=2,
            )
        return page.chats

    def list_page(
        self,
        include_archived: bool = False,
        *,
        q: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> ChatPage:
        """Get one page of the current user's chats, with the cursor for the next.

        Args:
            include_archived: If True, include archived (soft-deleted) chats.
            q: Only chats whose title contains this text (case-insensitive).
            limit: Page size (1-200).
            cursor: The previous page's ``next_cursor``; None for the first page.

        Returns:
            A ChatPage. Its ``next_cursor`` is None on the last page. A server
            that predates pagination ignores ``limit`` and returns every chat
            in one page without a cursor.
        """
        return self._get_page(include_archived, q, limit, cursor)

    def iter_all(
        self,
        include_archived: bool = False,
        *,
        q: Optional[str] = None,
        page_size: int = CHATS_PAGE_MAX,
    ) -> Iterator[Dict[str, Any]]:
        """Iterate over all of the current user's chats, a page at a time.

        Follows the server's ``X-Next-Cursor`` until the last page. Against a
        server that predates pagination, the first response holds every chat
        and carries no cursor, so this yields them all and stops.

        Chats created or updated while iterating move to the front of the
        list: the rest are neither repeated nor skipped, and the moved ones
        are not yielded again.

        Args:
            include_archived: If True, include archived (soft-deleted) chats.
            q: Only chats whose title contains this text (case-insensitive).
            page_size: Chats per request (1-200).

        Yields:
            Chats, most recently updated first.
        """
        cursor: Optional[str] = None
        # Every cursor followed so far: a server that hands back any earlier
        # cursor (the same one, or a cycle such as A -> B -> A) would
        # otherwise make this loop forever.
        seen: Set[str] = set()
        while True:
            page = self._get_page(include_archived, q, page_size, cursor)
            yield from page.chats
            if not page.next_cursor:
                return
            if page.next_cursor in seen:
                raise SinasAPIError(
                    f"GET /chats returned cursor {page.next_cursor!r} again; stopping"
                )
            seen.add(page.next_cursor)
            cursor = page.next_cursor

    def _get_page(
        self,
        include_archived: bool,
        q: Optional[str],
        limit: Optional[int],
        cursor: Optional[str],
    ) -> ChatPage:
        params: Dict[str, Any] = {}
        if include_archived:
            params["include_archived"] = "true"
        if q is not None:
            params["q"] = q
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        response = self._client._request_response("GET", "/chats", params=params)
        return ChatPage(
            chats=response.json(),
            next_cursor=response.headers.get("x-next-cursor") or None,
            truncated=response.headers.get("x-truncated", "").lower() == "true",
        )

    def update(
        self,
        chat_id: str,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a chat.

        Args:
            chat_id: Chat ID (UUID).
            title: New title.

        Returns:
            Updated chat information.
        """
        data: Dict[str, Any] = {}
        if title is not None:
            data["title"] = title

        return self._client._request("PUT", f"/chats/{chat_id}", json=data)

    def delete(self, chat_id: str) -> None:
        """Delete a chat and all its messages.

        Args:
            chat_id: Chat ID (UUID).
        """
        self._client._request("DELETE", f"/chats/{chat_id}")
