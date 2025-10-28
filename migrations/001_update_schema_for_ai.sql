-- Migration: Add AI processing columns to prompts table
-- Run this in your Supabase SQL Editor

-- Add new columns for AI processing
ALTER TABLE prompts 
ADD COLUMN IF NOT EXISTS ai_response text,
ADD COLUMN IF NOT EXISTS ai_command text,
ADD COLUMN IF NOT EXISTS ai_processing_status text DEFAULT 'completed',
ADD COLUMN IF NOT EXISTS processed_at timestamptz,
ADD COLUMN IF NOT EXISTS error_message text;

-- Change user_id from int4 to text (if needed)
-- First check if column exists and is int4
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'prompts' 
        AND column_name = 'user_id' 
        AND data_type = 'integer'
    ) THEN
        ALTER TABLE prompts ALTER COLUMN user_id TYPE text USING user_id::text;
    END IF;
END $$;

-- Add index for processing status
CREATE INDEX IF NOT EXISTS idx_prompts_status ON prompts(ai_processing_status);

-- Update existing records to have 'completed' status
UPDATE prompts SET ai_processing_status = 'completed' WHERE ai_processing_status IS NULL;
