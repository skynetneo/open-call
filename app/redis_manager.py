# app/redis_manager.py
import aioredis
import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class RedisManager:
    """Handles Redis connection and provides helper functions."""

    _client = None

    @classmethod
    async def initialize(cls):
        if cls._client is None:
            cls._client = aioredis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            logger.info("Redis connection initialized.")

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.close()
            cls._client = None
            logger.info("Redis connection closed.")

    @classmethod
    def get_client(cls) -> aioredis.Redis:
        if cls._client is None:
            raise Exception("Redis client not initialized. Call RedisManager.initialize() first.")
        return cls._client

    @classmethod
    async def hset(cls, key: str, mapping: dict):
        """Store a hash in Redis."""
        try:
            await cls._client.hset(key, mapping=mapping)
        except Exception as e:
            logger.error(f"Redis error storing hash at {key}: {e}")
            raise

    @classmethod
    async def hgetall(cls, key: str) -> dict:
        """Retrieve a hash from Redis."""
        try:
            return await cls._client.hgetall(key)
        except Exception as e:
            logger.error(f"Redis error retrieving hash from {key}: {e}")
            return {}  # Return empty dict on error

    @classmethod
    async def hget(cls, key: str, field: str):
        """Retrieve a field from hash in Redis."""
        try:
            return await cls._client.hget(key, field)
        except Exception as e:
            logger.error(f"Redis error retrieving field {field} from {key}: {e}")
            return {}

    @classmethod
    async def expire(cls, key: str, time: int):
        """Set expire in Redis."""
        try:
            return await cls._client.expire(key, time)
        except Exception as e:
            logger.error(f"Redis error setting expire on {key}: {e}")
            return {}

    @classmethod
    async def delete(cls, key: str):
        """Delete from Redis."""
        try:
            await cls._client.delete(key)
        except Exception as e:
            logger.error(f"Redis error deleting key {key}: {e}")
            raise