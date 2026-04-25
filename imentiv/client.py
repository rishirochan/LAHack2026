"""Small vendored Imentiv SDK wrapper used by the backend."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from imentiv.exceptions import (
    ImentivAPIError,
    ImentivAuthenticationError,
    ImentivNotFoundError,
    ImentivRateLimitError,
    ImentivServerError,
    ImentivUnprocessableEntityError,
    ImentivValidationError,
)

logger = logging.getLogger(__name__)


class ImentivClient:
    """Requests-based client compatible with the Imentiv Python SDK shape."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.getenv("IMENTIV_API_KEY", "")
        if not self.api_key:
            raise ValueError("IMENTIV_API_KEY environment variable is not set")

        self.base_url = base_url or "https://api.imentiv.ai/"
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-API-Key": self.api_key,
                "Referer": "https://api.imentiv.ai",
                "User-Agent": "lahacks26-imentiv-client/1.0",
            }
        )
        self.video = VideoAPI(self)

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)
        if files:
            request_headers.pop("Content-Type", None)

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=urljoin(self.base_url, endpoint.lstrip("/")),
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                    headers=request_headers,
                    timeout=self.timeout,
                )
                logger.debug("Imentiv %s %s -> %s", method, endpoint, response.status_code)
                if response.status_code in (200, 201, 202, 204):
                    if not response.content:
                        return {}
                    return response.json()
                self._raise_for_response(response)
            except (requests.Timeout, requests.ConnectionError) as error:
                last_error = error
                if attempt >= self.max_retries:
                    break
                time.sleep(2**attempt)

        raise ImentivAPIError(f"Imentiv request failed after retries: {last_error}") from last_error

    def get(self, endpoint: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request("GET", endpoint, params=params)

    def post(
        self,
        endpoint: str,
        *,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.request("POST", endpoint, data=data, files=files, headers=headers, params=params, json=json)

    def close(self) -> None:
        self.session.close()

    def _raise_for_response(self, response: requests.Response) -> None:
        error_data: dict[str, Any] | None = None
        try:
            error_data = response.json()
            message = _extract_error_message(error_data) or response.text
        except ValueError:
            message = response.text or f"HTTP {response.status_code}"

        if response.status_code in (401, 403):
            raise ImentivAuthenticationError(message, response.status_code, error_data)
        if response.status_code == 400:
            raise ImentivValidationError(message, response.status_code, error_data)
        if response.status_code == 404:
            raise ImentivNotFoundError(message, response.status_code, error_data)
        if response.status_code == 422:
            raise ImentivUnprocessableEntityError(message, response.status_code, error_data)
        if response.status_code == 429:
            raise ImentivRateLimitError(message, response.status_code, error_data)
        if response.status_code >= 500:
            raise ImentivServerError(message, response.status_code, error_data)
        raise ImentivAPIError(message, response.status_code, error_data)


class VideoAPI:
    """Imentiv video upload and multimodal analytics endpoints."""

    def __init__(self, client: ImentivClient) -> None:
        self.client = client

    def upload(
        self,
        file_path: str,
        *,
        title: str | None = None,
        description: str = "",
        user_consent_version: str | None = None,
    ) -> dict[str, Any]:
        consent_headers: dict[str, str] = {}
        form_data = {
            "title": title or Path(file_path).name,
            "description": description,
        }
        if user_consent_version:
            form_data["user_consent_version"] = user_consent_version
            form_data["consent_version"] = user_consent_version
            consent_headers = {
                "X-User-Consent-Version": user_consent_version,
                "X-Consent-Version": user_consent_version,
            }

        with Path(file_path).open("rb") as file_handle:
            response = self.client.post(
                "v2/videos",
                files={"video_file": (Path(file_path).name, file_handle)},
                data=form_data,
                headers=consent_headers,
            )
        if "id" in response and "video_id" not in response:
            response["video_id"] = response["id"]
        return response

    def get_results(self, video_id: str, *, wait: bool = False, poll_interval: float = 2.0) -> dict[str, Any]:
        while True:
            try:
                response = self.client.get(f"v2/videos/{video_id}/multimodal-analytics")
                status = str(response.get("status") or "").lower()
                logger.debug("Imentiv video %s response keys=%s status=%s", video_id, sorted(response.keys()), status)
            except (ImentivNotFoundError, ImentivServerError) as error:
                if not wait:
                    raise
                logger.debug("Imentiv video %s still processing after transient %s", video_id, type(error).__name__)
                response = {"id": video_id, "status": "processing"}
                status = "processing"
            except ImentivUnprocessableEntityError as error:
                if not wait or "'annotated_video_mp4' field required" not in error.message:
                    raise
                logger.debug("Imentiv video %s awaiting annotated_video_mp4", video_id)
                response = {"id": video_id, "status": "processing"}
                status = "processing"

            if not wait or status in {"completed", "failed"}:
                return response
            time.sleep(poll_interval)


def _extract_error_message(error_data: dict[str, Any]) -> str | None:
    error = error_data.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if message:
            return str(message)
    for key in ("message", "detail"):
        if error_data.get(key):
            return str(error_data[key])
    return None
