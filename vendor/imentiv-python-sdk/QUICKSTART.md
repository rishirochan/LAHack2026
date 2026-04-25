# Quick Start Guide - Imentiv Python SDK

Get started with the Imentiv Python SDK in 5 minutes!

## Installation

```bash
pip install imentiv
```

## Basic Usage

### 1. Initialize the Client

```python
from imentiv import ImentivClient

# Option 1: Pass API key directly
client = ImentivClient(api_key="your-api-key")

# Option 2: Use environment variable
# export IMENTIV_API_KEY="your-api-key"
client = ImentivClient()

# Option 3: Use context manager (recommended)
with ImentivClient(api_key="your-api-key") as client:
    # Your code here
    pass
```

### 2. Video Analysis

```python
# Upload a video
result = client.video.upload("path/to/video.mp4")
video_id = result["video_id"]

# Request analysis
analysis = client.video.analyze(video_id, options={
    "detect_emotions": True,
    "detect_faces": True
})

# Check status
status = client.video.get_status(video_id)

# Get results when ready
if status["status"] == "completed":
    results = client.video.get_results(video_id)
    print(results)
```

### 3. Emotion Detection

```python
# From an image
emotions = client.emotion.detect_from_image("photo.jpg")
print(emotions)

# From text
sentiment = client.emotion.detect_from_text("I love this!")
print(sentiment)
```

### 4. Face Detection

```python
# Detect faces
faces = client.face.detect_faces("group_photo.jpg")
print(f"Found {len(faces['faces'])} faces")

# Analyze face attributes
attributes = client.face.analyze_face_attributes("portrait.jpg")
print(attributes)

# Compare two faces
comparison = client.face.compare_faces("image1.jpg", "image2.jpg")
print(f"Similarity: {comparison['similarity']}")
```

## Error Handling

```python
from imentiv import ImentivClient
from imentiv.exceptions import ImentivAPIError, ImentivAuthenticationError

try:
    with ImentivClient(api_key="your-api-key") as client:
        result = client.video.upload("video.mp4")
except ImentivAuthenticationError:
    print("Invalid API key")
except ImentivAPIError as e:
    print(f"API error: {e.message}")
```

## More Examples

Check out the [examples](examples/) directory for more comprehensive examples:
- [basic_usage.py](examples/basic_usage.py) - Basic functionality
- [advanced_usage.py](examples/advanced_usage.py) - Advanced patterns

## Next Steps

- Read the full [README](README.md) for detailed documentation
- Check the [API Reference](README.md#api-reference) for all available methods
- Visit [imentiv.ai](https://imentiv.ai/apis/) for API documentation

## Need Help?

- 📧 Email: support@imentiv.ai
- 🐛 Issues: https://github.com/imentiv/imentiv-python-sdk/issues
