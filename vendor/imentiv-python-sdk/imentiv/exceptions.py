"""
Custom exception classes for the Imentiv SDK.
"""

from typing import Any, Dict, Optional


class ImentivError(Exception):
    """Base exception for all Imentiv SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class ImentivAPIError(ImentivError):
    """Raised when the API returns an error response."""

    pass


class ImentivAuthenticationError(ImentivError):
    """Raised when authentication fails."""

    pass


class ImentivValidationError(ImentivError):
    """Raised when request validation fails."""

    pass


class ImentivUnprocessableEntityError(ImentivError):
    """Raised when the request is unprocessable (e.g. semantic errors)."""

    pass


class ImentivRateLimitError(ImentivError):
    """Raised when rate limit is exceeded."""

    pass


class ImentivNotFoundError(ImentivError):
    """Raised when a resource is not found."""

    pass


class ImentivServerError(ImentivError):
    """Raised when the server encounters an error."""

    pass
