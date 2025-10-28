# API Usage Examples

This document shows how to use the refile-backend API with AI integration.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file with your credentials:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
MISTRAL_API_KEY=your_mistral_api_key
UPLOAD_DIR=user-uploads
```

3. Start the server:
```bash
python run.py
```

Or using uvicorn directly:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### 1. Upload File with AI Processing

**Endpoint:** `POST /api/upload`

**Headers:**
- `x-user-id`: Your user ID (required for authentication)

**Form Data:**
- `prompt`: Natural language description of what you want to do (e.g., "Extract audio from this video")
- `file`: The file to upload

**Example using curl:**
```bash
curl -X POST http://localhost:8000/api/upload \
  -H "x-user-id: user123" \
  -F "prompt=Extract audio from the video as MP3" \
  -F "file=@wedding_video.mp4"
```

**Example Response:**
```json
{
  "status": "ok",
  "file": {
    "id": "abc123-...",
    "original_filename": "wedding_video.mp4",
    "stored_filename": "abc123-....mp4",
    "content_type": "video/mp4",
    "path": "user-uploads/user123/abc123-....mp4"
  },
  "prompt_record": {...},
  "ai_response": {
    "linux_command": "ffmpeg -i wedding_video.mp4 -vn -acodec libmp3lame audio.mp3",
    "input_files": ["wedding_video.mp4"],
    "output_files": ["audio.mp3"],
    "description": "Extracts the audio track from wedding_video.mp4 and saves it as an MP3 file."
  }
}
```

### 2. Process Follow-up Request

**Endpoint:** `POST /api/process`

**Headers:**
- `x-user-id`: Your user ID

**Form Data:**
- `prompt`: Your follow-up request
- `uploaded_files`: JSON string of available filenames
- `previous_command`: Previous AI command (optional, for context)
- `previous_input_files`: Previous input files as JSON (optional)
- `previous_output_files`: Previous output files as JSON (optional)
- `previous_description`: Previous description (optional)

**Example using curl:**
```bash
curl -X POST http://localhost:8000/api/process \
  -H "x-user-id: user123" \
  -F "prompt=Convert that audio to WAV format" \
  -F "uploaded_files=[\"wedding_video.mp4\"]" \
  -F "previous_command=ffmpeg -i wedding_video.mp4 -vn -acodec libmp3lame audio.mp3" \
  -F "previous_input_files=[\"wedding_video.mp4\"]" \
  -F "previous_output_files=[\"audio.mp3\"]" \
  -F "previous_description=Extracts audio as MP3"
```

**Example Response:**
```json
{
  "status": "ok",
  "ai_response": {
    "linux_command": "ffmpeg -i audio.mp3 -acodec pcm_s16le audio.wav",
    "input_files": ["audio.mp3"],
    "output_files": ["audio.wav"],
    "description": "Converts the MP3 audio file to WAV format."
  }
}
```

### 3. List User Files

**Endpoint:** `GET /api/list/{user_id}`

**Headers:**
- `x-user-id`: Must match the user_id in the URL

**Example:**
```bash
curl http://localhost:8000/api/list/user123 \
  -H "x-user-id: user123"
```

### 4. Download File

**Endpoint:** `GET /api/download/{user_id}/{stored_filename}`

**Headers:**
- `x-user-id`: Must match the user_id in the URL

**Example:**
```bash
curl http://localhost:8000/api/download/user123/abc123-....mp4 \
  -H "x-user-id: user123" \
  --output downloaded_video.mp4
```

### 5. Health Check

**Endpoint:** `GET /api/health`

**Example:**
```bash
curl http://localhost:8000/api/health
```

## Python Client Example

```python
import requests

# Configuration
BASE_URL = "http://localhost:8000"
USER_ID = "user123"

# Upload a file with AI processing
def upload_and_process(file_path, prompt):
    with open(file_path, 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/api/upload",
            headers={"x-user-id": USER_ID},
            data={"prompt": prompt},
            files={"file": f}
        )
    return response.json()

# Follow-up request
def process_followup(prompt, uploaded_files, previous_result=None):
    data = {
        "prompt": prompt,
        "uploaded_files": str(uploaded_files)
    }
    
    if previous_result:
        ai_resp = previous_result['ai_response']
        data.update({
            "previous_command": ai_resp['linux_command'],
            "previous_input_files": str(ai_resp['input_files']),
            "previous_output_files": str(ai_resp['output_files']),
            "previous_description": ai_resp['description']
        })
    
    response = requests.post(
        f"{BASE_URL}/api/process",
        headers={"x-user-id": USER_ID},
        data=data
    )
    return response.json()

# Example usage
if __name__ == "__main__":
    # First request: upload and extract audio
    result1 = upload_and_process(
        "wedding_video.mp4",
        "Extract audio from the video as MP3"
    )
    print("AI Command:", result1['ai_response']['linux_command'])
    
    # Follow-up: convert to WAV
    result2 = process_followup(
        "Convert that audio to WAV format",
        ["wedding_video.mp4"],
        result1
    )
    print("Follow-up Command:", result2['ai_response']['linux_command'])
```

## Supported Operations

The AI agent can generate commands for:

### Video Operations (FFmpeg)
- Extract audio
- Trim/cut videos
- Compress videos
- Convert formats
- Resize videos
- Merge videos
- Remove audio
- Change playback speed
- Add watermarks
- Create GIFs
- Rotate videos
- Add subtitles

### Audio Operations (FFmpeg)
- Convert formats
- Trim audio
- Adjust volume
- Merge audio files
- Change bitrate
- Normalize audio
- Add fade effects
- Change playback speed

### Image Operations (ImageMagick)
- Resize images
- Convert formats
- Compress images
- Crop images
- Add watermarks
- Rotate images
- Apply grayscale
- Blur images
- Add text
- Create collages
- Remove backgrounds
- Generate thumbnails

### PDF Operations (Poppler/PDFtk)
- Merge PDFs
- Split pages
- Convert PDF to images
- Extract text
- Compress PDFs
- Rotate pages
- Remove pages
- Extract images
- Add/remove passwords
- Get metadata
- Flatten forms

### OCR Operations (Tesseract)
- Extract text from images
- OCR scanned PDFs
- Multi-language support

## Notes

- The AI generates **Linux commands** - you'll need FFmpeg, ImageMagick, etc. installed to run them
- Conversation context is maintained per user - follow-up requests understand previous commands
- File uploads are stored in user-specific folders for security
- Authentication uses `x-user-id` header (replace with JWT in production)
