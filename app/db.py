from supabase import create_client
from .config import settings

class SupabaseClient:
    def __init__(self):
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise RuntimeError("Supabase credentials not set in environment")
        self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        self.table = settings.PROMPTS_TABLE

    def insert_prompt(self, record: dict):
        # expects record keys matching table columns
        res = self.client.table(self.table).insert(record).execute()
        # Note: Supabase client may not always have status_code attribute
        if hasattr(res, 'status_code') and res.status_code >= 400:
            raise RuntimeError(res.error or "insert failed")
        return res.data

    def get_prompts_for_user(self, user_id: str):
        res = self.client.table(self.table).select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        # Note: Supabase client may not always have status_code attribute
        if hasattr(res, 'status_code') and res.status_code >= 400:
            raise RuntimeError(res.error or "select failed")
        return res.data
