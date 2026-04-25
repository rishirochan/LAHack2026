"""Tests for configuration management."""

import pytest

from imentiv.config import Config


def test_config_with_api_key(mock_api_key):
    """Test configuration with API key."""
    config = Config(api_key=mock_api_key)
    assert config.api_key == mock_api_key
    assert config.base_url == Config.DEFAULT_BASE_URL
    assert config.timeout == Config.DEFAULT_TIMEOUT
    assert config.max_retries == Config.DEFAULT_MAX_RETRIES


def test_config_with_env_var(mock_api_key, monkeypatch):
    """Test configuration using environment variable."""
    monkeypatch.setenv("IMENTIV_API_KEY", mock_api_key)
    config = Config()
    assert config.api_key == mock_api_key


def test_config_without_api_key(monkeypatch):
    """Test that config raises error without API key."""
    monkeypatch.delenv("IMENTIV_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key is required"):
        Config()


def test_config_custom_values(mock_api_key):
    """Test configuration with custom values."""
    config = Config(
        api_key=mock_api_key,
        base_url="https://custom.url",
        timeout=60,
        max_retries=5,
    )
    assert config.api_key == mock_api_key
    assert config.base_url == "https://custom.url"
    assert config.timeout == 60
    assert config.max_retries == 5


def test_config_get_headers(mock_api_key):
    """Test get_headers method."""
    config = Config(api_key=mock_api_key)
    headers = config.get_headers()

    assert "X-API-Key" in headers
    assert headers["X-API-Key"] == mock_api_key
    assert "Content-Type" not in headers
    assert "User-Agent" in headers


def test_config_repr_masks_api_key(mock_api_key):
    """Test that __repr__ masks the API key."""
    config = Config(api_key=mock_api_key)
    repr_str = repr(config)

    # API key should be masked
    assert mock_api_key not in repr_str
    assert "test...2345" in repr_str  # First 4 and last 4 chars
    assert "base_url=" in repr_str
    assert "timeout=" in repr_str
    assert "max_retries=" in repr_str


def test_config_repr_short_api_key():
    """Test that __repr__ handles short API keys."""
    config = Config(api_key="short")
    repr_str = repr(config)

    # Short keys should show ***
    assert "short" not in repr_str
    assert "***" in repr_str


def test_config_repr_eight_char_api_key():
    """Test that __repr__ masks 8-character API keys completely.

    This is an edge case: with the old logic (> 8), an 8-char key would
    show first 4 + last 4 = entire key. Now with >= 12, it shows ***.
    """
    config = Config(api_key="12345678")
    repr_str = repr(config)

    # 8-char key should be completely masked
    assert "12345678" not in repr_str
    assert "***" in repr_str


def test_config_repr_eleven_char_api_key():
    """Test that __repr__ masks 11-character API keys completely."""
    config = Config(api_key="12345678901")
    repr_str = repr(config)

    # 11-char key should be completely masked (< 12)
    assert "12345678901" not in repr_str
    assert "***" in repr_str


def test_config_repr_twelve_char_api_key():
    """Test that __repr__ shows partial masking for 12-character keys."""
    config = Config(api_key="123456789012")
    repr_str = repr(config)

    # 12-char key should show first 4 and last 4
    assert "1234...9012" in repr_str
    assert "123456789012" not in repr_str
