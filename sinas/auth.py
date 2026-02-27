"""Runtime Authentication API."""

from typing import TYPE_CHECKING, Any, Dict, List, Literal

if TYPE_CHECKING:
    from sinas.client import SinasClient


class AuthAPI:
    """Runtime Authentication API methods."""

    def __init__(self, client: "SinasClient") -> None:
        self._client = client

    def login(self, email: str) -> Dict[str, Any]:
        """Initiate login by sending OTP to email.

        Args:
            email: User's email address.

        Returns:
            Login response with message and session_id.
            Example: {"message": "OTP sent to your email", "session_id": "uuid-here"}
        """
        return self._client._request("POST", "/auth/login", json={"email": email})

    def verify_otp(self, session_id: str, otp_code: str) -> Dict[str, Any]:
        """Verify OTP and get access + refresh tokens.

        Args:
            session_id: Session ID from login() response.
            otp_code: One-time password code from email.

        Returns:
            Response with access token, refresh token, and user info.
            Example: {"access_token": "jwt-token", "refresh_token": "refresh-token",
                     "token_type": "bearer", "expires_in": 900, "user": {...}}
        """
        response = self._client._request(
            "POST", "/auth/verify-otp",
            json={"session_id": session_id, "otp_code": otp_code}
        )
        # Automatically set the token on the client
        if "access_token" in response:
            self._client.set_token(response["access_token"])
        return response

    def external_auth(self, token: str) -> Dict[str, Any]:
        """Exchange external OIDC token for SINAS JWT.

        Args:
            token: External OIDC token.

        Returns:
            Response with access token, refresh token, and user info.
        """
        response = self._client._request(
            "POST", "/auth/external-auth",
            json={"token": token}
        )
        if "access_token" in response:
            self._client.set_token(response["access_token"])
        return response

    def refresh(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token from login/verify response.

        Returns:
            Response with new access token.
            Example: {"access_token": "jwt-token", "token_type": "bearer", "expires_in": 900}
        """
        response = self._client._request(
            "POST", "/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        if "access_token" in response:
            self._client.set_token(response["access_token"])
        return response

    def logout(self, refresh_token: str) -> None:
        """Logout by revoking refresh token.

        Args:
            refresh_token: Refresh token to revoke.
        """
        self._client._request(
            "POST", "/auth/logout",
            json={"refresh_token": refresh_token}
        )

    def get_me(self) -> Dict[str, Any]:
        """Get current authenticated user info.

        Returns:
            User information.
        """
        return self._client._request("GET", "/auth/me")

    def check_permissions(
        self,
        permissions: List[str],
        logic: Literal["AND", "OR"] = "AND"
    ) -> Dict[str, Any]:
        """Check if the current user has the specified permissions.

        Args:
            permissions: List of permission strings to check.
            logic: Logic operator - "AND" requires all permissions, "OR" requires at least one.

        Returns:
            Permission check response with:
            - result: Boolean indicating if check passed
            - logic: The logic type used ("AND" or "OR")
            - checks: Array of individual permission results

        Example:
            >>> response = client.auth.check_permissions(
            ...     ["sinas.functions.read:all", "sinas.functions.create:own"],
            ...     logic="OR"
            ... )
            >>> response["result"]  # True if user has at least one permission
        """
        return self._client._request(
            "POST",
            "/auth/check-permissions",
            json={"permissions": permissions, "logic": logic}
        )
