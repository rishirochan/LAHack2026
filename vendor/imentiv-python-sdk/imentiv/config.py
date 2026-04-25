"""
Configuration management for the Imentiv SDK.
"""

import os
from typing import Optional

from imentiv._version import __version__


class Config:
    """Configuration class for Imentiv SDK."""

    DEFAULT_BASE_URL = "https://api.imentiv.ai/"
    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_RETRIES = 3

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        """
        Initialize configuration.

        Args:
            api_key: Imentiv API key. If not provided, will try to read from
                    IMENTIV_API_KEY environment variable.
            base_url: Base URL for the Imentiv API. Defaults to the official API URL.
            timeout: Request timeout in seconds. Defaults to 30.
            max_retries: Maximum number of retries for failed requests. Defaults to 3.

        Raises:
            ValueError: If API key is not provided and not found in environment.
        """
        self.api_key = api_key or os.environ.get("IMENTIV_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key is required. Provide it as an argument or set "
                "the IMENTIV_API_KEY environment variable."
            )

        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        self.max_retries = max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES

    def get_headers(self) -> dict:
        """
        Get default headers for API requests.

        Returns:
            Dictionary of headers including authorization.
        """
        return {
            "X-API-Key": self.api_key,
            "User-Agent": f"imentiv-python-sdk/{__version__}",
            "Referer": "https://api.imentiv.ai",
        }

    def __repr__(self) -> str:
        """Return a string representation with masked API key."""
        masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if len(self.api_key) >= 12 else "***"
        return (
            f"Config(api_key='{masked_key}', base_url='{self.base_url}', "
            f"timeout={self.timeout}, max_retries={self.max_retries})"
        )
