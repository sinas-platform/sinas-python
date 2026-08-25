"""FastAPI integration for SINAS authentication and authorization.

This module provides zero-boilerplate SINAS auth for FastAPI applications.

Example:
    ```python
    from fastapi import FastAPI, Depends
    from sinas.integrations.fastapi import SinasAuth

    app = FastAPI()
    sinas = SinasAuth(base_url="http://localhost:51245")

    # Auto-authenticated endpoints
    @app.get("/chats")
    async def get_chats(client: SinasClient = Depends(sinas)):
        return client.chats.list()

    # Permission-protected endpoints
    @app.delete("/users/{user_id}")
    async def delete_user(
        user_id: str,
        client: SinasClient = Depends(sinas.require("sinas.users.delete:all"))
    ):
        return client.users.delete(user_id)

    # Include auto-generated auth routes
    app.include_router(sinas.router, prefix="/auth")
    ```
"""

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Dict, Literal, Optional

try:
    from fastapi import APIRouter, Depends, Header, HTTPException, status
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    from pydantic import BaseModel, EmailStr
except ImportError:
    raise ImportError(
        "FastAPI integration requires fastapi and pydantic. "
        "Install with: pip install 'sinas[fastapi]'"
    )

if TYPE_CHECKING:
    from sinas.client import SinasClient

from sinas import SinasAPIError, SinasAuthError, SinasClient


class LoginRequest(BaseModel):
    """Login request body. `password` is required for instances running in
    `password` or `password+otp` auth modes; ignored otherwise."""

    email: EmailStr
    password: Optional[str] = None


class VerifyOTPRequest(BaseModel):
    """OTP verification request body."""

    session_id: str
    otp_code: str


class RefreshRequest(BaseModel):
    """Token refresh request body."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout request body."""

    refresh_token: str


