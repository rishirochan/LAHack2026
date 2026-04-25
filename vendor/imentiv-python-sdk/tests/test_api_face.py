"""Tests for the Face API client."""

import pytest
from unittest.mock import patch, mock_open

from imentiv.api.face import FaceAPI
from imentiv.base_client import BaseClient
from imentiv.config import Config


@pytest.fixture
def mock_base_client(mock_api_key):
    """Create a mock base client."""
    config = Config(api_key=mock_api_key)
    client = BaseClient(config)
    return client


@pytest.fixture
def face_api(mock_base_client):
    """Create a FaceAPI instance with mocked client."""
    return FaceAPI(mock_base_client)


class TestFaceAPI:
    """Tests for FaceAPI class."""

    def test_detect_faces(self, face_api):
        """Test detecting faces in an image."""
        mock_response = {"image_id": "img123"}
        
        with patch.object(face_api.client, "post", return_value=mock_response) as mock_post:
            with patch("builtins.open", mock_open(read_data=b"fake image data")):
                result = face_api.detect_faces("/path/to/image.jpg")

        assert result == mock_response
        args, kwargs = mock_post.call_args
        assert args[0] == "v1/images"
        assert kwargs["data"]["title"] == "Face Detection: image.jpg"
        assert kwargs["data"]["description"] == ""

    def test_analyze_face_attributes(self, face_api):
        """Test analyzing face attributes."""
        # Delegates to detect_faces
        mock_response = {"image_id": "img123"}
        
        with patch.object(face_api.client, "post", return_value=mock_response):
            with patch("builtins.open", mock_open(read_data=b"fake image data")):
                result = face_api.analyze_face_attributes("/path/to/image.jpg")
        
        assert result == mock_response

    def test_compare_faces(self, face_api):
        """Test comparing two faces (NotImplemented)."""
        with pytest.raises(NotImplementedError):
            face_api.compare_faces("/path/to/img1.jpg", "/path/to/img2.jpg")

    def test_track_faces_in_video(self, face_api, mock_video_id):
        """Test tracking faces in a video."""
        mock_response = {"status": "completed", "faces": []}

        with patch.object(face_api.client, "get", return_value=mock_response) as mock_get:
            result = face_api.track_faces_in_video(mock_video_id)

        mock_get.assert_called_once_with(f"v2/videos/{mock_video_id}/multimodal-analytics")
        assert result == mock_response

    def test_track_faces_unprocessable_processing(self, face_api, mock_video_id):
        """Test handling unprocessable entity error that indicates processing."""
        from imentiv.exceptions import ImentivUnprocessableEntityError
        
        error = ImentivUnprocessableEntityError("'annotated_video_mp4' field required")
        
        with patch.object(face_api.client, "get", side_effect=[error, {"status": "completed"}]):
            with patch("time.sleep"):
                result = face_api.track_faces_in_video(mock_video_id, wait=True)
                 
        assert result["status"] == "completed"

    def test_track_faces_unprocessable_other(self, face_api, mock_video_id):
        """Test handling unprocessable entity error that is a real error."""
        from imentiv.exceptions import ImentivUnprocessableEntityError
        
        error = ImentivUnprocessableEntityError("Other error")
        
        with patch.object(face_api.client, "get", side_effect=error):
            with pytest.raises(ImentivUnprocessableEntityError):
                face_api.track_faces_in_video(mock_video_id)

    def test_track_faces_wait_not_found(self, face_api, mock_video_id):
        """Test waiting for tracking when resource is initially not found."""
        from imentiv.exceptions import ImentivNotFoundError
        
        with patch.object(face_api.client, "get", side_effect=[ImentivNotFoundError("Msg"), {"status": "completed"}]):
            with patch("time.sleep"):
                result = face_api.track_faces_in_video(mock_video_id, wait=True)
        
        assert result["status"] == "completed"

    def test_track_faces_wait_server_error(self, face_api, mock_video_id):
        """Test waiting for tracking when server errors initially."""
        from imentiv.exceptions import ImentivServerError
        
        with patch.object(face_api.client, "get", side_effect=[ImentivServerError("Msg"), {"status": "completed"}]):
            with patch("time.sleep"):
                result = face_api.track_faces_in_video(mock_video_id, wait=True)
        
        assert result["status"] == "completed"

    def test_track_faces_raise_not_found(self, face_api, mock_video_id):
        """Test raising NotFoundError when wait=False."""
        from imentiv.exceptions import ImentivNotFoundError
        
        with patch.object(face_api.client, "get", side_effect=ImentivNotFoundError("Msg")):
            with pytest.raises(ImentivNotFoundError):
                face_api.track_faces_in_video(mock_video_id, wait=False)

    def test_track_faces_raise_server_error(self, face_api, mock_video_id):
        """Test raising ServerError when wait=False."""
        from imentiv.exceptions import ImentivServerError
        
        with patch.object(face_api.client, "get", side_effect=ImentivServerError("Msg")):
            with pytest.raises(ImentivServerError):
                face_api.track_faces_in_video(mock_video_id, wait=False)
