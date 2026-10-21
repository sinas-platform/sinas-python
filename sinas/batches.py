"""Batches API — submit, poll, drill into, and cancel batches of executions."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from sinas.client import SinasClient


class BatchesAPI:
    """`client.batches.*` — poll, list-executions, cancel.

    For submission helpers, see `client.functions.submit_batch(...)` and
    `client.agents.submit_batch(...)`.
    """

    def __init__(self, client: "SinasClient") -> None:
        self._client = client

    def get(self, batch_id: str) -> Dict[str, Any]:
        """Aggregate status + per-status counts for a batch."""
        return self._client._request("GET", f"/batches/{batch_id}")

    def list_executions(
        self,
        batch_id: str,
        *,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Drill into the children of a batch."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        resp = self._client._request("GET", f"/batches/{batch_id}/executions", params=params)
        return resp.get("executions", [])

    def cancel(self, batch_id: str) -> Dict[str, Any]:
        """Cancel any queued/pending children of the batch."""
        return self._client._request("POST", f"/batches/{batch_id}/cancel")
