"""
Audio analysis API endpoints.
"""

from typing import Any, Dict, Optional

from imentiv.base_client import BaseClient


class AudioAPI:
    """API client for audio analysis operations."""

    def __init__(self, client: BaseClient):
        """
        Initialize the Audio API client.

        Args:
            client: The base HTTP client.
        """
        self.client = client

    def upload(
        self, 
        file_path: str, 
        title: Optional[str] = None, 
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Upload an audio file for analysis (using v2 endpoint).

        Args:
            file_path: Path to the audio file to upload.
            title: Optional title for the audio. Defaults to filename.
            description: Optional description for the audio.

        Returns:
            Dictionary containing the upload response with audio ID.
        """
        if title is None:
            import os
            title = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            files = {"audio_file": f}
            data = {"title": title, "description": description}
            # Use v2 endpoint
            response = self.client.post("v2/audios", files=files, data=data)
            
            # Map 'id' to 'audio_id' for backward compatibility
            if "id" in response and "audio_id" not in response:
                response["audio_id"] = response["id"]
                
            return response

    def get_results(
        self, 
        audio_id: str, 
        wait: bool = False, 
        poll_interval: float = 2.0
    ) -> Dict[str, Any]:
        """
        Get the analysis results for a specific audio (v1 endpoint).
        
        Args:
            audio_id: The ID of the audio.
            wait: If True, waits until the analysis is completed.
            poll_interval: Time in seconds to wait between checks.
            
        Returns:
            Dictionary containing the analysis results.
        """
        import time
        from imentiv.exceptions import ImentivServerError, ImentivNotFoundError

        while True:
            try:
                response = self.client.get(f"v2/audios/{audio_id}/multimodal-analytics")
                status = response.get("status")
            except ImentivNotFoundError:
                if wait:
                    status = "processing"
                    response = {"status": "processing", "id": audio_id}
                else:
                    raise
            except ImentivServerError:
                 if wait:
                     status = "processing"
                     response = {"status": "processing", "id": audio_id}
                 else:
                     raise

            if not wait:
                return response

            if status in ["completed", "failed"]:
                return response
            
            time.sleep(poll_interval)

    def list(
        self, 
        page_size: int = 10, 
        offset_audio_id: Optional[str] = None,
        direction: str = "forward"
    ) -> Dict[str, Any]:
        """
        List all audios.

        Args:
            page_size: Number of results to return.
            offset_audio_id: The ID of the reference audio for pagination.
            direction: Pagination direction ('forward' or 'backward').

        Returns:
            Dictionary containing list of audios.
        """
        params = {"page_size": page_size, "direction": direction}
        if offset_audio_id:
            params["offset_audio_id"] = offset_audio_id
            
        return self.client.get("v2/audios", params=params)
