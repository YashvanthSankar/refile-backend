from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    UPLOAD_DIR: str = "user-uploads"
    # optional: table name for prompts
    PROMPTS_TABLE: str = "prompts"

    class Config:
        env_file = ".env"

settings = Settings()
