# 文件路径: app/utils/redis_client.py (可以重命名或替换您原来的文件)

import json
import pickle
from typing import Optional, Any, Callable, Set, List as PyList
from redis.asyncio.client import Redis as AsyncRedis
from loguru import logger


class BaseRedisClient:
    """
    一个 Redis 命令的封装器，提供序列化、分布式锁等便利功能。
    它不管理连接，而是接收一个已经建立好的 client 实例。
    """

    def __init__(self, client: AsyncRedis, serializer: str = "json"):
        self._client = client
        if serializer == "json":
            self._serializer = json.dumps
            self._deserializer = json.loads
        elif serializer == "pickle":
            self._serializer = pickle.dumps
            self._deserializer = pickle.loads
        else:
            raise ValueError(f"Unsupported serializer: {serializer}")

    async def set_obj(self, key: str, obj: Any, ex: int = 3600):
        try:
            data = self._serializer(obj)
            await self._client.set(name=key, value=data, ex=ex)
        except Exception as e:
            logger.error(f"Redis set_obj error: {e}")

    async def get_obj(self, key: str) -> Optional[Any]:
        val = await self._client.get(name=key)
        try:
            return self._deserializer(val) if val else None
        except (json.JSONDecodeError, pickle.UnpicklingError, TypeError) as e:
            logger.warning(f"Redis get_obj deserialization failed for key '{key}': {e}")
            return None
        except Exception as e:
            logger.error(f"Redis get_obj error for key '{key}': {e}")
            return None

    async def set(self, key: str, value: Any, ex: Optional[int] = None):
        return await self._client.set(name=key, value=value, ex=ex)

    async def get(self, key: str) -> Optional[str]:
        return await self._client.get(name=key)

    async def delete(self, *keys: str):
        return await self._client.delete(*keys)

    async def exists(self, *keys: str) -> bool:
        return await self._client.exists(*keys) > 0

    # ==================== Pipeline (已从旧版补全) ====================
    async def pipeline(self, transaction: bool = True):
        return self._client.pipeline(transaction=transaction)

    # ==================== Hash 支持 (已从旧版补全) ====================
    async def hset(self, name: str, key: str, value: Any):
        return await self._client.hset(name, key, value)

    async def hget(self, name: str, key: str) -> Optional[str]:
        return await self._client.hget(name, key)

    # ==================== Set 支持 (已从旧版补全) ====================
    async def sadd(self, name: str, *values: Any):
        return await self._client.sadd(name, *values)

    async def smembers(self, name: str) -> Set:
        return await self._client.smembers(name)

    # ==================== List 支持 (已从旧版补全) ====================
    async def lpush(self, name: str, *values: Any):
        return await self._client.lpush(name, *values)

    async def lrange(self, name: str, start: int = 0, end: int = -1) -> PyList:
        return await self._client.lrange(name, start, end)

    # ==================== 分布式锁 (已从旧版补全) ====================

    # --- 您原来的其他所有便利方法都可以移到这里 ---
    # 例如：
    async def acquire_lock(self, key: str, timeout: int = 10) -> bool:
        return await self._client.set(name=key, value="1", ex=timeout, nx=True)

    async def release_lock(self, key: str):
        await self._client.delete(key)

    # 您还可以直接访问原始客户端来执行其他命令
    @property
    def raw_client(self) -> AsyncRedis:
        return self._client