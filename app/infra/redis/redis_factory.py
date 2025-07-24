# 文件路径: app/infra/redis/redis_factory.py  (建议新建此文件)

import redis.asyncio as aioredis
from typing import Dict
from loguru import logger

from app.config import settings # 假设您的配置可以这样导入

class RedisFactory:
    """
    一个管理所有 Redis 客户端连接的工厂。
    它在应用启动时被实例化一次，并作为单例存在。
    """
    def __init__(self):
        self._clients: Dict[str, aioredis.Redis] = {}
        logger.info("Initializing RedisFactory...")

    async def init_clients(self):
        """
        根据配置文件，初始化所有的 Redis 客户端。
        这个方法应该在应用启动的 lifespan 事件中被调用。
        """
        for name, config in settings.redis.clients.items():
            try:
                pool = aioredis.ConnectionPool.from_url(
                    config._final_url,
                    max_connections=config.max_connections,
                    socket_timeout=config.socket_timeout,
                    socket_connect_timeout=config.socket_connect_timeout,
                    retry_on_timeout=True,
                )
                client = aioredis.Redis(connection_pool=pool)
                await client.ping()
                self._clients[name] = client
                logger.info(f"✅ Redis client '{name}' connected successfully.")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Redis client '{name}': {e}")
                raise RuntimeError(f"Could not connect to Redis client '{name}'") from e
        logger.info("RedisFactory initialized all clients.")

    def get_client(self, name: str = 'default') -> aioredis.Redis:
        """
        按名称获取一个已初始化的 Redis 客户端实例。
        """
        client = self._clients.get(name)
        if not client:
            raise RuntimeError(f"❌ Redis client '{name}' is not initialized or configured.")
        return client

    async def close_clients(self):
        """
        关闭所有 Redis 客户端连接。
        这个方法应该在应用关闭的 lifespan 事件中被调用。
        """
        for name, client in self._clients.items():
            await client.close()
            await client.connection_pool.disconnect()
            logger.info(f"🔌 Redis client '{name}' connection closed.")
        self._clients.clear()

    async def health_check(self, name: str = 'default') -> bool:
        """
        对指定名称的 Redis 客户端进行健康检查。
        """
        try:
            client = self.get_client(name)
            await client.ping()
            logger.info(f"Redis client '{name}' health check successful.")
            return True
        except Exception as e:
            logger.error(f"Redis client '{name}' health check failed: {e}")
            return False

    def get_pool_stats(self, name: str = 'default') -> dict:
        """
        获取指定名称的 Redis 客户端的连接池状态。
        """
        try:
            client = self.get_client(name)
            pool = client.connection_pool
            return {
                "max_connections": pool.max_connections,
                "in_use_connections": len(pool._in_use_connections),
                "available_connections": len(pool._available_connections),
            }
        except Exception as e:
            logger.error(f"Failed to get pool stats for Redis client '{name}': {e}")
            return {}
# 创建一个全局的工厂实例，以便在整个应用中共享
redis_factory = RedisFactory()