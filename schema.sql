-- Supabase/PostgreSQL schema for refile app

-- Create the prompts table
CREATE TABLE prompts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text NOT NULL,
  prompt text NOT NULL,
  original_filename text,
  stored_filename text NOT NULL,
  content_type text,
  ai_response text,
  ai_command text,
  ai_processing_status text DEFAULT 'completed',
  processed_at timestamptz,
  error_message text,
  created_at timestamptz DEFAULT now()
);

-- Create index on user_id for faster queries
CREATE INDEX idx_prompts_user_id ON prompts(user_id);

-- Create index on created_at for sorting
CREATE INDEX idx_prompts_created_at ON prompts(created_at DESC);

-- Create index on processing status for querying pending jobs
CREATE INDEX idx_prompts_status ON prompts(ai_processing_status);
