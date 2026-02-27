"""Runtime State API."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from sinas.client import SinasClient


class StateAPI:
    """Runtime State API methods."""

    def __init__(self, client: "SinasClient") -> None:
        self._client = client

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        visibility: str = "private",
        group_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        relevance_score: Optional[float] = None,
        expires_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new state entry.

        Args:
            namespace: State namespace.
            key: State key.
            value: State value (JSON-serializable).
            visibility: Visibility level ("private", "group", "public"). Defaults to "private".
            group_id: Group ID (required if visibility is "group").
            assistant_id: Optional assistant ID.
            description: Optional description.
            tags: Optional list of tags.
            relevance_score: Optional relevance score (0-1).
            expires_at: Optional expiration datetime (ISO 8601 format).

        Returns:
            Created state entry.
        """
        data: Dict[str, Any] = {
            "namespace": namespace,
            "key": key,
            "value": value,
            "visibility": visibility,
        }
        if group_id is not None:
            data["group_id"] = group_id
        if assistant_id is not None:
            data["assistant_id"] = assistant_id
        if description is not None:
            data["description"] = description
        if tags is not None:
            data["tags"] = tags
        if relevance_score is not None:
            data["relevance_score"] = relevance_score
        if expires_at is not None:
            data["expires_at"] = expires_at

        return self._client._request("POST", "/states", json=data)

    def get(self, state_id: str) -> Dict[str, Any]:
        """Get a specific state entry.

        Args:
            state_id: State ID (UUID).

        Returns:
            State entry.
        """
        return self._client._request("GET", f"/states/{state_id}")

    def list(
        self,
        namespace: Optional[str] = None,
        visibility: Optional[str] = None,
        assistant_id: Optional[str] = None,
        tags: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List state entries accessible to the current user.

        Args:
            namespace: Filter by namespace.
            visibility: Filter by visibility ("private", "group", "public").
            assistant_id: Filter by assistant ID.
            tags: Comma-separated list of tags to filter by.
            search: Search in keys and descriptions.
            skip: Number of entries to skip (pagination).
            limit: Maximum number of entries to return (1-1000).

        Returns:
            List of state entries.
        """
        params: Dict[str, Any] = {"skip": skip, "limit": limit}
        if namespace is not None:
            params["namespace"] = namespace
        if visibility is not None:
            params["visibility"] = visibility
        if assistant_id is not None:
            params["assistant_id"] = assistant_id
        if tags is not None:
            params["tags"] = tags
        if search is not None:
            params["search"] = search

        return self._client._request("GET", "/states", params=params)

    def update(
        self,
        state_id: str,
        value: Optional[Any] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        relevance_score: Optional[float] = None,
        expires_at: Optional[str] = None,
        visibility: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a state entry.

        Args:
            state_id: State ID (UUID).
            value: New value.
            description: New description.
            tags: New list of tags.
            relevance_score: New relevance score.
            expires_at: New expiration datetime.
            visibility: New visibility level.

        Returns:
            Updated state entry.
        """
        data: Dict[str, Any] = {}
        if value is not None:
            data["value"] = value
        if description is not None:
            data["description"] = description
        if tags is not None:
            data["tags"] = tags
        if relevance_score is not None:
            data["relevance_score"] = relevance_score
        if expires_at is not None:
            data["expires_at"] = expires_at
        if visibility is not None:
            data["visibility"] = visibility

        return self._client._request("PUT", f"/states/{state_id}", json=data)

    def delete(self, state_id: str) -> Dict[str, Any]:
        """Delete a state entry.

        Args:
            state_id: State ID (UUID).

        Returns:
            Deletion confirmation message.
        """
        return self._client._request("DELETE", f"/states/{state_id}")
