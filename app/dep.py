# app/dependencies.py
import httpx
from app.clients import SupabaseClient, TwilioClient, GroqClient, ElevenLabsClient, GoogleClient
from app.redis_manager import RedisManager
from app.config import settings
from typing import AsyncGenerator
from fastapi import Depends

async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Dependency for getting an httpx AsyncClient (managed by lifespan)."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client: #Added timeout
        yield client

async def get_supabase_client(http_client: httpx.AsyncClient = Depends(get_http_client)) -> SupabaseClient:
    """Dependency for getting a SupabaseClient (using the shared http_client)."""
    return SupabaseClient(http_client)

async def get_twilio_client() -> TwilioClient:
    return TwilioClient()

async def get_groq_client() -> GroqClient:
    return GroqClient()

async def get_elevenlabs_client() -> ElevenLabsClient:
    return ElevenLabsClient()

async def get_redis_client() -> RedisManager:
    return RedisManager.get_client()

async def get_google_client() -> GoogleClient:
    return GoogleClient()