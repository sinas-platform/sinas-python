"""Runtime Chats API."""

import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Union

from sinas.exceptions import SinasAPIError

if TYPE_CHECKING:
    from sinas.client import SinasClient

# The largest page GET /chats serves.
CHATS_PAGE_MAX = 200


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
    ) -> Dict[str, Any]:
        """Invoke an agent synchronously — send a message, get a reply.

        Combines chat creation and message sending into a single request/response.
        Use session_key for conversation continuity across multiple calls.

        Args:
            namespace: Agent namespace.
            agent_name: Agent name.
            message: Message to send (string or list of content blocks).
            session_key: Optional key for conversation continuity (e.g., Slack channel ID).
            reset: If True, archive the existing session and start fresh.
            input: Optional agent input variables (only used when creating a new chat).

        Returns:
            Dict with reply, chat_id, session_key, and usage.
        """
        data: Dict[str, Any] = {"message": message}
        if session_key is not None:
            data["session_key"] = session_key
        if reset:
            data["reset"] = True
        if input is not None:
            data["input"] = input

        return self._client._request(
            "POST",
            f"/agents/{namespace}/{agent_name}/invoke",
            json=data,
        )

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
    ) -> Dict[str, Any]:
        """Send message to chat and get response (blocking).

        Args:
            chat_id: Chat ID (UUID).
            content: Message content (string or list of content blocks).

        Returns:
            Message response from the agent.
        """
        return self._client._request(
            "POST",
            f"/chats/{chat_id}/messages",
            json={"content": content}
        )

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
            Server-sent event data chunks.
        """
        return self._client._stream(
            "POST",
            f"/chats/{chat_id}/messages/stream",
            json={"content": content}
        )

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
        while True:
            page = self._get_page(include_archived, q, page_size, cursor)
            yield from page.chats
            if not page.next_cursor:
                return
            if page.next_cursor == cursor:
                raise SinasAPIError("GET /chats returned the same cursor twice; stopping")
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
