"""ARQ Worker 配置。真实任务（AI 抽取/IMAP 轮询）在阶段4/5 接入。"""

from arq.connections import RedisSettings

from app.core.config import settings


async def heartbeat(ctx: dict) -> str:
    """占位任务：ARQ 要求至少注册一个 function，阶段4 前先放一个空操作。"""
    return "ok"


async def startup(ctx: dict) -> None:  # pragma: no cover
    pass


async def shutdown(ctx: dict) -> None:  # pragma: no cover
    pass


class WorkerSettings:
    # 阶段4 加入 AI 抽取任务；阶段5 加入 IMAP 轮询 cron
    functions = [heartbeat]
    cron_jobs: list = []
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
