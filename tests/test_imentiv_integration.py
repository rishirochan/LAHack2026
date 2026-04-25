import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from imentiv import ImentivClient
from backend.shared.imentiv import extract_video_id, extract_transcript_segments, normalize_imentiv_results


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.content = b"{}" if payload is not None else b""

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.text or f"HTTP {self.status_code}")


class ImentivIntegrationTests(unittest.TestCase):
    def test_video_upload_uses_v2_multipart_and_consent_headers(self) -> None:
        client = ImentivClient(api_key="test-key", timeout=120, max_retries=3)
        calls = []

        def fake_request(**kwargs):
            calls.append(kwargs)
            return FakeResponse(201, {"id": "video-123"})

        client.session.request = fake_request
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
            temp_file.write(b"video")
            temp_path = temp_file.name
        try:
            result = client.video.upload(
                temp_path,
                title="Practice clip",
                description="Chunk analysis",
                user_consent_version="2.0.0",
            )
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertEqual(result["video_id"], "video-123")
        request = calls[0]
        self.assertEqual(request["method"], "POST")
        self.assertTrue(str(request["url"]).endswith("/v2/videos"))
        self.assertIn("video_file", request["files"])
        self.assertEqual(request["data"]["title"], "Practice clip")
        self.assertEqual(request["data"]["description"], "Chunk analysis")
        self.assertEqual(request["data"]["user_consent_version"], "2.0.0")
        self.assertEqual(request["data"]["consent_version"], "2.0.0")
        self.assertEqual(request["headers"]["X-API-Key"], "test-key")
        self.assertEqual(request["headers"]["X-User-Consent-Version"], "2.0.0")
        self.assertEqual(request["headers"]["X-Consent-Version"], "2.0.0")

    def test_extract_video_id_accepts_video_id_or_id(self) -> None:
        self.assertEqual(extract_video_id({"video_id": "new-id"}), "new-id")
        self.assertEqual(extract_video_id({"id": "legacy-id"}), "legacy-id")
        with self.assertRaisesRegex(RuntimeError, "video_id"):
            extract_video_id({"status": "processing"})

    def test_polling_treats_transient_processing_errors_as_waitable(self) -> None:
        client = ImentivClient(api_key="test-key", timeout=120, max_retries=3)
        responses = [
            FakeResponse(404, {"message": "not ready"}),
            FakeResponse(500, {"message": "warming up"}),
            FakeResponse(422, {"error": {"message": "'annotated_video_mp4' field required"}}),
            FakeResponse(200, {"id": "video-123", "status": "completed", "summary": "done"}),
        ]

        def fake_request(**_kwargs):
            return responses.pop(0)

        client.session.request = fake_request
        with patch("imentiv.client.time.sleep", return_value=None):
            result = client.video.get_results("video-123", wait=True, poll_interval=0.01)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["summary"], "done")
        self.assertEqual(responses, [])

    def test_normalize_results_reconstructs_transcript_and_scores(self) -> None:
        raw = {
            "status": "completed",
            "summary": "Strong response",
            "dominant_emotion": {"name": "confidence"},
            "emotion_analysis": {
                "overall": {
                    "confidence": 0.7,
                    "neutral": 0.2,
                    "fear": 0.1,
                }
            },
            "segment_text_emotions": [
                {
                    "start_millis": 0,
                    "end_millis": 1200,
                    "sentence": "I led the launch.",
                    "dominant_emotion": {"label": "confidence"},
                    "emotions": [{"label": "confidence", "score": 0.8}],
                }
            ],
        }

        normalized = normalize_imentiv_results(raw)

        self.assertEqual(normalized["transcript"], "I led the launch.")
        self.assertEqual(normalized["summary"], "Strong response")
        self.assertEqual(normalized["dominant_emotion"], "confidence")
        self.assertGreater(normalized["confidence_score"], 0)
        self.assertGreater(normalized["clarity_score"], 0)
        self.assertEqual(normalized["transcript_segments"][0]["emotion"], "confidence")

    def test_extract_audio_segments_maps_imentiv_shape(self) -> None:
        segments = extract_transcript_segments(
            {
                "segment_text_emotions": [
                    {
                        "start_millis": 500,
                        "end_millis": 1500,
                        "sentence": "hello",
                        "dominant_emotion": {"label": "neutral"},
                        "emotions": [{"label": "neutral", "score": 0.9}],
                    }
                ]
            }
        )

        self.assertEqual(
            segments,
            [
                {
                    "start": 0.5,
                    "end": 1.5,
                    "text": "hello",
                    "emotion": "neutral",
                    "raw_emotions": [{"label": "neutral", "score": 0.9}],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
