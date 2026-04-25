"""Exceptions raised by the vendored Imentiv client."""

from typing import Any


class ImentivError(Exception):
    """Base exception for Imentiv client failures."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(message)


class ImentivAPIError(ImentivError):
    """Raised when the Imentiv API returns an unexpected error."""


class ImentivAuthenticationError(ImentivAPIError):
    """Raised when the Imentiv API key is invalid or missing."""


class ImentivValidationError(ImentivAPIError):
    """Raised for invalid Imentiv request payloads."""


class ImentivUnprocessableEntityError(ImentivAPIError):
    """Raised when Imentiv returns HTTP 422."""


class ImentivNotFoundError(ImentivAPIError):
    """Raised when Imentiv has no resource for the requested id."""


class ImentivRateLimitError(ImentivAPIError):
    """Raised when the Imentiv API rate limit is exceeded."""


class ImentivServerError(ImentivAPIError):
    """Raised when the Imentiv API returns a server error."""
