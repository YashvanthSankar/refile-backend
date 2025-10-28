refile-backend

FastAPI backend for the refile app. Handles user file uploads, stores files in user-specific folders, records prompts in Supabase, and serves files back to the frontend.

Quick start

1. Create a virtualenv and install dependencies:

   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

2. Copy `.env.example` to `.env` and fill in Supabase credentials.

3. Run the app with uvicorn:

   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

API endpoints

- POST /api/upload
  Form fields: user_id (string), prompt (string), file (file)
  Returns JSON with stored file metadata and prompt DB record.

- GET /api/list/{user_id}
  Returns a list of prompt records for the user.

- GET /api/download/{user_id}/{stored_filename}
  Download a stored file.

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

Notes

- This backend intentionally does not run AI workflows. It stores files and prompts and provides a simple API to retrieve them. AI processing can be added later by polling the prompts table or using webhooks.
