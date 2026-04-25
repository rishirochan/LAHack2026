"""Tests for exception classes."""

from imentiv.exceptions import (
    ImentivAPIError,
    ImentivAuthenticationError,
    ImentivError,
    ImentivNotFoundError,
    ImentivRateLimitError,
    ImentivServerError,
    ImentivValidationError,
)

# Also test imports from main package
import imentiv


def test_imentiv_error():
    """Test base ImentivError."""
    error = ImentivError("Test error", status_code=400, response={"error": "test"})
    assert error.message == "Test error"
    assert error.status_code == 400
    assert error.response == {"error": "test"}
    assert str(error) == "Test error"


def test_imentiv_api_error():
    """Test ImentivAPIError."""
    error = ImentivAPIError("API error")
    assert isinstance(error, ImentivError)
    assert error.message == "API error"


def test_imentiv_authentication_error():
    """Test ImentivAuthenticationError."""
    error = ImentivAuthenticationError("Auth failed", status_code=401)
    assert isinstance(error, ImentivError)
    assert error.message == "Auth failed"
    assert error.status_code == 401


def test_imentiv_validation_error():
    """Test ImentivValidationError."""
    error = ImentivValidationError("Validation failed", status_code=400)
    assert isinstance(error, ImentivError)
    assert error.message == "Validation failed"


def test_imentiv_rate_limit_error():
    """Test ImentivRateLimitError."""
    error = ImentivRateLimitError("Rate limit exceeded", status_code=429)
    assert isinstance(error, ImentivError)
    assert error.status_code == 429


def test_imentiv_not_found_error():
    """Test ImentivNotFoundError."""
    error = ImentivNotFoundError("Resource not found", status_code=404)
    assert isinstance(error, ImentivError)
    assert error.status_code == 404


def test_imentiv_server_error():
    """Test ImentivServerError."""
    error = ImentivServerError("Server error", status_code=500)
    assert isinstance(error, ImentivError)
    assert error.status_code == 500


def test_exceptions_importable_from_main_package():
    """Test that all exceptions can be imported from the main imentiv package."""
    # Verify all exceptions are accessible from main package
    assert hasattr(imentiv, "ImentivError")
    assert hasattr(imentiv, "ImentivAPIError")
    assert hasattr(imentiv, "ImentivAuthenticationError")
    assert hasattr(imentiv, "ImentivValidationError")
    assert hasattr(imentiv, "ImentivRateLimitError")
    assert hasattr(imentiv, "ImentivNotFoundError")
    assert hasattr(imentiv, "ImentivServerError")

    # Verify they are the same classes
    assert imentiv.ImentivError is ImentivError
    assert imentiv.ImentivNotFoundError is ImentivNotFoundError
    assert imentiv.ImentivServerError is ImentivServerError


def test_version_importable_from_main_package():
    """Test that __version__ can be imported from the main imentiv package."""
    assert hasattr(imentiv, "__version__")
    assert isinstance(imentiv.__version__, str)
    assert imentiv.__version__ == "0.1.0"
