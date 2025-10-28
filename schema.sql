-- Supabase/PostgreSQL schema for refile app

-- Create the prompts table
CREATE TABLE prompts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text NOT NULL,
  prompt text NOT NULL,
  original_filename text,
  stored_filename text NOT NULL,
  content_type text,
  created_at timestamptz DEFAULT now()
);

-- Create index on user_id for faster queries
CREATE INDEX idx_prompts_user_id ON prompts(user_id);

-- Create index on created_at for sorting
CREATE INDEX idx_prompts_created_at ON prompts(created_at DESC);

-- Optional: Add Row Level Security (RLS) policies
-- ALTER TABLE prompts ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own prompts
-- CREATE POLICY "Users can view their own prompts"
--   ON prompts FOR SELECT
--   USING (auth.uid()::text = user_id);

-- Policy: Users can insert their own prompts
-- CREATE POLICY "Users can insert their own prompts"
--   ON prompts FOR INSERT
--   WITH CHECK (auth.uid()::text = user_id);
