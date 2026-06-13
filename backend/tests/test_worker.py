"""Worker 任务测试：extract_invoice 占位逻辑。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.invoice import Invoice
from app.models.user import User
from app.worker.settings import extract_invoice, heartbeat, shutdown, startup


async def test_heartbeat() -> None:
    assert await heartbeat({}) == "ok"


async def test_extract_invoice_marks_pending(db_session: AsyncSession) -> None:
    user = User(email="w@b.com", password_hash=hash_password("password123"))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    inv = Invoice(
        user_id=user.id,
        file_key="k",
        source="manual",
        status="processing",
        reimbursement_status="unreimbursed",
    )
    db_session.add(inv)
    await db_session.commit()
    await db_session.refresh(inv)

    ctx: dict = {}
    await startup(ctx)
    try:
        assert await extract_invoice(ctx, str(inv.id)) == "ok"
        assert await extract_invoice(ctx, "00000000-0000-0000-0000-000000000000") == "not found"
    finally:
        await shutdown(ctx)

    await db_session.refresh(inv)
    assert inv.status == "pending"
