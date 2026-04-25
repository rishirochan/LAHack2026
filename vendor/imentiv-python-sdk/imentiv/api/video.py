"""
Video analysis API endpoints.
"""

from typing import Any, Dict, Optional

from imentiv.base_client import BaseClient


class VideoAPI:
    """API client for video analysis operations."""

    def __init__(self, client: BaseClient):
        """
        Initialize the Video API client.

        Args:
            client: The base HTTP client.
        """
        self.client = client

    def upload(
        self,
        file_path: str,
        title: Optional[str] = None,
        description: str = "",
        user_consent_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a video file for analysis.

        Args:
            file_path: Path to the video file to upload.
            title: Optional title for the video. Defaults to filename.
            description: Optional description for the video.
            user_consent_version: Imentiv consent version accepted for this upload.

        Returns:
            Dictionary containing the upload response with video ID.

        Example:
            >>> client.video.upload("path/to/video.mp4", title="My video", description="A test video")
            {"video_id": "abc123", "status": "processing"}
        """
        if title is None:
            # Use filename as default title
            import os
            title = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            files = {"video_file": f}
            data = {"title": title, "description": description}
            params = None
            headers = None
            if user_consent_version:
                data["user_consent_version"] = user_consent_version
                data["consent_version"] = user_consent_version
                params = {"user_consent_version": user_consent_version}
                headers = {
                    "X-User-Consent-Version": user_consent_version,
                    "X-Consent-Version": user_consent_version,
                }
            # Use v2 endpoint
            response = self.client.post("v2/videos", files=files, data=data, params=params, headers=headers)
            
            # Map 'id' to 'video_id' for backward compatibility
            if "id" in response and "video_id" not in response:
                response["video_id"] = response["id"]
                
            return response

    def analyze(self, video_id: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Request analysis for an uploaded video.

        Args:
            video_id: The ID of the uploaded video.
            options: Optional analysis configuration.

        Returns:
            Dictionary containing the analysis request response.

        Example:
            >>> client.video.analyze("abc123", options={"detect_emotions": True})
            {"analysis_id": "xyz789", "status": "queued"}
        """
        payload = {"video_id": video_id}
        if options:
            payload.update(options)
        return self.client.post("v2/videos/analyze", json=payload)

    def get_status(
        self, 
        video_id: str, 
        wait: bool = False, 
        poll_interval: float = 2.0
    ) -> Dict[str, Any]:
        """
        Get the processing status of a video.

        Args:
            video_id: The ID of the video.
            wait: If True, waits until the processing is completed (or failed).
            poll_interval: Time in seconds to wait between status checks.

        Returns:
            Dictionary containing the video status.

        Example:
            >>> client.video.get_status("abc123", wait=True)
            {"status": "completed", "progress": 100}
        """
        import time
        from imentiv.exceptions import ImentivUnprocessableEntityError, ImentivServerError, ImentivNotFoundError

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
                # If the video is not found yet (transient), retry if waiting
                if wait:
                    status = "processing"
                    response = {"status": "processing", "id": video_id}
                else:
                    raise
            except ImentivServerError:
                 # Should retry on 500 error during polling
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

    def get_results(
        self, 
        video_id: str, 
        wait: bool = False, 
        poll_interval: float = 2.0
    ) -> Dict[str, Any]:
        """
        Get the analysis results for a video.

        Args:
            video_id: The ID of the video.
            wait: If True, waits until the analysis is completed.
            poll_interval: Time in seconds to wait between checks.

        Returns:
            Dictionary containing the complete analysis results.
        """
        if wait:
            self.get_status(video_id, wait=True, poll_interval=poll_interval)
        return self.client.get(f"v2/videos/{video_id}/multimodal-analytics")

    def list(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """
        List all videos.

        Args:
            page: Page number for pagination.
            per_page: Number of results per page.

        Returns:
            Dictionary containing list of videos and pagination info.

        Example:
            >>> client.video.list(page=1, per_page=10)
            {"videos": [...], "total": 42, "page": 1}
        """
        params = {"page": page, "per_page": per_page}
        return self.client.get("v2/videos", params=params)

    def delete(self, video_id: str) -> Dict[str, Any]:
        """
        Delete a video.

        Args:
            video_id: The ID of the video to delete.

        Returns:
            Dictionary containing the deletion confirmation.

        Example:
            >>> client.video.delete("abc123")
            {"message": "Video deleted successfully"}
        """
        return self.client.delete(f"v2/videos/{video_id}")
