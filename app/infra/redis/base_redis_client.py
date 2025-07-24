# 文件路径: app/utils/redis_client.py (可以重命名或替换您原来的文件)

import json
import pickle
from typing import Optional, Any, Callable
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
        except Exception as e:
            logger.error(f"Redis get_obj deserialization failed: {e}")
            return None

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