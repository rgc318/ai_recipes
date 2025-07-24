# app/infra/redis/redis_dep.py

from app.infra.redis.redis_factory import redis_factory
from app.infra.redis.base_redis_client import BaseRedisClient
from app.config import settings

def get_cache_client() -> BaseRedisClient:
    """
    依赖注入函数，提供一个带序列化功能的缓存客户端。
    """
    # 从工厂获取 'default' Redis 客户端的原始连接
    raw_client = redis_factory.get_client('default')
    # 获取对应的序列化配置
    serializer = settings.redis.clients.get('default').serializer
    # 用原始连接和配置来创建一个便利的封装器实例
    return BaseRedisClient(client=raw_client, serializer=serializer)

# 如果未来有 broker，可以这样创建
# def get_broker_client() -> aioredis.Redis:
#     return redis_factory.get_client('broker')
