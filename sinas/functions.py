"""Runtime Functions API.

For sync execution use `client.executions` after polling; for fire-and-forget
async execution use `client.functions.enqueue(...)`.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from sinas.client import SinasClient


class FunctionsAPI:
    """Runtime Functions API methods."""

    def __init__(self, client: "SinasClient") -> None:
        self._client = client

    def enqueue(
        self,
        namespace: str,
        name: str,
        input: Optional[Dict[str, Any]] = None,
        *,
        trigger_id: Optional[str] = None,
        delay_seconds: Optional[int] = None,
        callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enqueue a function for async execution (fire-and-forget).

        Returns immediately with `{execution_id, status}`. The function is run
        by a worker; the caller polls `client.executions.get(execution_id)` or
        receives a callback (if `callback_url` is set).

        Args:
            namespace: Function namespace.
            name: Function name.
            input: Input payload validated against the function's input_schema.
            trigger_id: App-supplied correlation id stored on the execution
                record (e.g. "grove:run:01HX...").
            delay_seconds: Delay before the worker picks up the job. None =
                immediate.
            callback_url: HTTPS URL Sinas POSTs to once the execution
                terminates. Must match the instance's CALLBACK_URL_HOSTS
                allowlist.

        Returns:
            `{"execution_id": "...", "status": "queued"}`
        """
        body: Dict[str, Any] = {"input": input or {}}
        if trigger_id is not None:
            body["trigger_id"] = trigger_id
        if delay_seconds is not None:
            body["delay_seconds"] = delay_seconds
        if callback_url is not None:
            body["callback_url"] = callback_url
        return self._client._request(
            "POST",
            f"/functions/{namespace}/{name}/execute/async",
            json=body,
        )

    def submit_batch(
        self,
        namespace: str,
        name: str,
        inputs: List[Dict[str, Any]],
        *,
        trigger_id_prefix: Optional[str] = None,
        delay_seconds: Optional[int] = None,
        callback_url: Optional[str] = None,
        batch_callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit N function executions as a batch.

        Returns `{batch_id, execution_ids, total, status}`. Poll progress via
        `client.batches.get(batch_id)`.
        """
        body: Dict[str, Any] = {"inputs": inputs}
        if trigger_id_prefix is not None:
            body["trigger_id_prefix"] = trigger_id_prefix
        if delay_seconds is not None:
            body["delay_seconds"] = delay_seconds
        if callback_url is not None:
            body["callback_url"] = callback_url
        if batch_callback_url is not None:
            body["batch_callback_url"] = batch_callback_url
        return self._client._request(
            "POST",
            f"/functions/{namespace}/{name}/execute/batch",
            json=body,
        )
