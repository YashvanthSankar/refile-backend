from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str = "http://localhost:54321"  # Default for local testing
    SUPABASE_KEY: str = "your_key_here"  # Default for local testing
    MISTRAL_API_KEY: str = ""  # Optional - Mistral API key
    GROQ_API_KEY: str  # Required - Groq API key for AI agent
    UPLOAD_DIR: str = "user_uploads"
    # optional: table name for prompts
    PROMPTS_TABLE: str = "prompts"

    class Config:
        env_file = ".env"

settings = Settings()
