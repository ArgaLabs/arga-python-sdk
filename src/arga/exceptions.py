from __future__ import annotations

from typing import Any


class ArgaError(Exception):
    """Base exception for the Arga SDK."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ArgaAPIError(ArgaError):
    """Raised when the Arga API returns a non-2xx response."""

    def __init__(
        self,
        status_code: int,
        message: str,
        response: Any = None,
    ) -> None:
        self.status_code = status_code
        self.response = response
        super().__init__(f"HTTP {status_code}: {message}")
