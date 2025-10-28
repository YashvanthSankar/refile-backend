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

def create_preset(self, preset_data: dict):
    """Create a new preset"""
    result = self.client.table('presets').insert(preset_data).execute()
    return result.data[0] if result.data else None

def list_presets(self, category=None, tag=None, search=None, user_id=None, limit=50, offset=0):
    """List presets with filters"""
    query = self.client.table('presets').select('*').eq('is_public', True)
    
    if category:
        query = query.eq('category', category)
    if tag:
        query = query.contains('tags', [tag])
    if search:
        query = query.or_(f'name.ilike.%{search}%,description.ilike.%{search}%')
    if user_id:
        query = query.eq('user_id', user_id)
    
    query = query.order('likes_count', desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    return result.data

def get_preset_by_id(self, preset_id: str):
    """Get a specific preset"""
    result = self.client.table('presets').select('*').eq('id', preset_id).single().execute()
    return result.data

def has_user_liked_preset(self, preset_id: str, user_id: str):
    """Check if user has liked a preset"""
    result = self.client.table('preset_likes').select('id').eq('preset_id', preset_id).eq('user_id', user_id).execute()
    return len(result.data) > 0

def toggle_preset_like(self, preset_id: str, user_id: str):
    """Toggle like on a preset"""
    has_liked = self.has_user_liked_preset(preset_id, user_id)
    
    if has_liked:
        # Unlike
        self.client.table('preset_likes').delete().eq('preset_id', preset_id).eq('user_id', user_id).execute()
        self.client.rpc('decrement_preset_likes', {'preset_id': preset_id}).execute()
        new_count = self.get_preset_by_id(preset_id)['likes_count']
        return {'liked': False, 'likes_count': new_count}
    else:
        # Like
        self.client.table('preset_likes').insert({'preset_id': preset_id, 'user_id': user_id}).execute()
        self.client.rpc('increment_preset_likes', {'preset_id': preset_id}).execute()
        new_count = self.get_preset_by_id(preset_id)['likes_count']
        return {'liked': True, 'likes_count': new_count}

def increment_preset_usage(self, preset_id: str):
    """Increment usage count"""
    self.client.rpc('increment_preset_usage', {'preset_id': preset_id}).execute()

def delete_preset(self, preset_id: str):
    """Delete a preset"""
    self.client.table('presets').delete().eq('id', preset_id).execute()