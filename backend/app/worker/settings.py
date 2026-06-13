"""ARQ Worker 配置：DB 会话注入 ctx；extract_invoice 任务（阶段4 接入真实 AI）。"""

import uuid

from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.enums import InvoiceStatus
from app.models.invoice import Invoice


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
    """AI 抽取任务。阶段4 替换为真实多模态抽取；当前占位：标记为待校对。"""
    maker = ctx["sessionmaker"]
    async with maker() as session:
        inv = await session.get(Invoice, uuid.UUID(invoice_id))
        if inv is None:
            return "not found"
        inv.status = InvoiceStatus.PENDING.value
        await session.commit()
    return "ok"


class WorkerSettings:
    functions = [heartbeat, extract_invoice]
    cron_jobs: list = []
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
