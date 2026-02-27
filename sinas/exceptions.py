"""SINAS SDK exceptions."""

from typing import Any, Dict, Optional


class SinasError(Exception):
    """Base exception for SINAS SDK."""

    pass


class SinasAPIError(SinasError):
    """Exception raised for API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class SinasAuthError(SinasAPIError):
    """Exception raised for authentication errors."""

    pass


class SinasNotFoundError(SinasAPIError):
    """Exception raised when a resource is not found."""

    pass


class SinasValidationError(SinasAPIError):
    """Exception raised for validation errors."""

    pass
