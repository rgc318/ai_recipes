# app/dependencies/redis_dep.py

from app.infra.redis.redis_client import RedisClient
from redis.asyncio.client import Redis as AsyncRedis

async def get_redis_client() -> AsyncRedis:
    return RedisClient.get_client()
