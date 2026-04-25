"""Tests for the main ImentivClient class."""

import pytest
from unittest.mock import patch

from imentiv import ImentivClient


def test_client_initialization_with_api_key(mock_api_key):
    """Test client initialization with API key."""
    client = ImentivClient(api_key=mock_api_key)
    assert client.config.api_key == mock_api_key
    assert client.video is not None
    assert client.emotion is not None
    assert client.face is not None
    client.close()


def test_client_initialization_with_env_var(mock_api_key, monkeypatch):
    """Test client initialization using environment variable."""
    monkeypatch.setenv("IMENTIV_API_KEY", mock_api_key)
    client = ImentivClient()
    assert client.config.api_key == mock_api_key
    client.close()


def test_client_initialization_without_api_key(monkeypatch):
    """Test that client raises error without API key."""
    monkeypatch.delenv("IMENTIV_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key is required"):
        ImentivClient()


def test_client_custom_configuration(mock_api_key):
    """Test client with custom configuration."""
    client = ImentivClient(
        api_key=mock_api_key,
        base_url="https://custom.api.url",
        timeout=60,
        max_retries=5,
    )
    assert client.config.base_url == "https://custom.api.url"
    assert client.config.timeout == 60
    assert client.config.max_retries == 5
    client.close()


def test_client_context_manager(mock_api_key):
    """Test client as context manager."""
    with ImentivClient(api_key=mock_api_key) as client:
        assert client.config.api_key == mock_api_key
    # Session should be closed after exiting context


def test_client_close(mock_api_key):
    """Test client close method."""
    client = ImentivClient(api_key=mock_api_key)
    client.close()


def test_client_repr_masks_api_key(mock_api_key):
    """Test that __repr__ masks the API key."""
    client = ImentivClient(api_key=mock_api_key)
    repr_str = repr(client)

    # API key should be masked in the representation
    assert mock_api_key not in repr_str
    assert "ImentivClient" in repr_str
    assert "Config" in repr_str
    client.close()


def test_get_account_info(mock_api_key):
    """Test get_account_info method."""
    client = ImentivClient(api_key=mock_api_key)
    mock_response = {"credits_remaining": 1000}
    
    with patch.object(client._base_client, "get", return_value=mock_response) as mock_get:
        result = client.get_account_info()
    
    mock_get.assert_called_once_with("/account")
    assert result == mock_response
    client.close()


def test_get_api_version(mock_api_key):
    """Test get_api_version method."""
    client = ImentivClient(api_key=mock_api_key)
    mock_response = {"version": "1.0.0"}
    
    with patch.object(client._base_client, "get", return_value=mock_response) as mock_get:
        result = client.get_api_version()
    
    mock_get.assert_called_once_with("/version")
    assert result == mock_response
    client.close()

