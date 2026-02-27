"""FastAPI routers for SINAS Runtime API endpoints.

This module provides ready-to-mount FastAPI routers that proxy requests to SINAS Runtime API.
Each router handles authentication automatically and forwards requests to the backend.
"""

import asyncio
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Depends, HTTPException, Request
    from fastapi.responses import JSONResponse, StreamingResponse
    from fastapi.routing import APIRoute
    from pydantic import BaseModel, EmailStr
except ImportError:
    raise ImportError(
        "FastAPI integration requires fastapi. "
        "Install with: pip install 'sinas[fastapi]'"
    )

from sinas import SinasClient
from sinas.exceptions import SinasAPIError
from sinas.integrations.fastapi import SinasAuth


class SinasProxyRoute(APIRoute):
    """Route class that forwards SINAS API errors with their original status code."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original(request)
            except SinasAPIError as e:
                detail = e.response.get("detail", str(e)) if e.response else str(e)
                return JSONResponse(
                    status_code=e.status_code or 500,
                    content={"detail": detail},
                )

        return handler


class TemplateRenderRequest(BaseModel):
    """Request to render a template."""

    variables: Dict[str, Any]


class TemplateEmailRequest(BaseModel):
    """Request to send email with template."""

    to: EmailStr
    from_alias: Optional[str] = None
    from_name: Optional[str] = None
    variables: Dict[str, Any]


class FileUploadRequest(BaseModel):
    """Request to upload a file."""

    name: str
    content_base64: str
    content_type: str
    visibility: str = "private"
    file_metadata: Optional[Dict[str, Any]] = None


class FileSearchRequestModel(BaseModel):
    """Request to search files."""

    query: Optional[str] = None
    metadata_filter: Optional[Dict[str, Any]] = None
    limit: int = 100


class FileMetadataUpdateRequest(BaseModel):
    """Request to update file metadata."""

    file_metadata: Dict[str, Any]


def create_state_router(base_url: str, prefix: str = "") -> APIRouter:
    """Create a FastAPI router for state management endpoints.

    Args:
        base_url: SINAS API base URL.
        prefix: Optional prefix for routes (e.g., "/states").

    Returns:
        FastAPI router with state endpoints.

    Example:
        ```python
        app.include_router(create_state_router("http://localhost:51245"), prefix="/runtime/states")
        ```
    """
    router = APIRouter(tags=["states"], route_class=SinasProxyRoute)
    auth = SinasAuth(base_url=base_url)

    @router.post(prefix or "")
    async def create_state(
        request: Request,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Create a new state entry."""
        body = await request.json()
        return await asyncio.to_thread(client.state.set, **body)

    @router.get(prefix or "")
    async def list_states(
        namespace: Optional[str] = None,
        visibility: Optional[str] = None,
        assistant_id: Optional[str] = None,
        tags: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        client: SinasClient = Depends(auth)
    ) -> List[Dict[str, Any]]:
        """List state entries."""
        return await asyncio.to_thread(
            client.state.list,
            namespace=namespace,
            visibility=visibility,
            assistant_id=assistant_id,
            tags=tags,
            search=search,
            skip=skip,
            limit=limit
        )

    @router.get(f"{prefix}/{{state_id}}")
    async def get_state(
        state_id: str,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Get a specific state entry."""
        return await asyncio.to_thread(client.state.get, state_id)

    @router.put(f"{prefix}/{{state_id}}")
    async def update_state(
        state_id: str,
        request: Request,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Update a state entry."""
        body = await request.json()
        return await asyncio.to_thread(client.state.update, state_id, **body)

    @router.delete(f"{prefix}/{{state_id}}")
    async def delete_state(
        state_id: str,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Delete a state entry."""
        return await asyncio.to_thread(client.state.delete, state_id)

    return router


def create_chat_router(base_url: str, prefix: str = "") -> APIRouter:
    """Create a FastAPI router for chat endpoints.

    Args:
        base_url: SINAS API base URL.
        prefix: Optional prefix for routes (e.g., "/chats").

    Returns:
        FastAPI router with chat endpoints.

    Example:
        ```python
        app.include_router(create_chat_router("http://localhost:51245"), prefix="/runtime/chats")
        ```
    """
    router = APIRouter(tags=["chats"], route_class=SinasProxyRoute)
    auth = SinasAuth(base_url=base_url)

    @router.post("/agents/{namespace}/{agent_name}/chats")
    async def create_chat(
        namespace: str,
        agent_name: str,
        request: Request,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Create a new chat with an agent."""
        body = await request.json()
        return await asyncio.to_thread(client.chats.create, namespace, agent_name, **body)

    @router.post(f"{prefix}/{{chat_id}}/messages")
    async def send_message(
        chat_id: str,
        request: Request,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Send a message to a chat."""
        body = await request.json()
        return await asyncio.to_thread(client.chats.send, chat_id, body["content"])

    @router.post(f"{prefix}/{{chat_id}}/messages/stream")
    async def stream_message(
        chat_id: str,
        request: Request,
        client: SinasClient = Depends(auth)
    ):
        """Stream a message to a chat."""
        body = await request.json()

        async def event_generator():
            # Run the sync iterator in a thread to avoid blocking
            stream_iter = await asyncio.to_thread(
                lambda: list(client.chats.stream(chat_id, body["content"]))
            )
            for chunk in stream_iter:
                yield f"data: {chunk}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @router.get(prefix or "")
    async def list_chats(
        client: SinasClient = Depends(auth)
    ) -> List[Dict[str, Any]]:
        """List all chats for the current user."""
        return await asyncio.to_thread(client.chats.list)

    @router.get(f"{prefix}/{{chat_id}}")
    async def get_chat(
        chat_id: str,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Get a chat with all messages."""
        return await asyncio.to_thread(client.chats.get, chat_id)

    @router.put(f"{prefix}/{{chat_id}}")
    async def update_chat(
        chat_id: str,
        request: Request,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Update a chat."""
        body = await request.json()
        return await asyncio.to_thread(client.chats.update, chat_id, **body)

    @router.delete(f"{prefix}/{{chat_id}}")
    async def delete_chat(
        chat_id: str,
        client: SinasClient = Depends(auth)
    ) -> None:
        """Delete a chat."""
        await asyncio.to_thread(client.chats.delete, chat_id)
        return None

    return router


def create_webhook_router(base_url: str, prefix: str = "") -> APIRouter:
    """Create a FastAPI router for webhook execution endpoints.

    Args:
        base_url: SINAS API base URL.
        prefix: Optional prefix for routes (e.g., "/webhooks").

    Returns:
        FastAPI router with webhook endpoints.

    Example:
        ```python
        app.include_router(create_webhook_router("http://localhost:51245"), prefix="/runtime/webhooks")
        ```
    """
    router = APIRouter(tags=["webhooks"], route_class=SinasProxyRoute)
    auth = SinasAuth(base_url=base_url)

    @router.api_route(
        f"{prefix}/{{path:path}}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
    )
    async def execute_webhook(
        path: str,
        request: Request,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Execute a webhook."""
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.json() if request.headers.get("content-type") == "application/json" else None

        return await asyncio.to_thread(
            client.webhooks.run,
            path=path,
            method=request.method,
            body=body,
            query=dict(request.query_params)
        )

    return router


def create_executions_router(base_url: str, prefix: str = "") -> APIRouter:
    """Create a FastAPI router for execution endpoints.

    Args:
        base_url: SINAS API base URL.
        prefix: Optional prefix for routes (e.g., "/executions").

    Returns:
        FastAPI router with execution endpoints.

    Example:
        ```python
        app.include_router(create_executions_router("http://localhost:51245"), prefix="/runtime/executions")
        ```
    """
    router = APIRouter(tags=["executions"], route_class=SinasProxyRoute)
    auth = SinasAuth(base_url=base_url)

    @router.get(prefix or "")
    async def list_executions(
        function_name: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        client: SinasClient = Depends(auth)
    ) -> List[Dict[str, Any]]:
        """List executions."""
        return await asyncio.to_thread(
            client.executions.list,
            function_name=function_name,
            status=status,
            skip=skip,
            limit=limit
        )

    @router.get(f"{prefix}/{{execution_id}}")
    async def get_execution(
        execution_id: str,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Get execution details."""
        return await asyncio.to_thread(client.executions.get, execution_id)

    @router.get(f"{prefix}/{{execution_id}}/steps")
    async def get_execution_steps(
        execution_id: str,
        client: SinasClient = Depends(auth)
    ) -> List[Dict[str, Any]]:
        """Get execution steps."""
        return await asyncio.to_thread(client.executions.get_steps, execution_id)

    @router.post(f"{prefix}/{{execution_id}}/continue")
    async def continue_execution(
        execution_id: str,
        request: Request,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Continue a paused execution."""
        body = await request.json()
        return await asyncio.to_thread(
            client.executions.continue_execution, execution_id, body["input"]
        )

    return router


def create_templates_router(base_url: str, prefix: str = "") -> APIRouter:
    """Create a FastAPI router for templates endpoints.

    Args:
        base_url: SINAS API base URL.
        prefix: Optional prefix for routes (e.g., "/templates").

    Returns:
        FastAPI router with templates endpoints.

    Example:
        ```python
        app.include_router(create_templates_router("http://localhost:51245"), prefix="/runtime/templates")
        ```
    """
    router = APIRouter(tags=["templates"], route_class=SinasProxyRoute)
    auth = SinasAuth(base_url=base_url)

    @router.post(f"{prefix}/{{namespace}}/{{name}}/render")
    async def render_template(
        namespace: str,
        name: str,
        render_request: TemplateRenderRequest,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Render a template with given variables."""
        return await asyncio.to_thread(
            client.templates.render, namespace, name, render_request.variables
        )

    @router.post(f"{prefix}/{{namespace}}/{{name}}/email")
    async def send_email_with_template(
        namespace: str,
        name: str,
        email_request: TemplateEmailRequest,
        client: SinasClient = Depends(auth)
    ) -> Dict[str, Any]:
        """Send an email using a template."""
        return await asyncio.to_thread(
            client.templates.send_email,
            namespace,
            name,
            email_request.to,
            email_request.variables,
            email_request.from_alias,
            email_request.from_name
        )

    return router


def create_files_router(base_url: str, prefix: str = "") -> APIRouter:
    """Create a FastAPI router for file management endpoints.

    Args:
        base_url: SINAS API base URL.
        prefix: Optional prefix for routes (e.g., "/files").

    Returns:
        FastAPI router with file endpoints.

    Example:
        ```python
        app.include_router(create_files_router("http://localhost:51245"), prefix="/runtime/files")
        ```
    """
    router = APIRouter(tags=["files"], route_class=SinasProxyRoute)
    auth = SinasAuth(base_url=base_url)

    @router.get(f"{prefix}/serve/{{token}}")
    async def serve_file(token: str) -> Any:
        """Serve a file by token (unauthenticated)."""
        from fastapi.responses import Response

        client = SinasClient(base_url=base_url)
        try:
            result = await asyncio.to_thread(client.files.serve, token)
            return Response(
                content=result["content"],
                media_type=result["content_type"],
                headers={"Content-Disposition": f'inline; filename="{result["filename"]}"'}
                if result["filename"] else {},
            )
        finally:
            client.close()

    @router.post(f"{prefix}/{{namespace}}/{{collection}}")
    async def upload_file(
        namespace: str,
        collection: str,
        upload_request: FileUploadRequest,
        client: SinasClient = Depends(auth),
    ) -> Dict[str, Any]:
        """Upload a file."""
        kwargs: Dict[str, Any] = {
            "namespace": namespace,
            "collection": collection,
            "name": upload_request.name,
            "content_base64": upload_request.content_base64,
            "content_type": upload_request.content_type,
            "visibility": upload_request.visibility,
        }
        if upload_request.file_metadata is not None:
            kwargs["file_metadata"] = upload_request.file_metadata
        return await asyncio.to_thread(client.files.upload, **kwargs)

    @router.get(f"{prefix}/{{namespace}}/{{collection}}")
    async def list_files(
        namespace: str,
        collection: str,
        client: SinasClient = Depends(auth),
    ) -> List[Dict[str, Any]]:
        """List files in a collection."""
        return await asyncio.to_thread(client.files.list, namespace, collection)

    @router.post(f"{prefix}/{{namespace}}/{{collection}}/search")
    async def search_files(
        namespace: str,
        collection: str,
        search_request: FileSearchRequestModel,
        client: SinasClient = Depends(auth),
    ) -> List[Dict[str, Any]]:
        """Search files in a collection."""
        return await asyncio.to_thread(
            client.files.search,
            namespace=namespace,
            collection=collection,
            query=search_request.query,
            metadata_filter=search_request.metadata_filter,
            limit=search_request.limit,
        )

    @router.post(f"{prefix}/{{namespace}}/{{collection}}/{{filename}}/url")
    async def generate_temp_url(
        namespace: str,
        collection: str,
        filename: str,
        version: Optional[int] = None,
        expires_in: int = 3600,
        client: SinasClient = Depends(auth),
    ) -> Dict[str, Any]:
        """Generate a temporary public URL for a file."""
        return await asyncio.to_thread(
            client.files.generate_temp_url,
            namespace=namespace,
            collection=collection,
            filename=filename,
            version=version,
            expires_in=expires_in,
        )

    @router.get(f"{prefix}/{{namespace}}/{{collection}}/{{filename}}")
    async def download_file(
        namespace: str,
        collection: str,
        filename: str,
        version: Optional[int] = None,
        client: SinasClient = Depends(auth),
    ) -> Dict[str, Any]:
        """Download a file."""
        return await asyncio.to_thread(
            client.files.download,
            namespace=namespace,
            collection=collection,
            filename=filename,
            version=version,
        )

    @router.patch(f"{prefix}/{{namespace}}/{{collection}}/{{filename}}")
    async def update_file_metadata(
        namespace: str,
        collection: str,
        filename: str,
        update_request: FileMetadataUpdateRequest,
        client: SinasClient = Depends(auth),
    ) -> Dict[str, Any]:
        """Update file metadata."""
        return await asyncio.to_thread(
            client.files.update_metadata,
            namespace=namespace,
            collection=collection,
            filename=filename,
            file_metadata=update_request.file_metadata,
        )

    @router.delete(f"{prefix}/{{namespace}}/{{collection}}/{{filename}}")
    async def delete_file(
        namespace: str,
        collection: str,
        filename: str,
        client: SinasClient = Depends(auth),
    ) -> None:
        """Delete a file."""
        await asyncio.to_thread(
            client.files.delete,
            namespace=namespace,
            collection=collection,
            filename=filename,
        )
        return None

    return router


def create_runtime_router(base_url: str, include_auth: bool = False) -> APIRouter:
    """Create a complete runtime router with all endpoints.

    Args:
        base_url: SINAS API base URL.
        include_auth: Whether to include auth endpoints (login, verify-otp, etc.).

    Returns:
        FastAPI router with all runtime endpoints.

    Example:
        ```python
        app.include_router(create_runtime_router("http://localhost:51245"), prefix="/runtime")
        ```
    """
    router = APIRouter()

    # Include individual routers
    router.include_router(create_state_router(base_url), prefix="/states")
    router.include_router(create_chat_router(base_url), prefix="/chats")
    router.include_router(create_webhook_router(base_url), prefix="/webhooks")
    router.include_router(create_executions_router(base_url), prefix="/executions")
    router.include_router(create_templates_router(base_url), prefix="/templates")
    router.include_router(create_files_router(base_url), prefix="/files")

    # Optionally include auth endpoints
    if include_auth:
        auth = SinasAuth(base_url=base_url)
        router.include_router(auth.router, prefix="/auth")

    return router
