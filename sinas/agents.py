"""Runtime Agents API."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from sinas.client import SinasClient


class AgentsAPI:
    """`client.agents.*` — batch submission for now (other agent surface
    lives under `client.chats`)."""

    def __init__(self, client: "SinasClient") -> None:
        self._client = client

    def submit_batch(
        self,
        namespace: str,
        name: str,
        inputs: List[Dict[str, Any]],
        *,
        trigger_id_prefix: Optional[str] = None,
        callback_url: Optional[str] = None,
        batch_callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit N agent invocations as a batch.

        Each `inputs[i]` is `{"input_variables": {...}, "message": "..."}`.
        Returns `{batch_id, execution_ids, chat_ids, total, status}`.
        """
        body: Dict[str, Any] = {"inputs": inputs}
        if trigger_id_prefix is not None:
            body["trigger_id_prefix"] = trigger_id_prefix
        if callback_url is not None:
            body["callback_url"] = callback_url
        if batch_callback_url is not None:
            body["batch_callback_url"] = batch_callback_url
        return self._client._request(
            "POST",
            f"/agents/{namespace}/{name}/chats/batch",
            json=body,
        )
