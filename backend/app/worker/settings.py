"""ARQ Worker 配置。任务函数与定时任务在后续阶段接入。"""

from arq.connections import RedisSettings

from app.core.config import settings


async def startup(ctx: dict) -> None:  # pragma: no cover
    pass


async def shutdown(ctx: dict) -> None:  # pragma: no cover
    pass


class WorkerSettings:
    # 阶段4 加入 AI 抽取任务；阶段5 加入 IMAP 轮询 cron
    functions: list = []
    cron_jobs: list = []
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
