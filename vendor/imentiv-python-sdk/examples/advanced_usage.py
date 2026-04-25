"""
Advanced usage example with error handling and best practices.

This example demonstrates:
- Proper error handling
- Context manager usage
- Polling for analysis completion
- Batch operations
"""

import os
import time
from typing import List

from imentiv import ImentivClient
from imentiv.exceptions import (
    ImentivAPIError,
    ImentivAuthenticationError,
    ImentivRateLimitError,
)


def wait_for_analysis_completion(client: ImentivClient, video_id: str, max_wait: int = 300):
    """
    Poll the API until video analysis is complete.

    Args:
        client: The Imentiv client instance.
        video_id: The ID of the video being analyzed.
        max_wait: Maximum time to wait in seconds.

    Returns:
        The final analysis results.

    Raises:
        TimeoutError: If analysis doesn't complete within max_wait seconds.
    """
    start_time = time.time()

    while time.time() - start_time < max_wait:
        status = client.video.get_status(video_id)
        current_status = status.get("status")

        print(f"Status: {current_status}, Progress: {status.get('progress', 0)}%")

        if current_status == "completed":
            print("Analysis completed!")
            return client.video.get_results(video_id)
        elif current_status in ["failed", "error"]:
            raise ImentivAPIError(f"Analysis failed: {status.get('error', 'Unknown error')}")

        # Wait before checking again
        time.sleep(5)

    raise TimeoutError(f"Analysis did not complete within {max_wait} seconds")


def batch_process_videos(client: ImentivClient, video_paths: List[str]):
    """
    Upload and analyze multiple videos.

    Args:
        client: The Imentiv client instance.
        video_paths: List of paths to video files.

    Returns:
        List of video IDs that were successfully uploaded.
    """
    video_ids = []

    for video_path in video_paths:
        try:
            print(f"Processing: {video_path}")
            result = client.video.upload(video_path)
            video_id = result["video_id"]
            video_ids.append(video_id)

            # Request analysis
            client.video.analyze(video_id, options={"detect_emotions": True})
            print(f"Successfully uploaded and queued: {video_id}")

        except ImentivAPIError as e:
            print(f"Failed to process {video_path}: {e.message}")
            continue

    return video_ids


def example_with_error_handling():
    """Example demonstrating proper error handling."""
    print("=== Error Handling Example ===")

    try:
        # Use context manager for automatic cleanup
        with ImentivClient(api_key=os.environ.get("IMENTIV_API_KEY")) as client:

            # Try to upload a video
            video_path = "path/to/video.mp4"
            result = client.video.upload(video_path)
            video_id = result["video_id"]

            # Request analysis
            client.video.analyze(video_id)

            # Wait for completion
            results = wait_for_analysis_completion(client, video_id)
            print(f"Analysis results: {results}")

    except ImentivAuthenticationError as e:
        print(f"Authentication failed: {e.message}")
        print("Please check your API key.")

    except ImentivRateLimitError as e:
        print(f"Rate limit exceeded: {e.message}")
        print("Please wait before making more requests.")

    except ImentivAPIError as e:
        print(f"API error: {e.message}")
        if e.status_code:
            print(f"Status code: {e.status_code}")

    except FileNotFoundError:
        print("Video file not found. Please check the file path.")

    except Exception as e:
        print(f"Unexpected error: {e}")


def example_batch_processing():
    """Example of processing multiple videos."""
    print("\n=== Batch Processing Example ===")

    video_files = [
        "video1.mp4",
        "video2.mp4",
        "video3.mp4",
    ]

    try:
        with ImentivClient(api_key=os.environ.get("IMENTIV_API_KEY")) as client:
            video_ids = batch_process_videos(client, video_files)
            print(f"\nSuccessfully processed {len(video_ids)} videos")

            # Monitor all videos
            for video_id in video_ids:
                try:
                    wait_for_analysis_completion(client, video_id, max_wait=600)
                    print(f"Video {video_id} completed successfully")
                except TimeoutError:
                    print(f"Video {video_id} timed out")
                except ImentivAPIError as e:
                    print(f"Video {video_id} failed: {e.message}")

    except Exception as e:
        print(f"Error during batch processing: {e}")


def example_custom_configuration():
    """Example with custom client configuration."""
    print("\n=== Custom Configuration Example ===")

    # Create client with custom settings using context manager
    with ImentivClient(
        api_key=os.environ.get("IMENTIV_API_KEY"),
        timeout=60,  # Increase timeout to 60 seconds
        max_retries=5,  # Retry up to 5 times
    ) as client:
        # Your API calls here
        account = client.get_account_info()
        print(f"Account info: {account}")


if __name__ == "__main__":
    print("Advanced Usage Examples\n")

    # Uncomment the examples you want to run
    # example_with_error_handling()
    # example_batch_processing()
    # example_custom_configuration()

    print("\nTo run these examples, uncomment the function calls above")
    print("and set the IMENTIV_API_KEY environment variable.")
