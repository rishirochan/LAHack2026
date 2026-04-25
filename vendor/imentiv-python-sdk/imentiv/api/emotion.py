"""
Emotion detection API endpoints.
"""

from typing import Any, Dict, Optional

from imentiv.base_client import BaseClient


class EmotionAPI:
    """API client for emotion detection operations."""

    def __init__(self, client: BaseClient):
        """
        Initialize the Emotion API client.

        Args:
            client: The base HTTP client.
        """
        self.client = client

    def detect_from_image(self, image_path: str, title: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload an image for emotion detection (async).
        
        Args:
            image_path: Path to the image file.
            title: Optional title for the image.
            
        Returns:
            Dictionary containing image_id and status.
        """
        if title is None:
            import os
            title = os.path.basename(image_path)
            
        with open(image_path, "rb") as f:
            files = {"image": f}
            data = {"title": title, "description": ""}
            return self.client.post("v1/images", files=files, data=data)

    def get_image_analysis(
        self, 
        image_id: str, 
        wait: bool = False, 
        poll_interval: float = 2.0
    ) -> Dict[str, Any]:
        """
        Get the analysis results for a specific image.
        
        Args:
            image_id: The ID of the image.
            wait: If True, waits until the analysis is completed.
            poll_interval: Time in seconds to wait between checks.
            
        Returns:
            Dictionary containing the analysis results.
        """
        import time
        from imentiv.exceptions import ImentivServerError, ImentivNotFoundError
        
        while True:
            try:
                response = self.client.get(f"v1/images/{image_id}")
                status = response.get("status")
            except ImentivNotFoundError:
                if wait:
                    status = "processing"
                    response = {"status": "processing", "id": image_id}
                else:
                    raise
            except ImentivServerError:
                 if wait:
                     status = "processing"
                     response = {"status": "processing", "id": image_id}
                 else:
                     raise

            if not wait:
                return response

            if status in ["completed", "failed"]:
                return response
            
            time.sleep(poll_interval)

    def detect_from_text(self, text: str, title: str = "Text Analysis") -> Dict[str, Any]:
        """
        Analyze text for emotions (async).
        
        Args:
            text: Text to analyze.
            title: Optional title for the analysis.
            
        Returns:
            Dictionary containing text_id and status.
        """
        data = {"text": text, "title": title}
        # Use v2 endpoint for text upload
        return self.client.post("v2/texts", data=data)

    def get_text_analysis(
        self, 
        text_id: str, 
        wait: bool = False, 
        poll_interval: float = 2.0
    ) -> Dict[str, Any]:
        """
        Get the analysis results for a specific text.
        
        Args:
            text_id: The ID of the text.
            wait: If True, waits until the analysis is completed.
            poll_interval: Time in seconds to wait between checks.
            
        Returns:
            Dictionary containing the analysis results.
        """
        import time
        from imentiv.exceptions import ImentivServerError, ImentivNotFoundError

        while True:
            try:
                response = self.client.get(f"v1/texts/{text_id}")
                status = response.get("status")
            except ImentivNotFoundError:
                if wait:
                    status = "processing"
                    response = {"status": "processing", "id": text_id}
                else:
                    raise
            except ImentivServerError:
                 if wait:
                     status = "processing"
                     response = {"status": "processing", "id": text_id}
                 else:
                     raise

            if not wait:
                return response

            if status in ["completed", "failed"]:
                return response
            
            time.sleep(poll_interval)

    def analyze_video_emotions(
        self,
        video_id: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze emotions throughout a video.
        
        Note: This initiates a comprehensive analysis. Use video.get_results() to fetch data.
        """
        # It seems specific emotion endpoints for video might not be needed if standard video pipeline covers it.
        # But keeping method signature for now, possibly forwarding or using available endpoints.
        # Based on OpenAPI, there is no direct POST /emotions/video. 
        # Analysis starts on upload.
        # We can implement specific emotion retrieval methods here.
        return self.client.get(f"v2/videos/{video_id}/multimodal-analytics")

    def get_emotion_categories(self) -> Dict[str, Any]:
        """
        Get available emotion categories.
        
        Returns:
            List of supported emotions (hardcoded as API doesn't provide endpoint).
        """
        return {
            "categories": [
                "admiration", "amusement", "approval", "caring", "desire", 
                "excitement", "gratitude", "joy", "love", "optimism", 
                "pride", "relief", "anger", "disappointment", "annoyance", 
                "disapproval", "disgust", "embarrassment", "fear", "grief", 
                "nervousness", "remorse", "sadness", "confusion", "curiosity", 
                "realization", "surprise", "neutral"
            ]
        }
