"""Tests for the Emotion API client."""

import pytest
from unittest.mock import patch, mock_open

from imentiv.api.emotion import EmotionAPI
from imentiv.base_client import BaseClient
from imentiv.config import Config


@pytest.fixture
def mock_base_client(mock_api_key):
    """Create a mock base client."""
    config = Config(api_key=mock_api_key)
    client = BaseClient(config)
    return client


@pytest.fixture
def emotion_api(mock_base_client):
    """Create an EmotionAPI instance with mocked client."""
    return EmotionAPI(mock_base_client)


class TestEmotionAPI:
    """Tests for EmotionAPI class."""

    def test_detect_from_image(self, emotion_api):
        """Test detecting emotions from an image upload."""
        mock_response = {"image_id": "img123", "status": "processing"}
        
        with patch.object(emotion_api.client, "post", return_value=mock_response) as mock_post:
            with patch("builtins.open", mock_open(read_data=b"fake image data")):
                result = emotion_api.detect_from_image("/path/to/image.jpg")

        assert result == mock_response
        # Verify call arguments
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "v1/images"
        assert "files" in kwargs
        assert kwargs["data"]["title"] == "image.jpg"
        assert kwargs["data"]["description"] == ""

    def test_get_image_analysis(self, emotion_api):
        """Test retrieving image analysis results."""
        mock_response = {"status": "completed", "faces": []}
        with patch.object(emotion_api.client, "get", return_value=mock_response) as mock_get:
            result = emotion_api.get_image_analysis("img123")
            
        mock_get.assert_called_once_with("v1/images/img123")
        assert result == mock_response

    def test_detect_from_text(self, emotion_api):
        """Test uploading text for emotion analysis."""
        mock_response = {"id": "txt123", "status": "processing"}

        with patch.object(emotion_api.client, "post", return_value=mock_response) as mock_post:
            result = emotion_api.detect_from_text("I am so happy today!")

        mock_post.assert_called_once_with(
            "v2/texts",
            data={"text": "I am so happy today!", "title": "Text Analysis"},
        )
        assert result == mock_response

    def test_get_text_analysis(self, emotion_api):
        """Test retrieving text analysis results."""
        mock_response = {"status": "completed", "emotions": {}}
        with patch.object(emotion_api.client, "get", return_value=mock_response) as mock_get:
            result = emotion_api.get_text_analysis("txt123")
            
        mock_get.assert_called_once_with("v1/texts/txt123")
        assert result == mock_response

    def test_analyze_video_emotions(self, emotion_api, mock_video_id):
        """Test analyzing emotions in a video."""
        mock_response = {"status": "completed"}

        with patch.object(emotion_api.client, "get", return_value=mock_response) as mock_get:
            result = emotion_api.analyze_video_emotions(mock_video_id)

        mock_get.assert_called_once_with(f"v2/videos/{mock_video_id}/multimodal-analytics")
        assert result == mock_response

    def test_get_emotion_categories(self, emotion_api):
        """Test getting available emotion categories."""
        # No API call mocked as it returns a static dictionary
        result = emotion_api.get_emotion_categories()
        assert "joy" in result["categories"]
        assert len(result["categories"]) > 0

    def test_get_image_analysis_wait_not_found(self, emotion_api):
        """Test waiting for image analysis when resource is initially not found."""
        from imentiv.exceptions import ImentivNotFoundError
        
        mock_completed = {"status": "completed", "data": {}}
        
        with patch.object(emotion_api.client, "get") as mock_get:
            mock_get.side_effect = [
                ImentivNotFoundError("Not found"),
                mock_completed
            ]
            
            with patch("time.sleep"):
                result = emotion_api.get_image_analysis("img123", wait=True)

        assert mock_get.call_count == 2
        assert result == mock_completed

    def test_get_image_analysis_wait_server_error(self, emotion_api):
        """Test waiting for image analysis when server errors initially."""
        from imentiv.exceptions import ImentivServerError
        
        mock_completed = {"status": "completed", "data": {}}
        
        with patch.object(emotion_api.client, "get") as mock_get:
            mock_get.side_effect = [
                ImentivServerError("Server error"),
                mock_completed
            ]
            
            with patch("time.sleep"):
                result = emotion_api.get_image_analysis("img123", wait=True)

        assert mock_get.call_count == 2
        assert result == mock_completed

    def test_get_image_analysis_raise_not_found(self, emotion_api):
        """Test that get_image_analysis raises ImentivNotFoundError when wait=False."""
        from imentiv.exceptions import ImentivNotFoundError
        
        with patch.object(emotion_api.client, "get", side_effect=ImentivNotFoundError("Not found")):
            with pytest.raises(ImentivNotFoundError):
                emotion_api.get_image_analysis("img123", wait=False)

    def test_get_image_analysis_raise_server_error(self, emotion_api):
        """Test that get_image_analysis raises ImentivServerError when wait=False."""
        from imentiv.exceptions import ImentivServerError
        
        with patch.object(emotion_api.client, "get", side_effect=ImentivServerError("Server error")):
            with pytest.raises(ImentivServerError):
                emotion_api.get_image_analysis("img123", wait=False)

    def test_get_text_analysis_wait_not_found(self, emotion_api):
        """Test waiting for text analysis when resource is initially not found."""
        from imentiv.exceptions import ImentivNotFoundError
        
        mock_completed = {"status": "completed", "data": {}}
        
        with patch.object(emotion_api.client, "get") as mock_get:
            mock_get.side_effect = [
                ImentivNotFoundError("Not found"),
                mock_completed
            ]
            
            with patch("time.sleep"):
                result = emotion_api.get_text_analysis("txt123", wait=True)

        assert mock_get.call_count == 2
        assert result == mock_completed

    def test_get_text_analysis_wait_server_error(self, emotion_api):
        """Test waiting for text analysis when server errors initially."""
        from imentiv.exceptions import ImentivServerError
        
        mock_completed = {"status": "completed", "data": {}}
        
        with patch.object(emotion_api.client, "get") as mock_get:
            mock_get.side_effect = [
                ImentivServerError("Server error"),
                mock_completed
            ]
            
            with patch("time.sleep"):
                result = emotion_api.get_text_analysis("txt123", wait=True)

        assert mock_get.call_count == 2
        assert result == mock_completed

    def test_get_text_analysis_raise_not_found(self, emotion_api):
        """Test that get_text_analysis raises ImentivNotFoundError when wait=False."""
        from imentiv.exceptions import ImentivNotFoundError
        
        with patch.object(emotion_api.client, "get", side_effect=ImentivNotFoundError("Not found")):
            with pytest.raises(ImentivNotFoundError):
                emotion_api.get_text_analysis("txt123", wait=False)

    def test_get_text_analysis_raise_server_error(self, emotion_api):
        """Test that get_text_analysis raises ImentivServerError when wait=False."""
        from imentiv.exceptions import ImentivServerError
        
        with patch.object(emotion_api.client, "get", side_effect=ImentivServerError("Server error")):
            with pytest.raises(ImentivServerError):
                emotion_api.get_text_analysis("txt123", wait=False)
