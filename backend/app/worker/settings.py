"""ARQ Worker 配置：DB 会话注入 ctx；extract_invoice 任务（AI 抽取）。"""

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.services.email_sync import sync_all
from app.services.extraction import run_extraction


async def startup(ctx: dict) -> None:
    engine = create_async_engine(settings.database_url)
    ctx["engine"] = engine
    ctx["sessionmaker"] = async_sessionmaker(engine, expire_on_commit=False)


async def shutdown(ctx: dict) -> None:
    await ctx["engine"].dispose()


async def heartbeat(ctx: dict) -> str:
    """占位任务，保证 ARQ 至少一个 function。"""
    return "ok"


async def extract_invoice(ctx: dict, invoice_id: str) -> str:
    """AI 抽取任务：下载原件 → 多模态抽取 → 落库（pending/failed）。"""
    maker = ctx["sessionmaker"]
    async with maker() as session:
        await run_extraction(session, invoice_id)
    return "ok"


class WorkerSettings:
    functions = [heartbeat, extract_invoice]
    # 每 30 分钟轮询所有启用的邮箱（PRD 15-30 分钟）
    cron_jobs = [cron(sync_all, minute={0, 30}, run_at_startup=False)]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    # 限制并发抽取数：AIGC 网关对突发并发敏感（会以 402/429 限流），
    # 低并发 + ai 层退避重试 = 既不打爆网关又能在偶发限流时自愈。
    max_jobs = 4
    on_startup = startup
    on_shutdown = shutdown
