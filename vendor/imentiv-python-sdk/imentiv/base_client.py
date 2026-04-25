"""
Base HTTP client for making API requests.
"""

import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests

from imentiv.config import Config

logger = logging.getLogger(__name__)
from imentiv.exceptions import (
    ImentivAPIError,
    ImentivAuthenticationError,
    ImentivNotFoundError,
    ImentivRateLimitError,
    ImentivServerError,
    ImentivUnprocessableEntityError,
    ImentivValidationError,
)


class BaseClient:
    """Base HTTP client for making requests to the Imentiv API."""

    def __init__(self, config: Config):
        """
        Initialize the base client.

        Args:
            config: Configuration object containing API key and settings.
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(config.get_headers())

    def _handle_error_response(self, response: requests.Response) -> None:
        """
        Handle error responses from the API.

        Args:
            response: The HTTP response object.

        Raises:
            ImentivAuthenticationError: For 401 status codes.
            ImentivValidationError: For 400 status codes.
            ImentivNotFoundError: For 404 status codes.
            ImentivRateLimitError: For 429 status codes.
            ImentivServerError: For 500+ status codes.
            ImentivAPIError: For other error status codes.
        """
        status_code = response.status_code
        error_data = None

        try:
            error_data = response.json()
            message = error_data.get("error", {}).get("message", response.text)
        except Exception:
            message = response.text or f"HTTP {status_code} error"

        if status_code == 401:
            raise ImentivAuthenticationError(message, status_code, error_data)
        elif status_code == 400:
            raise ImentivValidationError(message, status_code, error_data)
        elif status_code == 404:
            raise ImentivNotFoundError(message, status_code, error_data)
        elif status_code == 422:
            raise ImentivUnprocessableEntityError(message, status_code, error_data)
        elif status_code == 429:
            raise ImentivRateLimitError(message, status_code, error_data)
        elif status_code >= 500:
            raise ImentivServerError(message, status_code, error_data)
        else:
            raise ImentivAPIError(message, status_code, error_data)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.).
            endpoint: API endpoint path.
            params: Query parameters.
            json: JSON request body.
            data: Form data.
            files: Files to upload.
            headers: Additional request headers.
            retry_count: Current retry attempt number.

        Returns:
            Parsed JSON response data.

        Raises:
            Various ImentivError subclasses depending on the error type.
        """
        # Remove leading slash so urljoin doesn't treat endpoint as absolute and replace the base path
        url = urljoin(self.config.base_url, endpoint.lstrip("/"))
        
        logger.debug(f"Request {method} {url}")
        if params:
            logger.debug(f"Params: {params}")
        if json:
            logger.debug(f"JSON body: {json}")
        if data:
            logger.debug(f"Data: {data}")

        try:
            # Remove Content-Type header if uploading files
            request_headers = self.session.headers.copy()
            if headers:
                request_headers.update(headers)
            if files:
                # Let requests generate the multipart boundary.
                request_headers.pop("Content-Type", None)

            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                data=data,
                files=files,
                timeout=self.config.timeout,
                headers=request_headers if files or headers else None,
            )

            logger.debug(f"Response {response.status_code}")

            # Handle successful responses (including 204 No Content for DELETE)
            if response.status_code in (200, 201, 202, 204):
                if response.content:
                    resp_json = response.json()
                    logger.debug(f"Response body: {resp_json}")
                    return resp_json
                return {}

            # Handle error responses
            self._handle_error_response(response)
            # If _handle_error_response returns without raising, raise a generic error
            raise ImentivAPIError(
                f"Unhandled error response: {response.status_code} {response.text}"
            )

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            # Retry on timeout or connection errors
            if retry_count < self.config.max_retries:
                time.sleep(2**retry_count)  # Exponential backoff
                return self._request(method, endpoint, params=params, json=json, data=data, files=files, headers=headers, retry_count=retry_count + 1)
            raise ImentivAPIError(
                f"Request failed after {self.config.max_retries} retries: {str(e)}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise ImentivAPIError(f"Request failed: {str(e)}") from e

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request."""
        return self._request("GET", endpoint, params=params)

    def post(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make a POST request."""
        return self._request("POST", endpoint, params=params, json=json, data=data, files=files, headers=headers)

    def put(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a PUT request."""
        return self._request("PUT", endpoint, json=json)

    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make a DELETE request."""
        return self._request("DELETE", endpoint)

    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
