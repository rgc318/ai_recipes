import redis.asyncio as redis
from redis.asyncio.client import Redis as AsyncRedis
from redis.exceptions import ConnectionError
from redis.asyncio.connection import ConnectionPool
from typing import Optional, Any, Callable, Union
import json
import pickle
from loguru import logger


class RedisClient:
    _client: Optional[AsyncRedis] = None
    _serializer: Callable = json.dumps
    _deserializer: Callable = json.loads

    @classmethod
    async def init(
        cls,
        redis_url: str,
        max_connections: int,
        socket_timeout: int,
        socket_connect_timeout: int,
        serializer: str = "json",
    ):
        try:
            pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=max_connections,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                retry_on_timeout=True,
            )
            cls._client = redis.Redis(connection_pool=pool)

            await cls._client.ping()
            logger.info("✅ Redis 已连接成功")

            if serializer == "json":
                cls._serializer = json.dumps
                cls._deserializer = json.loads
            elif serializer == "pickle":
                cls._serializer = pickle.dumps
                cls._deserializer = pickle.loads
            else:
                raise ValueError(f"不支持的序列化方式: {serializer}")

        except Exception as e:
            logger.error(f"❌ Redis 初始化失败: {e}")
            raise RuntimeError("无法连接 Redis") from e

    @classmethod
    def get_client(cls) -> AsyncRedis:
        if cls._client is None:
            raise RuntimeError("❌ Redis 未初始化")
        return cls._client

    @classmethod
    async def health_check(cls) -> bool:
        try:
            await cls.get_client().ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.close()
            await cls._client.connection_pool.disconnect()
            cls._client = None
            logger.info("🔌 Redis 连接已关闭")

    # ==================== 通用 KV ====================

    @classmethod
    async def set(cls, key: str, value: Any, ex: Optional[int] = None):
        try:
            await cls.get_client().set(name=key, value=value, ex=ex)
        except Exception as e:
            logger.error(f"Redis set 错误: {e}")

    @classmethod
    async def get(cls, key: str) -> Optional[str]:
        try:
            return await cls.get_client().get(name=key)
        except Exception as e:
            logger.error(f"Redis get 错误: {e}")
            return None

    @classmethod
    async def delete(cls, key: str):
        try:
            await cls.get_client().delete(key)
        except Exception as e:
            logger.error(f"Redis delete 错误: {e}")

    @classmethod
    async def exists(cls, key: str) -> bool:
        try:
            return await cls.get_client().exists(key) == 1
        except Exception as e:
            logger.error(f"Redis exists 错误: {e}")
            return False

    # ==================== 序列化支持 ====================

    @classmethod
    async def set_obj(cls, key: str, obj: Any, ex: int = 3600):
        try:
            data = cls._serializer(obj)
            await cls.set(key, data, ex=ex)
        except Exception as e:
            logger.error(f"Redis set_obj 错误: {e}")

    @classmethod
    async def get_obj(cls, key: str) -> Optional[Any]:
        val = await cls.get(key)
        try:
            return cls._deserializer(val) if val else None
        except Exception as e:
            logger.error(f"Redis get_obj 反序列化失败: {e}")
            return None

    # ==================== Pipeline ====================

    @classmethod
    async def pipeline(cls):
        return cls.get_client().pipeline()

    # ==================== Hash 支持 ====================

    @classmethod
    async def hset(cls, name: str, key: str, value: Any):
        await cls.get_client().hset(name, key, value)

    @classmethod
    async def hget(cls, name: str, key: str) -> Optional[str]:
        return await cls.get_client().hget(name, key)

    # ==================== Set 支持 ====================

    @classmethod
    async def sadd(cls, name: str, *values: Any):
        await cls.get_client().sadd(name, *values)

    @classmethod
    async def smembers(cls, name: str) -> set:
        return await cls.get_client().smembers(name)

    # ==================== List 支持 ====================

    @classmethod
    async def lpush(cls, name: str, *values: Any):
        await cls.get_client().lpush(name, *values)

    @classmethod
    async def lrange(cls, name: str, start: int = 0, end: int = -1):
        return await cls.get_client().lrange(name, start, end)

    # ==================== 分布式锁（简单版） ====================

    @classmethod
    async def acquire_lock(cls, key: str, timeout: int = 10) -> bool:
        return await cls.get_client().set(name=key, value="1", ex=timeout, nx=True)

    @classmethod
    async def release_lock(cls, key: str):
        await cls.delete(key)

    # ==================== 连接池状态 ====================

    @classmethod
    def get_pool_stats(cls) -> dict:
        pool = cls.get_client().connection_pool
        return {
            "in_use_connections": len(pool._in_use_connections),
            "available_connections": len(pool._available_connections),
        }
