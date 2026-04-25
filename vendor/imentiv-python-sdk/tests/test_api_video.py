"""Tests for the Video API client."""

import pytest
from unittest.mock import patch, mock_open

from imentiv.api.video import VideoAPI
from imentiv.base_client import BaseClient
from imentiv.config import Config


@pytest.fixture
def mock_base_client(mock_api_key):
    """Create a mock base client."""
    config = Config(api_key=mock_api_key)
    client = BaseClient(config)
    return client


@pytest.fixture
def video_api(mock_base_client):
    """Create a VideoAPI instance with mocked client."""
    return VideoAPI(mock_base_client)


class TestVideoAPI:
    """Tests for VideoAPI class."""

    def test_upload_calls_post_with_file(self, video_api, mock_video_upload_response):
        """Test that upload opens file and calls post."""
        with patch.object(video_api.client, "post", return_value=mock_video_upload_response) as mock_post:
            with patch("builtins.open", mock_open(read_data=b"fake video data")):
                result = video_api.upload("/path/to/video.mp4", user_consent_version="2.0.0")

        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs["data"]["user_consent_version"] == "2.0.0"
        assert mock_post.call_args.kwargs["data"]["consent_version"] == "2.0.0"
        assert mock_post.call_args.kwargs["params"]["user_consent_version"] == "2.0.0"
        assert mock_post.call_args.kwargs["headers"]["X-User-Consent-Version"] == "2.0.0"
        assert result == mock_video_upload_response
        assert result["video_id"] == "video_abc123"

    def test_analyze_with_options(self, video_api, mock_video_id):
        """Test analyze with custom options."""
        mock_response = {"analysis_id": "xyz789", "status": "queued"}

        with patch.object(video_api.client, "post", return_value=mock_response) as mock_post:
            result = video_api.analyze(mock_video_id, options={"detect_emotions": True})

        mock_post.assert_called_once_with(
            "v2/videos/analyze",
            json={"video_id": mock_video_id, "detect_emotions": True},
        )
        assert result["status"] == "queued"

    def test_analyze_without_options(self, video_api, mock_video_id):
        """Test analyze without options."""
        mock_response = {"analysis_id": "xyz789", "status": "queued"}

        with patch.object(video_api.client, "post", return_value=mock_response) as mock_post:
            result = video_api.analyze(mock_video_id)

        mock_post.assert_called_once_with(
            "v2/videos/analyze",
            json={"video_id": mock_video_id},
        )
        assert result["analysis_id"] == "xyz789"

    def test_get_status(self, video_api, mock_video_id):
        """Test getting video status."""
        mock_response = {"status": "completed", "progress": 100}

        with patch.object(video_api.client, "get", return_value=mock_response) as mock_get:
            result = video_api.get_status(mock_video_id)

        mock_get.assert_called_once_with(f"v2/videos/{mock_video_id}/multimodal-analytics")
        assert result["status"] == "completed"
        assert result["progress"] == 100

    def test_get_results(self, video_api, mock_video_id):
        """Test getting video results."""
        mock_response = {"emotions": [], "faces": [], "timestamps": []}

        with patch.object(video_api.client, "get", return_value=mock_response) as mock_get:
            result = video_api.get_results(mock_video_id)

        mock_get.assert_called_with(f"v2/videos/{mock_video_id}/multimodal-analytics")
        assert "emotions" in result

    def test_list_default_pagination(self, video_api):
        """Test listing videos with default pagination."""
        mock_response = {"videos": [], "total": 0, "page": 1}

        with patch.object(video_api.client, "get", return_value=mock_response) as mock_get:
            result = video_api.list()

        mock_get.assert_called_once_with("v2/videos", params={"page": 1, "per_page": 20})
        assert result["page"] == 1

    def test_list_custom_pagination(self, video_api):
        """Test listing videos with custom pagination."""
        mock_response = {"videos": [], "total": 100, "page": 5}

        with patch.object(video_api.client, "get", return_value=mock_response) as mock_get:
            result = video_api.list(page=5, per_page=50)

        mock_get.assert_called_once_with("v2/videos", params={"page": 5, "per_page": 50})
        assert result["page"] == 5

    def test_delete(self, video_api, mock_video_id):
        """Test deleting a video."""
        mock_response = {"message": "Video deleted successfully"}

        with patch.object(video_api.client, "delete", return_value=mock_response) as mock_delete:
            result = video_api.delete(mock_video_id)

        mock_delete.assert_called_once_with(f"v2/videos/{mock_video_id}")
        assert result["message"] == "Video deleted successfully"

    def test_upload_backward_compatibility(self, video_api):
        """Test that upload handles response with 'id' instead of 'video_id'."""
        mock_response = {"id": "vid_123", "status": "processing"}
        
        with patch.object(video_api.client, "post", return_value=mock_response):
            with patch("builtins.open", mock_open(read_data=b"fake video data")):
                result = video_api.upload("/path/to/video.mp4")

        assert result["video_id"] == "vid_123"
        assert result["id"] == "vid_123"

    def test_get_status_unprocessable_processing(self, video_api, mock_video_id):
        """Test handling unprocessable entity error that indicates processing."""
        from imentiv.exceptions import ImentivUnprocessableEntityError
        
        error = ImentivUnprocessableEntityError("'annotated_video_mp4' field required")
        
        with patch.object(video_api.client, "get", side_effect=[error, {"status": "completed"}]):
            with patch("time.sleep"):
                result = video_api.get_status(mock_video_id, wait=True)
                 
        assert result["status"] == "completed"

    def test_get_status_unprocessable_other(self, video_api, mock_video_id):
        """Test handling unprocessable entity error that is a real error."""
        from imentiv.exceptions import ImentivUnprocessableEntityError
        
        error = ImentivUnprocessableEntityError("Other error")
        
        with patch.object(video_api.client, "get", side_effect=error):
            with pytest.raises(ImentivUnprocessableEntityError):
                video_api.get_status(mock_video_id)

    def test_get_status_wait_not_found(self, video_api, mock_video_id):
        """Test waiting for status when resource is initially not found."""
        from imentiv.exceptions import ImentivNotFoundError
        
        with patch.object(video_api.client, "get", side_effect=[ImentivNotFoundError("Msg"), {"status": "completed"}]):
            with patch("time.sleep"):
                result = video_api.get_status(mock_video_id, wait=True)
        
        assert result["status"] == "completed"

    def test_get_status_wait_server_error(self, video_api, mock_video_id):
        """Test waiting for status when server errors initially."""
        from imentiv.exceptions import ImentivServerError
        
        with patch.object(video_api.client, "get", side_effect=[ImentivServerError("Msg"), {"status": "completed"}]):
            with patch("time.sleep"):
                result = video_api.get_status(mock_video_id, wait=True)
        
        assert result["status"] == "completed"

    def test_get_status_raise_not_found(self, video_api, mock_video_id):
        """Test raising NotFoundError when wait=False."""
        from imentiv.exceptions import ImentivNotFoundError
        
        with patch.object(video_api.client, "get", side_effect=ImentivNotFoundError("Msg")):
            with pytest.raises(ImentivNotFoundError):
                video_api.get_status(mock_video_id, wait=False)

    def test_get_status_raise_server_error(self, video_api, mock_video_id):
        """Test raising ServerError when wait=False."""
        from imentiv.exceptions import ImentivServerError
        
        with patch.object(video_api.client, "get", side_effect=ImentivServerError("Msg")):
            with pytest.raises(ImentivServerError):
                video_api.get_status(mock_video_id, wait=False)

    def test_get_results_wait(self, video_api, mock_video_id):
        """Test getting results with wait=True."""
        mock_response = {"emotions": []}
        
        with patch.object(video_api, "get_status") as mock_status:
            with patch.object(video_api.client, "get", return_value=mock_response) as mock_get:
                result = video_api.get_results(mock_video_id, wait=True)
        
        mock_status.assert_called_once_with(mock_video_id, wait=True, poll_interval=2.0)
        mock_get.assert_called_with(f"v2/videos/{mock_video_id}/multimodal-analytics")
        assert result == mock_response
