from supabase import create_client
from .config import settings
from datetime import datetime

class SupabaseClient:
    def __init__(self):
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise RuntimeError("Supabase credentials not set in environment")
        self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        self.table = settings.PROMPTS_TABLE

    def insert_prompt(self, record: dict):
        """Insert a new prompt record into the database"""
        # expects record keys matching table columns
        res = self.client.table(self.table).insert(record).execute()
        # Note: Supabase client may not always have status_code attribute
        if hasattr(res, 'status_code') and res.status_code >= 400:
            raise RuntimeError(res.error or "insert failed")
        return res.data[0] if res.data else None

    def get_prompts_for_user(self, user_id: str):
        """Get all prompts for a specific user"""
        res = self.client.table(self.table).select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        # Note: Supabase client may not always have status_code attribute
        if hasattr(res, 'status_code') and res.status_code >= 400:
            raise RuntimeError(res.error or "select failed")
        return res.data
    
    def get_prompt_by_id(self, prompt_id: str):
        """Get a specific prompt by ID"""
        res = self.client.table(self.table).select("*").eq("id", prompt_id).execute()
        if hasattr(res, 'status_code') and res.status_code >= 400:
            raise RuntimeError(res.error or "select failed")
        return res.data[0] if res.data else None
    
    def update_prompt_status(self, prompt_id: str, status: str):
        """Update the processing status of a prompt"""
        data = {
            "ai_processing_status": status,
            "processed_at": datetime.utcnow().isoformat() if status in ["completed", "failed"] else None
        }
        res = self.client.table(self.table).update(data).eq("id", prompt_id).execute()
        if hasattr(res, 'status_code') and res.status_code >= 400:
            raise RuntimeError(res.error or "update failed")
        return res.data[0] if res.data else None
    
    def update_prompt_ai_response(self, prompt_id: str, ai_response: str = None, 
                                  ai_command: str = None, status: str = "completed",
                                  error_message: str = None):
        """Update prompt with AI response and command"""
        data = {
            "ai_response": ai_response,
            "ai_command": ai_command,
            "ai_processing_status": status,
            "processed_at": datetime.utcnow().isoformat(),
        }
        
        if error_message:
            data["error_message"] = error_message
        
        res = self.client.table(self.table).update(data).eq("id", prompt_id).execute()
        if hasattr(res, 'status_code') and res.status_code >= 400:
            raise RuntimeError(res.error or "update failed")
        return res.data[0] if res.data else None

