"""
Face analysis API endpoints.
"""

from typing import Any, Dict, Optional

from imentiv.base_client import BaseClient


class FaceAPI:
    """API client for face analysis operations."""

    def __init__(self, client: BaseClient):
        """
        Initialize the Face API client.

        Args:
            client: The base HTTP client.
        """
        self.client = client

    def detect_faces(self, image_path: str) -> Dict[str, Any]:
        """
        Detect faces in an image (using Image Emotion API).
        
        Note: This delegates to the image upload process.
        Returns the initial response from image upload.
        """
        import os
        title = "Face Detection: " + os.path.basename(image_path)
        with open(image_path, "rb") as f:
            files = {"image": f}
            data = {"title": title, "description": ""}
            return self.client.post("v1/images", files=files, data=data)

    def analyze_face_attributes(self, image_path: str) -> Dict[str, Any]:
        """
        Analyze face attributes.
        """
        return self.detect_faces(image_path)
    
    def compare_faces(self, image_path1: str, image_path2: str) -> Dict[str, Any]:
        """
        Compare faces.
        Note: This functionality is not currently supported by the public API v2/v1 endpoints found.
        """
        raise NotImplementedError("Face comparison is not currently available via the API.")
    
    def track_faces_in_video(
        self,
        video_id: str,
        options: Optional[Dict[str, Any]] = None,
        wait: bool = False,
        poll_interval: float = 2.0
    ) -> Dict[str, Any]:
        """
        Track faces in video.
        
        Args:
            video_id: The ID of the video to analyze.
            options: Optional configuration (unused here but kept for compatibility).
            wait: If True, waits until the analysis is completed.
            poll_interval: Time in seconds to wait between checks.

        Returns:
            Video details which include face tracking data.
        """
        import time
        from imentiv.exceptions import ImentivServerError, ImentivUnprocessableEntityError, ImentivNotFoundError

        while True:
            try:
                response = self.client.get(f"v2/videos/{video_id}/multimodal-analytics")
                status = response.get("status")
            except ImentivUnprocessableEntityError as e:
                # If the error is about missing annotated video, it means it's still processing
                if "'annotated_video_mp4' field required" in str(e.message):
                    status = "processing"
                    response = {"status": "processing", "id": video_id}
                else:
                    raise
            except ImentivNotFoundError:
                if wait:
                    status = "processing"
                    response = {"status": "processing", "id": video_id}
                else:
                    raise
            except ImentivServerError:
                 if wait:
                     status = "processing"
                     response = {"status": "processing", "id": video_id}
                 else:
                     raise

            if not wait:
                return response

            if status in ["completed", "failed"]:
                return response
            
            time.sleep(poll_interval)
