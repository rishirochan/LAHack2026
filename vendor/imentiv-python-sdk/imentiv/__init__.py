"""
Imentiv Python SDK

A Python client library for interacting with the Imentiv AI API.
Provides emotion detection, video analysis, and face analysis capabilities.
"""

from imentiv._version import __version__
from imentiv.client import ImentivClient
from imentiv.exceptions import (
    ImentivAPIError,
    ImentivAuthenticationError,
    ImentivError,
    ImentivNotFoundError,
    ImentivRateLimitError,
    ImentivServerError,
    ImentivValidationError,
)
__all__ = [
    "__version__",
    "ImentivClient",
    "ImentivError",
    "ImentivAPIError",
    "ImentivAuthenticationError",
    "ImentivValidationError",
    "ImentivRateLimitError",
    "ImentivNotFoundError",
    "ImentivServerError",
]
