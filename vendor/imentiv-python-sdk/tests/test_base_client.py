"""Tests for the BaseClient class."""

import pytest
from unittest.mock import Mock, patch
import requests

from imentiv.base_client import BaseClient
from imentiv.config import Config
from imentiv.exceptions import (
    ImentivAPIError,
    ImentivAuthenticationError,
    ImentivNotFoundError,
    ImentivRateLimitError,
    ImentivServerError,
    ImentivValidationError,
)


@pytest.fixture
def base_client(mock_api_key):
    """Create a BaseClient instance."""
    config = Config(api_key=mock_api_key)
    return BaseClient(config)


class TestBaseClient:
    """Tests for BaseClient class."""

    def test_initialization(self, base_client, mock_api_key):
        """Test client initialization."""
        assert base_client.config.api_key == mock_api_key
        assert base_client.session is not None

    def test_headers_set_on_session(self, base_client, mock_api_key):
        """Test that headers are set on the session."""
        assert "X-API-Key" in base_client.session.headers
        assert base_client.session.headers["X-API-Key"] == mock_api_key

    def test_close(self, base_client):
        """Test closing the client."""
        base_client.close()
        # Session should still exist but be closed
        assert base_client.session is not None

    def test_context_manager(self, mock_api_key):
        """Test context manager usage."""
        config = Config(api_key=mock_api_key)
        with BaseClient(config) as client:
            assert client.session is not None


class TestErrorHandling:
    """Tests for error handling in BaseClient."""

    def test_authentication_error(self, base_client):
        """Test 401 raises ImentivAuthenticationError."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.json.return_value = {"error": {"message": "Invalid API key"}}

        with pytest.raises(ImentivAuthenticationError) as exc_info:
            base_client._handle_error_response(mock_response)

        assert exc_info.value.status_code == 401

    def test_validation_error(self, base_client):
        """Test 400 raises ImentivValidationError."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.json.return_value = {"error": {"message": "Invalid input"}}

        with pytest.raises(ImentivValidationError) as exc_info:
            base_client._handle_error_response(mock_response)

        assert exc_info.value.status_code == 400

    def test_not_found_error(self, base_client):
        """Test 404 raises ImentivNotFoundError."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.json.return_value = {"error": {"message": "Resource not found"}}

        with pytest.raises(ImentivNotFoundError) as exc_info:
            base_client._handle_error_response(mock_response)

        assert exc_info.value.status_code == 404

    def test_rate_limit_error(self, base_client):
        """Test 429 raises ImentivRateLimitError."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        mock_response.json.return_value = {"error": {"message": "Rate limit exceeded"}}

        with pytest.raises(ImentivRateLimitError) as exc_info:
            base_client._handle_error_response(mock_response)

        assert exc_info.value.status_code == 429

    def test_server_error(self, base_client):
        """Test 500 raises ImentivServerError."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json.return_value = {"error": {"message": "Server error"}}

        with pytest.raises(ImentivServerError) as exc_info:
            base_client._handle_error_response(mock_response)

        assert exc_info.value.status_code == 500

    def test_generic_api_error(self, base_client):
        """Test other status codes raise ImentivAPIError."""
        mock_response = Mock()
        mock_response.status_code = 418
        mock_response.text = "I'm a teapot"
        mock_response.json.return_value = {"error": {"message": "Teapot error"}}

        with pytest.raises(ImentivAPIError) as exc_info:
            base_client._handle_error_response(mock_response)

        assert exc_info.value.status_code == 418

    def test_handle_error_response_invalid_json(self, base_client):
        """Test handling of error response with invalid JSON."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request (Not JSON)"
        # Parsing JSON raises error
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with pytest.raises(ImentivValidationError) as exc_info:
            base_client._handle_error_response(mock_response)
        
        assert exc_info.value.message == "Bad Request (Not JSON)"

    def test_unprocessable_entity_error(self, base_client):
        """Test 422 raises ImentivUnprocessableEntityError."""
        from imentiv.exceptions import ImentivUnprocessableEntityError
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.text = "Unprocessable"
        mock_response.json.return_value = {"error": {"message": "Invalid entity"}}

        with pytest.raises(ImentivUnprocessableEntityError) as exc_info:
            base_client._handle_error_response(mock_response)

        assert exc_info.value.status_code == 422


class TestRetryLogic:
    """Tests for retry logic in BaseClient."""

    def test_retry_on_timeout(self, base_client):
        """Test that requests are retried on timeout."""
        with patch.object(base_client.session, "request") as mock_request:
            mock_request.side_effect = [
                requests.exceptions.Timeout("Connection timed out"),
                requests.exceptions.Timeout("Connection timed out"),
                Mock(status_code=200, content=b'{"success": true}', json=lambda: {"success": True}),
            ]

            with patch("time.sleep"):  # Skip actual sleep
                result = base_client.get("/test")

        assert result == {"success": True}
        assert mock_request.call_count == 3

    def test_max_retries_exceeded(self, base_client):
        """Test that ImentivAPIError is raised after max retries."""
        with patch.object(base_client.session, "request") as mock_request:
            mock_request.side_effect = requests.exceptions.Timeout("Connection timed out")

            with patch("time.sleep"):  # Skip actual sleep
                with pytest.raises(ImentivAPIError) as exc_info:
                    base_client.get("/test")

        assert "retries" in str(exc_info.value.message)


class TestSuccessfulResponses:
    """Tests for successful response handling."""

    def test_200_response(self, base_client):
        """Test handling of 200 response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"data": "test"}'
        mock_response.json.return_value = {"data": "test"}

        with patch.object(base_client.session, "request", return_value=mock_response):
            result = base_client.get("/test")

        assert result == {"data": "test"}

    def test_201_response(self, base_client):
        """Test handling of 201 response."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.content = b'{"created": true}'
        mock_response.json.return_value = {"created": True}

        with patch.object(base_client.session, "request", return_value=mock_response):
            result = base_client.post("/test", json={"data": "new"})

        assert result == {"created": True}

    def test_204_no_content_response(self, base_client):
        """Test handling of 204 No Content response."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.content = b""

        with patch.object(base_client.session, "request", return_value=mock_response):
            result = base_client.delete("/test/123")

        assert result == {}


class TestRequestExecution:
    """Tests for request execution details."""

    def test_request_with_files(self, base_client):
        """Test request with files handles headers correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"{}"
        mock_response.json.return_value = {}

        with patch.object(base_client.session, "request", return_value=mock_response) as mock_request:
            base_client.post("/upload", files={"file": ("test.txt", b"content")})
        
        args, kwargs = mock_request.call_args
        headers = kwargs["headers"]
        assert headers["Content-Type"] is None

    def test_request_exception(self, base_client):
        """Test generic RequestException raises ImentivAPIError."""
        with patch.object(base_client.session, "request", side_effect=requests.exceptions.RequestException("Generic error")):
            with pytest.raises(ImentivAPIError) as exc_info:
                base_client.get("/test")
        
        assert "Request failed: Generic error" in str(exc_info.value.message)

    def test_put_request(self, base_client):
        """Test PUT request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"{}"
        mock_response.json.return_value = {}

        with patch.object(base_client.session, "request", return_value=mock_response) as mock_request:
            base_client.put("/resource", json={"key": "value"})
        
        mock_request.assert_called_with(
            method="PUT",
            url=base_client.config.base_url + "resource",
            params=None,
            json={"key": "value"},
            data=None,
            files=None,
            timeout=30,
            headers=None
        )