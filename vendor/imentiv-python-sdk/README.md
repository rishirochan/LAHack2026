# Imentiv Python SDK

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A comprehensive Python SDK for the [Imentiv AI API](https://imentiv.ai/apis/), providing easy access to emotion detection, video analysis, and face recognition capabilities.

## Features

- 🎭 **Emotion Detection** - Analyze emotions from images, videos, and text
- 🎥 **Video Analysis** - Upload and process videos for comprehensive emotion and face analysis
- 👤 **Face Detection** - Detect faces, analyze attributes, and compare faces
- 🔒 **Secure** - API key authentication with proper error handling
- 🚀 **Easy to Use** - Intuitive, well-documented API
- ⚡ **Robust** - Built-in retry logic and error handling
- 🔄 **Async Support** - Context manager support for resource management

## Installation

Install the SDK using pip:

```bash
pip install imentiv
```

For development with testing tools:

```bash
pip install imentiv[dev]
```

## Quick Start

```python
from imentiv import ImentivClient

# Initialize the client
client = ImentivClient(api_key="your-api-key-here")

# Upload and analyze a video
result = client.video.upload("path/to/video.mp4")
video_id = result["video_id"]
analysis = client.video.analyze(video_id)

# Detect emotions from an image
emotions = client.emotion.detect_from_image("path/to/image.jpg")

# Detect faces
faces = client.face.detect_faces("path/to/image.jpg")

# Don't forget to close the client
client.close()
```

### Using Context Manager (Recommended)

```python
from imentiv import ImentivClient

with ImentivClient(api_key="your-api-key-here") as client:
    result = client.video.upload("video.mp4")
    # Client automatically closes when exiting the context
```

## Authentication

The SDK requires an API key from Imentiv. You can provide it in two ways:

### 1. Pass directly to the client

```python
client = ImentivClient(api_key="your-api-key-here")
```

### 2. Set as an environment variable

```bash
export IMENTIV_API_KEY="your-api-key-here"
```

```python
client = ImentivClient()  # Automatically reads from environment
```

## Usage Examples

### Video Analysis

```python
from imentiv import ImentivClient

with ImentivClient(api_key="your-api-key") as client:
    # Upload a video
    upload_result = client.video.upload("meeting_recording.mp4")
    video_id = upload_result["video_id"]
    
    # Request analysis
    analysis = client.video.analyze(video_id, options={
        "detect_emotions": True,
        "detect_faces": True,
    })
    
    # Check status
    status = client.video.get_status(video_id)
    print(f"Status: {status['status']}")
    
    # Get results (when completed)
    if status["status"] == "completed":
        results = client.video.get_results(video_id)
        print(f"Emotions detected: {results['emotions']}")
    
    # List all videos
    videos = client.video.list(page=1, per_page=10)
    
    # Delete a video
    client.video.delete(video_id)
```

### Emotion Detection

```python
# Detect emotions from an image
emotions = client.emotion.detect_from_image("selfie.jpg")
print(f"Detected emotions: {emotions}")

# Analyze text sentiment
text_analysis = client.emotion.detect_from_text(
    "I'm so excited about this new feature!"
)
print(f"Sentiment: {text_analysis['sentiment']}")

# Analyze video emotions
video_emotions = client.emotion.analyze_video_emotions(
    video_id="abc123",
    options={"timeline": True}
)

# Get available emotion categories
categories = client.emotion.get_emotion_categories()
```

### Face Analysis

```python
# Detect faces in an image
faces = client.face.detect_faces("group_photo.jpg")
print(f"Found {len(faces['faces'])} faces")

# Analyze face attributes
attributes = client.face.analyze_face_attributes("portrait.jpg")
print(f"Age: {attributes['age']}, Gender: {attributes['gender']}")

# Compare two faces
comparison = client.face.compare_faces("person1.jpg", "person2.jpg")
print(f"Similarity: {comparison['similarity']}")
print(f"Match: {comparison['is_match']}")

# Track faces in a video
tracking = client.face.track_faces_in_video("video123")
print(f"Unique faces: {tracking['unique_faces']}")
```

### Error Handling

```python
from imentiv import ImentivClient
from imentiv.exceptions import (
    ImentivAuthenticationError,
    ImentivRateLimitError,
    ImentivAPIError,
)

try:
    with ImentivClient(api_key="your-api-key") as client:
        result = client.video.upload("video.mp4")
        
except ImentivAuthenticationError:
    print("Invalid API key")
    
except ImentivRateLimitError:
    print("Rate limit exceeded, please wait")
    
except ImentivAPIError as e:
    print(f"API error: {e.message}")
    print(f"Status code: {e.status_code}")
```

### Advanced Configuration

```python
# Custom configuration
client = ImentivClient(
    api_key="your-api-key",
    base_url="https://api.imentiv.ai/v1",  # Custom API endpoint
    timeout=60,  # Request timeout in seconds
    max_retries=5,  # Maximum retry attempts
)
```

### Account Information

```python
# Get account details
account = client.get_account_info()
print(f"Credits remaining: {account['credits_remaining']}")
print(f"Plan: {account['plan']}")

# Get API version
version = client.get_api_version()
print(f"API version: {version['version']}")
```

## API Reference

### ImentivClient

Main client class for interacting with the Imentiv API.

**Methods:**
- `video` - Access video analysis endpoints
- `emotion` - Access emotion detection endpoints
- `face` - Access face analysis endpoints
- `get_account_info()` - Get account information
- `get_api_version()` - Get API version
- `close()` - Close the client session

### VideoAPI

Methods for video analysis:
- `upload(file_path)` - Upload a video file
- `analyze(video_id, options)` - Request video analysis
- `get_status(video_id)` - Get processing status
- `get_results(video_id)` - Get analysis results
- `list(page, per_page)` - List all videos
- `delete(video_id)` - Delete a video

### EmotionAPI

Methods for emotion detection:
- `detect_from_image(image_path)` - Detect emotions from an image
- `detect_from_text(text)` - Analyze text sentiment
- `analyze_video_emotions(video_id, options)` - Analyze video emotions
- `get_emotion_categories()` - Get available emotion types

### FaceAPI

Methods for face analysis:
- `detect_faces(image_path)` - Detect faces in an image
- `analyze_face_attributes(image_path)` - Analyze face attributes
- `compare_faces(image_path1, image_path2)` - Compare two faces
- `track_faces_in_video(video_id, options)` - Track faces in video

## Exception Hierarchy

```
ImentivError (base exception)
├── ImentivAPIError
├── ImentivAuthenticationError (401)
├── ImentivValidationError (400)
├── ImentivNotFoundError (404)
├── ImentivRateLimitError (429)
└── ImentivServerError (500+)
```

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/imentiv/imentiv-python-sdk.git
cd imentiv-python-sdk

#### Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver.

```bash
# Create a virtual environment
uv venv

# Activate the environment
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate   # On Windows

# Install in editable mode with dev dependencies
uv pip install -e ".[dev]"
```

#### Using pip

```bash
# Install in development mode
pip install -e ".[dev]"
```
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=imentiv --cov-report=html

# Run specific test file
pytest tests/test_client.py
```

### Code Quality

```bash
# Format code with black
black imentiv tests examples

# Lint with ruff
ruff check imentiv tests examples

# Type checking with mypy
mypy imentiv
```

## Examples

Check out the [examples](examples/) directory for more comprehensive examples:

- [basic_usage.py](examples/basic_usage.py) - Basic SDK usage
- [advanced_usage.py](examples/advanced_usage.py) - Advanced patterns and error handling

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- 📧 Email: support@imentiv.ai
- 🌐 Website: https://imentiv.ai
- 📚 API Documentation: https://imentiv.ai/apis/
- 🐛 Issues: https://github.com/imentiv/imentiv-python-sdk/issues

## Changelog

### Version 0.1.0 (Initial Release)

- ✅ Core client implementation
- ✅ Video analysis API support
- ✅ Emotion detection API support
- ✅ Face analysis API support
- ✅ Comprehensive error handling
- ✅ Retry logic and rate limiting
- ✅ Type hints and documentation
- ✅ Unit tests
- ✅ Usage examples