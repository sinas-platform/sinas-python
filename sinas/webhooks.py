"""Runtime Webhooks API."""

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from sinas.client import SinasClient


class WebhooksAPI:
    """Runtime Webhooks API methods."""

    def __init__(self, client: "SinasClient") -> None:
        self._client = client

    def run(
        self,
        path: str,
        method: str = "POST",
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        query: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Execute a webhook by path and HTTP method.

        Args:
            path: Webhook path (without /webhooks/ prefix).
            method: HTTP method (GET, POST, PUT, DELETE, PATCH). Defaults to POST.
            body: Optional request body (for POST/PUT/PATCH).
            headers: Optional custom headers.
            query: Optional query parameters.

        Returns:
            Webhook execution result with execution_id and result.
        """
        # Construct the full webhook URL
        url = f"/webhooks/{path}"

        # Merge custom headers with default headers
        request_headers = self._client._get_headers()
        if headers:
            request_headers.update(headers)

        # Make request with specified method
        response = self._client._client.request(
            method=method.upper(),
            url=f"{self._client.base_url}{url}",
            json=body,
            params=query,
            headers=request_headers,
        )

        self._client._handle_response(response)

        if response.status_code == 204:
            return {}

        return response.json()
