"""
Main Imentiv SDK client.
"""

from typing import Optional

from imentiv.api.audio import AudioAPI
from imentiv.api.emotion import EmotionAPI
from imentiv.api.face import FaceAPI
from imentiv.api.video import VideoAPI
from imentiv.base_client import BaseClient
from imentiv.config import Config


class ImentivClient:
    """
    Main client for interacting with the Imentiv AI API.

    This client provides access to video analysis, emotion detection,
    face analysis, and audio analysis capabilities through a simple, intuitive interface.

    Example:
        >>> from imentiv import ImentivClient
        >>> client = ImentivClient(api_key="your-api-key")
        >>>
        >>> # Upload and analyze a video
        >>> result = client.video.upload("video.mp4")
        >>> video_id = result["video_id"]
        >>> analysis = client.video.analyze(video_id)
        >>>
        >>> # Analyze audio
        >>> audio_result = client.audio.upload("audio.mp3")
        >>>
        >>> # Detect emotions from an image
        >>> emotions = client.emotion.detect_from_image("photo.jpg")
        >>>
        >>> # Detect faces
        >>> faces = client.face.detect_faces("group_photo.jpg")

    Attributes:
        video: Video analysis API client.
        emotion: Emotion detection API client.
        face: Face analysis API client.
        audio: Audio analysis API client.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        """
        Initialize the Imentiv client.

        Args:
            api_key: Your Imentiv API key. If not provided, will try to read
                    from the IMENTIV_API_KEY environment variable.
            base_url: Base URL for the API. Defaults to https://api.imentiv.ai/v1
            timeout: Request timeout in seconds. Defaults to 30.
            max_retries: Maximum number of retries for failed requests. Defaults to 3.

        Raises:
            ValueError: If API key is not provided and not found in environment.

        Example:
            >>> client = ImentivClient(api_key="your-api-key")
            >>> # Or using environment variable
            >>> import os
            >>> os.environ["IMENTIV_API_KEY"] = "your-api-key"
            >>> client = ImentivClient()
        """
        self.config = Config(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._base_client = BaseClient(self.config)

        # Initialize API clients
        self.video = VideoAPI(self._base_client)
        self.emotion = EmotionAPI(self._base_client)
        self.face = FaceAPI(self._base_client)
        self.audio = AudioAPI(self._base_client)

    def close(self) -> None:
        """
        Close the client and clean up resources.

        Example:
            >>> client = ImentivClient(api_key="your-api-key")
            >>> # ... use client ...
            >>> client.close()
        """
        self._base_client.close()

    def __enter__(self):
        """
        Context manager entry.

        Example:
            >>> with ImentivClient(api_key="your-api-key") as client:
            ...     result = client.video.upload("video.mp4")
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def get_account_info(self):
        """
        Get account information and usage statistics.

        Returns:
            Dictionary containing account details and usage limits.

        Example:
            >>> client.get_account_info()
            {"credits_remaining": 1000, "plan": "pro", "usage": {...}}
        """
        return self._base_client.get("/account")

    def get_api_version(self):
        """
        Get the current API version information.

        Returns:
            Dictionary containing API version and status.

        Example:
            >>> client.get_api_version()
            {"version": "1.0.0", "status": "operational"}
        """
        return self._base_client.get("/version")

    def __repr__(self) -> str:
        """Return a string representation with masked API key."""
        return f"ImentivClient({self.config!r})"
