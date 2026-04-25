"""
Basic usage example for the Imentiv Python SDK.

This example demonstrates the core functionality of the SDK including:
- Client initialization
- Video upload and analysis
- Emotion detection
- Face detection
"""

import os
import logging
import http.client as http_client

# Enable debug logging for HTTP requests
# http_client.HTTPConnection.debuglevel = 1
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

import argparse
from imentiv import ImentivClient


def example_video_analysis(client, video_id=None):
    """Example: Upload and analyze a video."""
    print("=== Video Analysis Example ===")

    if not video_id:
        # Upload a video file
        video_path = "media/video1.mp4"
        print(f"Uploading video: {video_path}")
        upload_result = client.video.upload(video_path)
        video_id = upload_result["id"]
        print(f"Video uploaded successfully. ID: {video_id}")
    else:
        print(f"Using existing Video ID: {video_id}")

    # Check status
    print("Checking analysis status...")
    status = client.video.get_status(video_id, wait=True)
    print(f"Status: {status}")

    # Get results (once processing is complete)
    if status.get("status") == "completed":
        print("Getting analysis results...")
        results = client.video.get_results(video_id)
        print(f"Results: {results}")

    # List all videos
    print("Listing videos...")
    videos = client.video.list(page=1, per_page=10)
    print(f"Total videos: {videos.get('count', 0)}")


def example_image_emotion_detection(client):
    """Example: Detect emotions from an image."""
    print("\n=== Image Emotion Detection Example ===")
    
    try:
        image_path = "media/image1.png"
        print(f"Uploading image for emotion detection: {image_path}")
        result = client.emotion.detect_from_image(image_path)
        image_id = result.get("image_id")
        print(f"Image uploaded. ID: {image_id}")

        # Get results with wait=True
        print("Waiting for image analysis...")
        status_res = client.emotion.get_image_analysis(image_id, wait=True)
        print(f"Image analysis completed: {status_res}")
                
    except Exception as e:
        print(f"Image emotion detection failed: {e}")


def example_text_emotion_detection(client):
    """Example: Detect emotions from text."""
    print("\n=== Text Emotion Detection Example ===")
    
    try:
        text = "I am so excited about this new project!"
        print(f"Analyzing text: '{text}'")
        text_upload = client.emotion.detect_from_text(text)
        text_id = text_upload.get("id")
        print(f"Text uploaded. ID: {text_id}")
        
        # Get results with wait=True
        print("Waiting for text analysis...")
        status_res = client.emotion.get_text_analysis(text_id, wait=True)
        print(f"Text analysis completed: {status_res}")

    except Exception as e:
        print(f"Text emotion detection failed: {e}")


def example_face_detection(client):
    """Example: Detect and analyze faces."""
    print("\n=== Face Detection Example ===")
    
    try:
        # Since face detection is part of image analysis, we reuse the flow
        image_path = "media/image1.png"
        print(f"Detecting faces in: {image_path}")
        
        # Use the face API wrapper
        result = client.face.detect_faces(image_path)
        image_id = result.get("image_id")
        print(f"Image uploaded for face detection. ID: {image_id}")
        
        # We can also wait via face API if implemented, or re-use emotion API
        # but let's assume we just want to verify content.
        # Track faces in video also supports wait now.
    except Exception as e:
        print(f"Face detection failed: {e}")


def example_audio_analysis(client):
    """Example: Upload and analyze audio."""
    print("\n=== Audio Analysis Example ===")
    
    try:
        audio_path = "media/audio1.mp3"
        print(f"Uploading audio: {audio_path}")
        
        # Upload
        upload_result = client.audio.upload(audio_path)
        audio_id = upload_result.get("audio_id") or upload_result.get("id")
        print(f"Audio uploaded successfully. ID: {audio_id}")
        
        # Get results (wait for completion)
        print("Waiting for audio analysis...")
        results = client.audio.get_results(audio_id, wait=True)
        print(f"Audio analysis completed: {results}")

    except Exception as e:
        print(f"Audio analysis failed: {e}")


def example_account_info(client):
    """Example: Get account information."""
    print("\n=== Account Information Example ===")

    # Get account info
    account = client.get_account_info()

    print(f"Account info: {account}")

    # Get API version
    version = client.get_api_version()
    print(f"API version: {version}")



def main():
    parser = argparse.ArgumentParser(description="Imentiv SDK Basic Usage Example")
    parser.add_argument("--api-key", help="Imentiv API Key")
    parser.add_argument("--video-id", help="Existing Video ID to check status for (skips upload)")
    parser.add_argument(
        "--media", 
        choices=["video", "audio", "text", "image", "all"], 
        default="all",
        help="Type of analysis to run (video, audio, text, image, or all)"
    )
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("IMENTIV_API_KEY")
    if not api_key:
        raise ValueError("Please provide an API key via --api-key or IMENTIV_API_KEY environment variable")

    print(f"Using API Key: {api_key}")
    client = ImentivClient(api_key=api_key)

    try:
        run_all = args.media == "all"
        
        if run_all or args.media == "video":
            example_video_analysis(client, video_id=args.video_id)
            
        if run_all or args.media == "image":
            example_image_emotion_detection(client)
            example_face_detection(client)

        if run_all or args.media == "text":
            example_text_emotion_detection(client)

        if run_all or args.media == "audio":
            example_audio_analysis(client)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()

