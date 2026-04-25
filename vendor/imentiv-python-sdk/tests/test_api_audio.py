"""Tests for the Audio API client."""

import pytest
from unittest.mock import patch, mock_open

from imentiv.api.audio import AudioAPI
from imentiv.base_client import BaseClient
from imentiv.config import Config


@pytest.fixture
def mock_base_client(mock_api_key):
    """Create a mock base client."""
    config = Config(api_key=mock_api_key)
    client = BaseClient(config)
    return client


@pytest.fixture
def audio_api(mock_base_client):
    """Create a AudioAPI instance with mocked client."""
    return AudioAPI(mock_base_client)


class TestAudioAPI:
    """Tests for AudioAPI class."""

    def test_upload_calls_post_with_file(self, audio_api):
        """Test that upload opens file and calls post."""
        mock_response = {"audio_id": "audio_123", "status": "processing"}
        
        with patch.object(audio_api.client, "post", return_value=mock_response) as mock_post:
            with patch("builtins.open", mock_open(read_data=b"fake audio data")):
                result = audio_api.upload("/path/to/audio.mp3")

        # Verify correct v2 endpoint and parameters
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "v2/audios"
        assert "files" in kwargs
        assert "audio_file" in kwargs["files"]
        assert result == mock_response

    def test_get_results(self, audio_api):
        """Test getting audio results."""
        mock_response = {"status": "completed", "emotions": []}
        audio_id = "audio_123"

        with patch.object(audio_api.client, "get", return_value=mock_response) as mock_get:
            result = audio_api.get_results(audio_id)

        mock_get.assert_called_once_with(f"v2/audios/{audio_id}/multimodal-analytics")
        assert result == mock_response

    def test_get_results_wait(self, audio_api):
        """Test waiting for results."""
        mock_processing = {"status": "processing"}
        mock_completed = {"status": "completed", "data": {}}
        audio_id = "audio_123"

        with patch.object(audio_api.client, "get") as mock_get:
            mock_get.side_effect = [mock_processing, mock_completed]
            
            with patch("time.sleep"):  # Skip waiting
                result = audio_api.get_results(audio_id, wait=True)

        assert mock_get.call_count == 2
        assert result == mock_completed

    def test_list_audios(self, audio_api):
        """Test listing audios."""
        mock_response = {"audios": [], "total": 0}

        with patch.object(audio_api.client, "get", return_value=mock_response) as mock_get:
            result = audio_api.list(page_size=20)

        mock_get.assert_called_once_with("v2/audios", params={"page_size": 20, "direction": "forward"})
        assert result == mock_response

    def test_upload_backward_compatibility(self, audio_api):
        """Test that upload handles response with 'id' instead of 'audio_id'."""
        mock_response = {"id": "audio_123", "status": "processing"}
        
        with patch.object(audio_api.client, "post", return_value=mock_response) as mock_post:
            with patch("builtins.open", mock_open(read_data=b"fake audio data")):
                result = audio_api.upload("/path/to/audio.mp3")

        assert result["audio_id"] == "audio_123"
        assert result["id"] == "audio_123"

    def test_get_results_wait_not_found(self, audio_api):
        """Test waiting for results when resource is initially not found."""
        from imentiv.exceptions import ImentivNotFoundError
        
        mock_completed = {"status": "completed", "data": {}}
        
        with patch.object(audio_api.client, "get") as mock_get:
            # First call raises NotFound, second returns completed
            mock_get.side_effect = [
                ImentivNotFoundError("Not found"),
                mock_completed
            ]
            
            with patch("time.sleep"):  # Skip waiting
                result = audio_api.get_results("audio_123", wait=True)

        assert mock_get.call_count == 2
        assert result == mock_completed

    def test_get_results_wait_server_error(self, audio_api):
        """Test waiting for results when server errors initially."""
        from imentiv.exceptions import ImentivServerError
        
        mock_completed = {"status": "completed", "data": {}}
        
        with patch.object(audio_api.client, "get") as mock_get:
            # First call raises ServerError, second returns completed
            mock_get.side_effect = [
                ImentivServerError("Server error"),
                mock_completed
            ]
            
            with patch("time.sleep"):  # Skip waiting
                result = audio_api.get_results("audio_123", wait=True)

        assert mock_get.call_count == 2
        assert result == mock_completed

    def test_get_results_raise_not_found(self, audio_api):
        """Test that get_results raises ImentivNotFoundError when wait=False."""
        from imentiv.exceptions import ImentivNotFoundError
        
        with patch.object(audio_api.client, "get", side_effect=ImentivNotFoundError("Not found")):
            with pytest.raises(ImentivNotFoundError):
                audio_api.get_results("audio_123", wait=False)

    def test_get_results_raise_server_error(self, audio_api):
        """Test that get_results raises ImentivServerError when wait=False."""
        from imentiv.exceptions import ImentivServerError
        
        with patch.object(audio_api.client, "get", side_effect=ImentivServerError("Server error")):
            with pytest.raises(ImentivServerError):
                audio_api.get_results("audio_123", wait=False)

    def test_list_audios_with_offset(self, audio_api):
        """Test listing audios with offset."""
        mock_response = {"audios": [], "total": 0}

        with patch.object(audio_api.client, "get", return_value=mock_response) as mock_get:
            result = audio_api.list(page_size=20, offset_audio_id="audio_prev")

        mock_get.assert_called_once_with(
            "v2/audios", 
            params={"page_size": 20, "direction": "forward", "offset_audio_id": "audio_prev"}
        )
        assert result == mock_response
