"""Runtime Chats API."""

from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Union

if TYPE_CHECKING:
    from sinas.client import SinasClient


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

    def list(self, include_archived: bool = False) -> List[Dict[str, Any]]:
        """List all chats for the current user.

        Args:
            include_archived: If True, include archived (soft-deleted) chats.

        Returns:
            List of chats.
        """
        params = {"include_archived": "true"} if include_archived else {}
        return self._client._request("GET", "/chats", params=params)

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
