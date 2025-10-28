refile-backend

FastAPI backend for the refile app. Handles user file uploads, stores files in user-specific folders, records prompts in Supabase, and uses AI to generate media processing commands. Integrated with LangChain and Mistral AI for intelligent command generation.

Quick start

1. Create a virtualenv and install dependencies:

   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt

2. Copy `.env.example` to `.env` and fill in your credentials:
   - Supabase URL and API key
   - Mistral AI API key
   - Upload directory path (optional)

3. Run the app with uvicorn:

   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

API endpoints

- POST /api/upload
  Form fields: prompt (string), file (file)
  Headers: x-user-id (string) - for authentication
  Returns JSON with stored file metadata, prompt DB record, and AI-generated command.
  
  Example AI response:
  ```json
  {
    "ai_response": {
      "linux_command": "ffmpeg -i wedding_video.mp4 -vn -acodec libmp3lame audio.mp3",
      "input_files": ["wedding_video.mp4"],
      "output_files": ["audio.mp3"],
      "description": "Extracts audio track and saves as MP3"
    }
  }
  ```

- POST /api/process
  Form fields: prompt (string), uploaded_files (JSON string), previous_* fields for conversation
  Headers: x-user-id (string) - for authentication
  Returns AI-generated command for follow-up requests without file upload.
  
  Use this for conversational follow-ups like:
  - "Convert that audio to WAV format"
  - "Compress the video to 720p"

- GET /api/list/{user_id}
  Headers: x-user-id (string) - must match user_id in path
  Returns a list of prompt records for the user.

- GET /api/download/{user_id}/{stored_filename}
  Headers: x-user-id (string) - must match user_id in path
  Download a stored file.

- GET /api/health
  Health check endpoint.

Database (Supabase)

Create a table named `prompts` (or set PROMPTS_TABLE) with columns:

- id: uuid (primary key)
- user_id: text
- prompt: text
- original_filename: text
- stored_filename: text
- content_type: text
- created_at: timestamptz

Example SQL (Postgres):

CREATE TABLE prompts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text NOT NULL,
  prompt text NOT NULL,
  original_filename text,
  stored_filename text NOT NULL,
  content_type text,
  created_at timestamptz DEFAULT now()
);

AI Agent Features

The integrated AI agent can generate commands for:
- **Video**: Extract audio, compress, trim, resize, add watermarks, create GIFs
- **Audio**: Convert formats, adjust volume, merge, normalize, change speed
- **Images**: Resize, convert, compress, crop, watermark, apply effects
- **PDFs**: Merge, split, compress, extract text/images, add passwords
- **OCR**: Extract text from images and scanned PDFs

The agent maintains conversation context per user, allowing natural follow-up requests.

Notes

- Authentication uses x-user-id header (placeholder for JWT in production)
- Users can only access their own files (enforced by security middleware)
- AI processing is fault-tolerant - upload succeeds even if AI fails
- Conversation history is maintained per user using LangGraph checkpoints
