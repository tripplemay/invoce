"""IMAP 归集 ingest/sync 测试（S3 与队列已 mock，用假 fetcher 代替真实 IMAP）。"""

from email.message import EmailMessage

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.email_account import EmailAccount
from app.models.invoice import Invoice
from app.models.user import User
from app.services import email_sync


@pytest.fixture
def mock_storage(monkeypatch):
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("app.core.storage.upload_bytes", _noop)


async def _make_account(db_session: AsyncSession) -> EmailAccount:
    user = User(email="m@b.com", password_hash=hash_password("password123"))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    acct = EmailAccount(user_id=user.id, imap_user="123@qq.com", auth_code_enc=b"x")
    db_session.add(acct)
    await db_session.commit()
    await db_session.refresh(acct)
    return acct


def _invoice_email() -> bytes:
    m = EmailMessage()
    m["Subject"] = "电子发票"
    m["From"] = "billing@corp.com"
    m.set_content("请查收")
    m.add_attachment(b"%PDF-1.4", maintype="application", subtype="pdf", filename="a.pdf")
    return m.as_bytes()


def _spam_email() -> bytes:
    m = EmailMessage()
    m["Subject"] = "会议通知"
    m["From"] = "hr@corp.com"
    m.set_content("今天开会")
    return m.as_bytes()


async def test_ingest_invoice_email(db_session, mock_storage) -> None:
    acct = await _make_account(db_session)
    enq: list[str] = []

    async def enqueue(iid: str) -> None:
        enq.append(iid)

    status, count = await email_sync.ingest_email(db_session, acct, _invoice_email(), enqueue)
    assert status == "SUCCESS" and count == 1
    assert len(enq) == 1
    inv = (await db_session.scalars(select(Invoice))).first()
    assert inv.source == "email_auto" and inv.status == "processing"


async def test_ingest_ignores_non_invoice(db_session, mock_storage) -> None:
    acct = await _make_account(db_session)

    async def enqueue(iid: str) -> None:
        pass

    status, count = await email_sync.ingest_email(db_session, acct, _spam_email(), enqueue)
    assert status == "IGNORED" and count == 0
    total = await db_session.scalar(select(func.count()).select_from(Invoice))
    assert total == 0


async def test_sync_account_updates_uid(db_session, mock_storage) -> None:
    acct = await _make_account(db_session)
    enq: list[str] = []

    async def enqueue(iid: str) -> None:
        enq.append(iid)

    async def fake_fetcher(account):
        return [(10, _invoice_email()), (12, _spam_email())]

    total = await email_sync.sync_account(db_session, acct, enqueue, fetcher=fake_fetcher)
    assert total == 1  # 一封发票 + 一封被忽略
    await db_session.refresh(acct)
    assert acct.last_sync_uid == 12
