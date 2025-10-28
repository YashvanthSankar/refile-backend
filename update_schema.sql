-- Add AI-related columns to prompts table
-- Run this in your Supabase SQL Editor

ALTER TABLE prompts 
ADD COLUMN IF NOT EXISTS ai_command TEXT,
ADD COLUMN IF NOT EXISTS ai_response JSONB,
ADD COLUMN IF NOT EXISTS ai_processing_status TEXT DEFAULT 'pending';

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_prompts_user_id ON prompts(user_id);
CREATE INDEX IF NOT EXISTS idx_prompts_status ON prompts(ai_processing_status);

-- Update existing rows
UPDATE prompts SET ai_processing_status = 'pending' WHERE ai_processing_status IS NULL;

SELECT 'Schema updated successfully!' as message;
