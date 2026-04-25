"""Test configuration and fixtures."""

import pytest


@pytest.fixture
def mock_api_key():
    """Provide a mock API key for testing."""
    return "test_api_key_12345"


@pytest.fixture
def mock_video_id():
    """Provide a mock video ID for testing."""
    return "video_abc123"


@pytest.fixture
def mock_video_upload_response():
    """Mock response for video upload."""
    return {
        "video_id": "video_abc123",
        "status": "processing",
        "created_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def mock_emotion_response():
    """Mock response for emotion detection."""
    return {
        "emotions": [
            {"type": "happy", "confidence": 0.95},
            {"type": "neutral", "confidence": 0.05},
        ]
    }


@pytest.fixture
def mock_face_response():
    """Mock response for face detection."""
    return {
        "faces": [
            {
                "x": 100,
                "y": 150,
                "width": 200,
                "height": 200,
                "confidence": 0.98,
            }
        ]
    }
