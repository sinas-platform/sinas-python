"""SINAS SDK client."""

import os
from typing import Any, Dict, Iterable, Iterator, List, NamedTuple, Optional

import httpx

from sinas.agents import AgentsAPI
from sinas.auth import AuthAPI
from sinas.batches import BatchesAPI
from sinas.chats import ChatsAPI
from sinas.executions import ExecutionsAPI
from sinas.exceptions import SinasAPIError, SinasAuthError, SinasNotFoundError, SinasValidationError
from sinas.files import FilesAPI
from sinas.functions import FunctionsAPI
from sinas.state import StateAPI
from sinas.templates import TemplatesAPI
from sinas.webhooks import WebhooksAPI


class ServerSentEvent(NamedTuple):
    """One event of an SSE stream, before its data is decoded."""

    event: str
    data: str
    id: Optional[str]


def iter_sse(lines: Iterable[str]) -> Iterator[ServerSentEvent]:
    """Parse the lines of a text/event-stream body into events.

    Follows the SSE format: ``field: value`` lines, events separated by a
    blank line, multi-line ``data`` joined with newlines, ``:`` comments
    (keep-alive pings) skipped, and the event name defaulting to
    ``"message"``. An event cut off by the end of the stream is still
    yielded.
    """
    event: Optional[str] = None
    data: List[str] = []
    event_id: Optional[str] = None
    for line in lines:
        line = line.rstrip("\r\n")
        if not line:
            if data:
                yield ServerSentEvent(event or "message", "\n".join(data), event_id)
            event, data, event_id = None, [], None
            continue
        if line.startswith(":"):
            continue
        name, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if name == "data":
            data.append(value)
        elif name == "event":
            event = value
        elif name == "id":
            event_id = value
    if data:
        yield ServerSentEvent(event or "message", "\n".join(data), event_id)


class SinasClient:
    """SINAS Runtime API client."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 30.0,
        use_env: bool = True,
    ) -> None:
        """Initialize SINAS Runtime client.

        Args:
            base_url: Base URL for SINAS API. Defaults to SINAS_BASE_URL env var.
            api_key: API key for authentication. Defaults to SINAS_API_KEY env var
                (unless use_env=False).
            token: JWT token for authentication. Defaults to SINAS_TOKEN env var
                (unless use_env=False).
            timeout: Request timeout in seconds.
            use_env: Whether missing credentials may fall back to the
                SINAS_API_KEY / SINAS_TOKEN environment variables. Pass False to
                build a client that is guaranteed to carry NO ambient
                credentials.

                This matters for server-side consumers. A process that sets
                SINAS_API_KEY for its own background work would otherwise have
                every request-scoped client built without a token silently
                inherit that service key — so a caller who presented no
                credentials gets answered as the service account. Any client
                representing an end user (or no user at all) should be built
                with use_env=False.
        """
        self.base_url = (base_url or os.getenv("SINAS_BASE_URL", "")).rstrip("/")
        if not self.base_url:
            raise ValueError(
                "base_url must be provided or SINAS_BASE_URL environment variable must be set"
            )

        self._api_key = api_key or (os.getenv("SINAS_API_KEY") if use_env else None)
        self._token = token or (os.getenv("SINAS_TOKEN") if use_env else None)
        self._timeout = timeout

        self._client = httpx.Client(timeout=timeout)

        # Initialize Runtime API modules
        self.auth = AuthAPI(self)
        self.state = StateAPI(self)
        self.chats = ChatsAPI(self)
        self.webhooks = WebhooksAPI(self)
        self.executions = ExecutionsAPI(self)
        self.functions = FunctionsAPI(self)
        self.agents = AgentsAPI(self)
        self.batches = BatchesAPI(self)
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
        response = self._request_response(method, path, json=json, params=params)
        if response.status_code == 204:
            return None
        return response.json()

    def _request_response(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Like _request, but return the response itself (for its headers).

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
        except httpx.HTTPError as e:
            raise SinasAPIError(f"HTTP request failed: {e}")
        self._handle_response(response)
        return response

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

    def _stream_sse(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ServerSentEvent]:
        """Make a streaming request and yield its server-sent events, event
        names included (``_stream`` yields only the data lines).

        Raises:
            SinasAPIError: If the request fails.
        """
        url = f"{self.base_url}{path}"
        headers = self._get_headers()
        headers["Accept"] = "text/event-stream"

        try:
            with self._client.stream(
                method=method,
                url=url,
                json=json,
                params=params,
                headers=headers,
            ) as response:
                if not response.is_success:
                    response.read()  # so the error's detail can be decoded
                self._handle_response(response)
                yield from iter_sse(response.iter_lines())
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