class SinasAuth:
    """FastAPI dependency for SINAS authentication and authorization.

    This class provides:
    - Automatic token extraction from Authorization header
    - Per-request SinasClient instantiation with user token
    - Permission checking decorators
    - Auto-generated auth endpoints (login, verify-otp, me)
    """

    def __init__(
        self,
        base_url: str,
        token_url: str = "/auth/token",
        auto_error: bool = True,
    ) -> None:
        """Initialize SINAS FastAPI auth.

        Args:
            base_url: Base URL for SINAS API.
            token_url: URL for token endpoint (for OpenAPI docs).
            auto_error: Whether to automatically raise HTTPException on auth errors.
        """
        self.base_url = base_url
        self.auto_error = auto_error
        self._security = HTTPBearer(auto_error=auto_error)

        # Create router with auto-generated auth endpoints
        self.router = self._create_auth_router()

    async def __call__(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    ) -> "SinasClient":
        """Extract token and return authenticated SinasClient.

        This is the main dependency - use it with Depends(sinas_auth).

        Args:
            credentials: HTTP Bearer credentials from Authorization header.

        Returns:
            Authenticated SinasClient instance.

        Raises:
            HTTPException: If authentication fails (when auto_error=True).
        """
        if not credentials:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # Return a genuinely unauthenticated client. use_env=False is
            # load-bearing: without it, a consumer that sets SINAS_API_KEY for
            # its own background work would have this "unauthenticated" client
            # pick up that service key, and an anonymous caller would be
            # answered as the service account (e.g. GET /me returning the
            # service identity, so a frontend renders a logged-in session for
            # a visitor who never authenticated).
            return SinasClient(base_url=self.base_url, use_env=False)

        token = credentials.credentials

        # Create client with user's token
        # use_env=False so a user-scoped client carries the caller's token and
        # nothing else — never the process's ambient service credentials.
        client = SinasClient(base_url=self.base_url, token=token, use_env=False)

        # Optionally validate token by fetching user info
        # This adds one extra request but ensures the token is valid
        try:
            await self._validate_token(client)
        except SinasAuthError:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return client

    async def _validate_token(self, client: "SinasClient") -> None:
        """Validate token by calling /auth/me endpoint.

        Args:
            client: SINAS client with token.

        Raises:
            SinasAuthError: If token is invalid.
        """
        # This will raise SinasAuthError if token is invalid
        await asyncio.to_thread(client.auth.get_me)

    def require(self, *permissions: str, logic: Literal["AND", "OR"] = "OR") -> Callable:
        """Create a dependency that requires specific permissions.

        Args:
            *permissions: One or more permission strings (e.g., "sinas.chats.read:own").
            logic: Logic operator - "OR" requires at least one permission (default),
                   "AND" requires all permissions.

        Returns:
            FastAPI dependency function that checks permissions.

        Example:
            ```python
            # OR logic (default) - user needs ANY permission
            @app.delete("/chats/{chat_id}")
            async def delete_chat(
                chat_id: str,
                client: SinasClient = Depends(sinas.require("sinas.chats.delete:own", "sinas.admin:all"))
            ):
                await asyncio.to_thread(client.chats.delete, chat_id)

            # AND logic - user needs ALL permissions
            @app.post("/admin/action")
            async def admin_action(
                client: SinasClient = Depends(
                    sinas.require("sinas.admin:all", "sinas.functions.write:all", logic="AND")
                )
            ):
                return {"message": "Admin action completed"}
            ```
        """

        async def permission_checker(
            client: "SinasClient" = Depends(self),
        ) -> "SinasClient":
            """Check if user has required permissions."""
            try:
                # Use the new check_permissions endpoint
                result = await asyncio.to_thread(
                    client.auth.check_permissions,
                    list(permissions),
                    logic
                )

                if not result.get("result", False):
                    operator = logic
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Missing required permission: {f' {operator} '.join(permissions)}",
                    )

                return client
            except SinasAuthError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

        return permission_checker

    def require_all(self, *permissions: str) -> Callable:
        """Create a dependency that requires ALL specified permissions (AND logic).

        This is a convenience method equivalent to require(..., logic="AND").

        Args:
            *permissions: One or more permission strings.

        Returns:
            FastAPI dependency function that checks permissions.

        Example:
            ```python
            @app.post("/admin/action")
            async def admin_action(
                client: SinasClient = Depends(sinas.require_all("sinas.admin:all", "sinas.functions.write:all"))
            ):
                return {"message": "Admin action completed"}
            ```
        """
        return self.require(*permissions, logic="AND")

    def _create_auth_router(self) -> APIRouter:
        """Create auto-generated authentication routes.

        Returns:
            FastAPI router with /login, /verify-otp, /refresh, and /me endpoints.
        """
        router = APIRouter(tags=["authentication"])

        # Unauthenticated client for login/verify — these are pre-auth routes,
        # so it must carry no ambient credentials either (see use_env above).
        base_client = SinasClient(base_url=self.base_url, use_env=False)

        @router.post("/login")
        async def login(request: LoginRequest) -> Dict[str, Any]:
            """Initiate login. Forwards `email` (and `password`, if supplied)
            to the upstream Sinas instance. The response shape varies by the
            instance's AUTH_MODE — see `AuthAPI.login` docstring."""
            try:
                return await asyncio.to_thread(
                    base_client.auth.login, request.email, request.password
                )
            except SinasAPIError as e:
                raise HTTPException(
                    status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e),
                )

        @router.post("/verify-otp")
        async def verify_otp(request: VerifyOTPRequest) -> Dict[str, Any]:
            """Verify OTP and return access token."""
            try:
                return await asyncio.to_thread(
                    base_client.auth.verify_otp, request.session_id, request.otp_code
                )
            except SinasAPIError as e:
                raise HTTPException(
                    status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e),
                )

        @router.post("/refresh")
        async def refresh_token(request: RefreshRequest) -> Dict[str, Any]:
            """Refresh access token using refresh token."""
            try:
                return await asyncio.to_thread(
                    base_client.auth.refresh, request.refresh_token
                )
            except SinasAPIError as e:
                raise HTTPException(
                    status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e),
                )

        @router.post("/logout")
        async def logout(request: LogoutRequest) -> Dict[str, Any]:
            """Logout by revoking refresh token."""
            try:
                await asyncio.to_thread(
                    base_client.auth.logout, request.refresh_token
                )
                return {"message": "Logged out successfully"}
            except SinasAPIError as e:
                raise HTTPException(
                    status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e),
                )

        @router.get("/me")
        async def get_current_user(client: "SinasClient" = Depends(self)) -> Dict[str, Any]:
            """Get current authenticated user info."""
            try:
                return await asyncio.to_thread(client.auth.get_me)
            except SinasAuthError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

        return router


# Convenience alias
SinasFastAPI = SinasAuth
