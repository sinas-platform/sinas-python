"""SINAS SDK client."""

import os
from typing import Any, Dict, Iterator, Optional

import httpx

from sinas.auth import AuthAPI
from sinas.chats import ChatsAPI
from sinas.executions import ExecutionsAPI
from sinas.exceptions import SinasAPIError, SinasAuthError, SinasNotFoundError, SinasValidationError
from sinas.files import FilesAPI
from sinas.state import StateAPI
from sinas.templates import TemplatesAPI
from sinas.webhooks import WebhooksAPI


class SinasClient:
    """SINAS Runtime API client."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize SINAS Runtime client.

        Args:
            base_url: Base URL for SINAS API. Defaults to SINAS_BASE_URL env var.
            api_key: API key for authentication. Defaults to SINAS_API_KEY env var.
            token: JWT token for authentication. Defaults to SINAS_TOKEN env var.
            timeout: Request timeout in seconds.
        """
        self.base_url = (base_url or os.getenv("SINAS_BASE_URL", "")).rstrip("/")
        if not self.base_url:
            raise ValueError(
                "base_url must be provided or SINAS_BASE_URL environment variable must be set"
            )

        self._api_key = api_key or os.getenv("SINAS_API_KEY")
        self._token = token or os.getenv("SINAS_TOKEN")
        self._timeout = timeout

        self._client = httpx.Client(timeout=timeout)

        # Initialize Runtime API modules
        self.auth = AuthAPI(self)
        self.state = StateAPI(self)
        self.chats = ChatsAPI(self)
        self.webhooks = WebhooksAPI(self)
        self.executions = ExecutionsAPI(self)
        self.templates = TemplatesAPI(self)
        self.files = FilesAPI(self)

    def __enter__(self) -> "SinasClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        headers = {"Content-Type": "application/json"}

        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        elif self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        return headers

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH).
            path: API path (without base URL).
            json: JSON request body.
            params: Query parameters.

        Returns:
            Response data.

        Raises:
            SinasAPIError: If the request fails.
        """
        url = f"{self.base_url}{path}"
        headers = self._get_headers()

        try:
            response = self._client.request(
                method=method,
                url=url,
                json=json,
                params=params,
                headers=headers,
            )
            self._handle_response(response)

            if response.status_code == 204:
                return None

            return response.json()
        except httpx.HTTPError as e:
            raise SinasAPIError(f"HTTP request failed: {e}")

    def _stream(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
    ) -> Iterator[str]:
        """Make a streaming HTTP request to the API.

        Args:
            method: HTTP method.
            path: API path (without base URL).
            json: JSON request body.

        Yields:
            Server-sent event data.

        Raises:
            SinasAPIError: If the request fails.
        """
        url = f"{self.base_url}{path}"
        headers = self._get_headers()

        try:
            with self._client.stream(
                method=method,
                url=url,
                json=json,
                headers=headers,
            ) as response:
                self._handle_response(response)
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        yield line[6:]
        except httpx.HTTPError as e:
            raise SinasAPIError(f"HTTP streaming request failed: {e}")

    def _handle_response(self, response: httpx.Response) -> None:
        """Handle HTTP response and raise appropriate exceptions.

        Args:
            response: HTTP response.

        Raises:
            SinasAuthError: If authentication fails.
            SinasNotFoundError: If resource is not found.
            SinasValidationError: If validation fails.
            SinasAPIError: For other API errors.
        """
        if response.is_success:
            return

        try:
            error_data = response.json()
        except Exception:
            error_data = {}

        message = error_data.get("detail", f"HTTP {response.status_code}")

        if response.status_code == 401:
            raise SinasAuthError(message, status_code=response.status_code, response=error_data)
        elif response.status_code == 404:
            raise SinasNotFoundError(message, status_code=response.status_code, response=error_data)
        elif response.status_code == 422:
            raise SinasValidationError(
                message, status_code=response.status_code, response=error_data
            )
        else:
            raise SinasAPIError(message, status_code=response.status_code, response=error_data)

    def set_token(self, token: str) -> None:
        """Set the authentication token.

        Args:
            token: JWT token.
        """
        self._token = token

    def set_api_key(self, api_key: str) -> None:
        """Set the API key.

        Args:
            api_key: API key.
        """
        self._api_key = api_key
