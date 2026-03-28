from fastapi import Depends
from redis.asyncio import Redis

from app.core.settings import Settings, get_settings

# Redis连接池全局实例


def get_cache(settings: Settings = Depends(get_settings)) -> Redis:
    """get Redis client with connection pooling and caching"""

    return Redis.from_url(
        url=settings.REDIS_URL,  # Redis连接URL
        password=settings.REDIS_PASSWORD,  # Redis密码
        encoding=settings.REDIS_ENCODING,  # Redis编码
        decode_responses=settings.REDIS_DECODE_RESPONSES,  # Redis解码响应
        max_connections=settings.REDIS_POOL_SIZE,  # Redis连接池大小
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,  # Redis套接字超时
        socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,  # Redis套接字连接超时
        health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL,  # Redis健康检查间隔 秒
    )
