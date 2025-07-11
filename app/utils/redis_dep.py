# app/dependencies/redis_dep.py

from fastapi import Depends
from app.utils.redis_client import RedisClient
from redis.asyncio.client import Redis as AsyncRedis

async def get_redis_client() -> AsyncRedis:
    return RedisClient.get_client()
