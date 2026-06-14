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


def _inline_image_email(payload: bytes) -> bytes:
    """无附件、仅 HTML 内嵌 base64 图的发票邮件（用于校验附件优先 / 小图过滤）。"""
    import base64

    b64 = base64.b64encode(payload).decode()
    html = f'<html><body>发票<img src="data:image/png;base64,{b64}"/></body></html>'
    m = EmailMessage()
    m["Subject"] = "电子发票"
    m["From"] = "billing@corp.com"
    m.set_content("请查收发票")
    m.add_alternative(html, subtype="html")
    return m.as_bytes()


async def test_ingest_dedup_same_file(db_session, mock_storage) -> None:
    """同一封发票邮件重复 ingest：第二次靠 file_key 去重，不再新建发票行。"""
    acct = await _make_account(db_session)

    async def enqueue(iid: str) -> None:
        pass

    s1, c1 = await email_sync.ingest_email(db_session, acct, _invoice_email(), enqueue)
    s2, c2 = await email_sync.ingest_email(db_session, acct, _invoice_email(), enqueue)
    assert (s1, c1) == ("SUCCESS", 1)
    assert (s2, c2) == ("SUCCESS", 0)  # 第二次去重，0 新增
    total = await db_session.scalar(select(func.count()).select_from(Invoice))
    assert total == 1


async def test_ingest_drops_tiny_inline_image(db_session, mock_storage) -> None:
    """无附件 + 内嵌小图（logo/像素）应被过滤，不产生发票。"""
    acct = await _make_account(db_session)

    async def enqueue(iid: str) -> None:
        pass

    raw = _inline_image_email(b"\x89PNG\r\n" + b"x" * 200)  # < MIN_IMAGE_BYTES
    status, count = await email_sync.ingest_email(db_session, acct, raw, enqueue)
    assert (status, count) == ("SUCCESS", 0)
    total = await db_session.scalar(select(func.count()).select_from(Invoice))
    assert total == 0


async def test_ingest_keeps_large_inline_image(db_session, mock_storage) -> None:
    """无附件但有足够大的内嵌图（真实图片发票）时，回退提取并入库。"""
    acct = await _make_account(db_session)
    enq: list[str] = []

    async def enqueue(iid: str) -> None:
        enq.append(iid)

    raw = _inline_image_email(b"\x89PNG\r\n" + b"x" * (email_sync.MIN_IMAGE_BYTES + 100))
    status, count = await email_sync.ingest_email(db_session, acct, raw, enqueue)
    assert (status, count) == ("SUCCESS", 1)
    assert len(enq) == 1


def _meituan_email() -> bytes:
    """美团式邮件：真发票 PDF + 行程单 PDF（行程单应被剔除）。"""
    m = EmailMessage()
    m["Subject"] = "美团出行电子发票及行程报销单"
    m["From"] = "noreply@meituan.com"
    m.set_content("请查收")
    m.add_attachment(
        b"%PDF-invoice", maintype="application", subtype="pdf", filename="电子发票1.pdf"
    )
    m.add_attachment(b"%PDF-trip", maintype="application", subtype="pdf", filename="行程单.pdf")
    return m.as_bytes()


def _toll_zip_email() -> bytes:
    """通行费式邮件：发票在 zip 内（pdf/ 两张），外加汇总单噪音 PDF。"""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("pdf/1_inv.pdf", b"%PDF-A")
        z.writestr("pdf/2_inv.pdf", b"%PDF-B")
        z.writestr("ofd/1_inv.ofd", b"OFD")
    m = EmailMessage()
    m["Subject"] = "通行费电子发票"
    m["From"] = "noreply@toll.com"
    m.set_content("请查收")
    m.add_attachment(
        buf.getvalue(), maintype="application", subtype="zip", filename="通行费电子发票.zip"
    )
    m.add_attachment(
        b"%PDF-sum",
        maintype="application",
        subtype="pdf",
        filename="通行费电子票据汇总单(票据).pdf",
    )
    return m.as_bytes()


async def test_ingest_meituan_keeps_only_invoice(db_session, mock_storage) -> None:
    acct = await _make_account(db_session)
    enq: list[str] = []

    async def enqueue(iid: str) -> None:
        enq.append(iid)

    status, count = await email_sync.ingest_email(db_session, acct, _meituan_email(), enqueue)
    assert (status, count) == ("SUCCESS", 1)  # 行程单被剔除，只入真发票
    assert len(enq) == 1


async def test_ingest_toll_extracts_zip_invoices(db_session, mock_storage) -> None:
    acct = await _make_account(db_session)
    enq: list[str] = []

    async def enqueue(iid: str) -> None:
        enq.append(iid)

    status, count = await email_sync.ingest_email(db_session, acct, _toll_zip_email(), enqueue)
    assert (status, count) == ("SUCCESS", 2)  # zip 内 2 张发票；汇总单被剔除
    assert len(enq) == 2


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


async def test_sync_account_fetch_failure_holds_watermark(db_session, mock_storage) -> None:
    """高 UID 取信失败(raw 空)时，水位线只停在上一个成功 UID，不越过失败封。"""
    acct = await _make_account(db_session)

    async def enqueue(iid: str) -> None:
        pass

    async def fetcher(account):
        return [(10, _invoice_email()), (12, b"")]  # 12 取信失败

    total = await email_sync.sync_account(db_session, acct, enqueue, fetcher=fetcher)
    assert total == 1
    await db_session.refresh(acct)
    assert acct.last_sync_uid == 10  # 不越过失败的 12，下轮会重试


async def test_sync_account_low_failure_blocks_but_processes_higher(
    db_session, mock_storage
) -> None:
    """低 UID 失败应阻止水位线推进，但更高 UID 的发票仍被处理入库（不阻塞新发票）。"""
    acct = await _make_account(db_session)
    enq: list[str] = []

    async def enqueue(iid: str) -> None:
        enq.append(iid)

    async def fetcher(account):
        return [(10, b""), (12, _invoice_email())]  # 10 失败，12 成功

    total = await email_sync.sync_account(db_session, acct, enqueue, fetcher=fetcher)
    assert total == 1  # 12 仍入库
    assert len(enq) == 1
    await db_session.refresh(acct)
    assert not acct.last_sync_uid  # 水位线不越过失败的 10，保持初始
