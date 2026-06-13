"""ARQ 队列连接助手。"""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings


async def get_pool() -> ArqRedis:
    return await create_pool(RedisSettings.from_dsn(settings.redis_url))
