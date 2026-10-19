"""SINAS Python SDK - AI Agent Platform Client."""

from sinas.chats import ChatPage
from sinas.client import SinasClient
from sinas.exceptions import (
    SinasError,
    SinasAPIError,
    SinasAuthError,
    SinasNotFoundError,
    SinasValidationError,
)

__version__ = "0.1.0"
__all__ = [
    "ChatPage",
    "SinasClient",
    "SinasError",
    "SinasAPIError",
    "SinasAuthError",
    "SinasNotFoundError",
    "SinasValidationError",
]
