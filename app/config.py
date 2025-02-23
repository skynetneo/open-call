# app/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    GROQ_API_KEY: str
    ELEVENLABS_API_KEY: str
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_NUMBER: str
    VOICE_ID: str
    GOOGLE_API_KEY: str
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_BUCKET: str
    WHISPER_API_URL: str = "http://127.0.0.1:9000/v1/audio/transcriptions"  # Default
    REDIS_URL: str = "redis://localhost:6379/0"  # Default
    GROQ_MODEL: str = "llama3-70b-8192"  # Default
    ELEVENLABS_MODEL: str = "eleven_turbo_v2"  # Default
    ELEVENLABS_API_BASE_URL: str = "https://api.elevenlabs.io/v1"  # Elevenlabs URL
    GOOGLE_MODEL: str = "gemini-1.0-pro"  # Default.  Changed to a valid model name.

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding='utf-8')

settings = Settings()