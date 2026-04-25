"""Tests for response models."""

from imentiv.models.response import AnalysisResult, Emotion, Face, VideoInfo


def test_video_info_from_dict():
    """Test VideoInfo creation from dictionary."""
    data = {
        "video_id": "abc123",
        "status": "completed",
        "created_at": "2024-01-01T00:00:00Z",
        "duration": 30.5,
        "size": 1024000,
    }
    video_info = VideoInfo.from_dict(data)
    assert video_info.video_id == "abc123"
    assert video_info.status == "completed"
    assert video_info.duration == 30.5
    assert video_info.size == 1024000


def test_emotion_from_dict():
    """Test Emotion creation from dictionary."""
    data = {
        "emotion_type": "happy",
        "confidence": 0.95,
        "timestamp": 5.5,
    }
    emotion = Emotion.from_dict(data)
    assert emotion.emotion_type == "happy"
    assert emotion.confidence == 0.95
    assert emotion.timestamp == 5.5


def test_emotion_from_dict_with_type_key():
    """Test Emotion creation with 'type' key instead of 'emotion_type'."""
    data = {
        "type": "sad",
        "confidence": 0.8,
    }
    emotion = Emotion.from_dict(data)
    assert emotion.emotion_type == "sad"
    assert emotion.confidence == 0.8


def test_face_from_dict():
    """Test Face creation from dictionary."""
    data = {
        "x": 100,
        "y": 150,
        "width": 200,
        "height": 200,
        "confidence": 0.98,
        "attributes": {"age": 25, "gender": "female"},
    }
    face = Face.from_dict(data)
    assert face.x == 100
    assert face.y == 150
    assert face.width == 200
    assert face.height == 200
    assert face.confidence == 0.98
    assert face.attributes["age"] == 25


def test_analysis_result_from_dict():
    """Test AnalysisResult creation from dictionary."""
    data = {
        "video_id": "abc123",
        "status": "completed",
        "emotions": [
            {"emotion_type": "happy", "confidence": 0.9},
            {"type": "neutral", "confidence": 0.1},
        ],
        "faces": [{"x": 50, "y": 60, "width": 100, "height": 100, "confidence": 0.95}],
        "summary": {"dominant_emotion": "happy"},
    }
    result = AnalysisResult.from_dict(data)
    assert result.video_id == "abc123"
    assert result.status == "completed"
    assert len(result.emotions) == 2
    assert len(result.faces) == 1
    assert result.summary["dominant_emotion"] == "happy"
