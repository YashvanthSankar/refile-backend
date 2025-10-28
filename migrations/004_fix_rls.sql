-- Fix for Row-Level Security (RLS) Issue
-- Run this in Supabase SQL Editor

-- Option 1: Disable RLS (Simple, for development only)
ALTER TABLE prompts DISABLE ROW LEVEL SECURITY;

-- Option 2: Enable RLS with proper policies (Recommended for production)
-- Uncomment the lines below if you want proper RLS setup:

/*
ALTER TABLE prompts ENABLE ROW LEVEL SECURITY;

-- Policy: Allow service role to insert (for API inserts)
CREATE POLICY "Allow service role full access"
ON prompts
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Policy: Allow authenticated users to insert their own data
CREATE POLICY "Users can insert their own data"
ON prompts
FOR INSERT
TO authenticated
WITH CHECK (true);  -- Or: WITH CHECK (auth.uid()::text = user_id)

-- Policy: Users can read their own data
CREATE POLICY "Users can view their own data"
ON prompts
FOR SELECT
TO authenticated
USING (true);  -- Or: USING (auth.uid()::text = user_id)

-- Policy: Allow anon role to insert (if using anon key from frontend)
CREATE POLICY "Allow anonymous inserts"
ON prompts
FOR INSERT
TO anon
WITH CHECK (true);

-- Policy: Allow anon role to select
CREATE POLICY "Allow anonymous selects"
ON prompts
FOR SELECT
TO anon
USING (true);
*/
