"""报销单一键发送测试（SMTP/队列/存储已 mock，不发真实邮件）。"""

import uuid

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.models.export_email_send import ExportEmailSend
from app.models.export_task import ExportTask
from app.services.export_runner import run_export_task
from app.services.export_sender import create_send_record, run_send_task


class FakePool:
    def __init__(self) -> None:
        self.jobs: list[tuple] = []

    async def enqueue_job(self, name, *args):
        self.jobs.append((name, args))

    async def aclose(self):
        pass


@pytest.fixture
def fake_pool(monkeypatch):
    pool = FakePool()

    async def _get():
        return pool

    monkeypatch.setattr("app.api.export_tasks.get_pool", _get)
    return pool


@pytest.fixture
def mock_io(monkeypatch):
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("app.core.storage.upload_bytes", _noop)
    monkeypatch.setattr("app.api.invoices.enqueue_extract", _noop)


@pytest.fixture
def outbound_on(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")


async def _make_invoice(auth_client: AsyncClient) -> str:
    up = await auth_client.post(
        "/invoices/upload", files={"files": ("a.pdf", b"%PDF-1.4", "application/pdf")}
    )
    inv = up.json()[0]
    await auth_client.patch(
        f"/invoices/{inv['id']}",
        json={
            "invoice_number": "E1",
            "issue_date": "2026-05-01",
            "seller_name": "阿里云/计算",
            "total_amount": "100.00",
        },
    )
    return inv["id"]


async def _completed_task(auth_client: AsyncClient, db_session) -> str:
    """建一个发票 → 导出任务 → 跑完打包（mock IO），返回已完成任务 id。"""
    iid = await _make_invoice(auth_client)
    t = (await auth_client.post("/export-tasks", json={"invoice_ids": [iid]})).json()

    async def _loader(key: str) -> bytes:
        return b"%PDF-1.4 file"

    async def _uploader(key: str, data: bytes, ctype: str) -> None:
        return None

    await run_export_task(db_session, uuid.UUID(t["id"]), file_loader=_loader, uploader=_uploader)
    return t["id"]


# ---------------- API 层 ----------------


async def test_send_requires_completed_task_409(
    auth_client: AsyncClient, mock_io, fake_pool, outbound_on
) -> None:
    iid = await _make_invoice(auth_client)
    t = (await auth_client.post("/export-tasks", json={"invoice_ids": [iid]})).json()
    r = await auth_client.post(f"/export-tasks/{t['id']}/send", json={"emails": ["x@y.com"]})
    assert r.status_code == 409
    assert [j for j in fake_pool.jobs if j[0] == "send_export_email"] == []


async def test_send_creates_record_and_enqueues(
    auth_client: AsyncClient, db_session, mock_io, fake_pool, outbound_on
) -> None:
    tid = await _completed_task(auth_client, db_session)
    c = (await auth_client.post("/contacts", json={"name": "财务", "email": "fin@corp.com"})).json()

    r = await auth_client.post(
        f"/export-tasks/{tid}/send",
        json={"contact_ids": [c["id"]], "emails": ["extra@corp.com"], "note": "本月报销"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert set(body["to_addresses"]) == {"fin@corp.com", "extra@corp.com"}
    assert body["note"] == "本月报销"
    # 入队 send_export_email（忽略建任务时的 run_export）
    send_jobs = [j for j in fake_pool.jobs if j[0] == "send_export_email"]
    assert len(send_jobs) == 1
    assert send_jobs[0][1] == (body["id"],)


async def test_send_dedupes_recipients(
    auth_client: AsyncClient, db_session, mock_io, fake_pool, outbound_on
) -> None:
    tid = await _completed_task(auth_client, db_session)
    c = (await auth_client.post("/contacts", json={"name": "财务", "email": "fin@corp.com"})).json()
    r = await auth_client.post(
        f"/export-tasks/{tid}/send",
        json={"contact_ids": [c["id"]], "emails": ["FIN@corp.com"]},
    )
    assert r.status_code == 201
    assert r.json()["to_addresses"] == ["fin@corp.com"]


async def test_send_no_recipient_field_422(
    auth_client: AsyncClient, db_session, mock_io, fake_pool, outbound_on
) -> None:
    tid = await _completed_task(auth_client, db_session)
    r = await auth_client.post(f"/export-tasks/{tid}/send", json={})
    assert r.status_code == 422


async def test_send_unresolvable_contacts_400(
    auth_client: AsyncClient, db_session, mock_io, fake_pool, outbound_on
) -> None:
    tid = await _completed_task(auth_client, db_session)
    # 只给了别人的/不存在的 contact_id，无临时邮箱 → 解析为空 → 400
    r = await auth_client.post(
        f"/export-tasks/{tid}/send", json={"contact_ids": [str(uuid.uuid4())]}
    )
    assert r.status_code == 400
    assert [j for j in fake_pool.jobs if j[0] == "send_export_email"] == []


async def test_send_disabled_503(
    auth_client: AsyncClient, db_session, mock_io, fake_pool, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "smtp_host", "")
    tid = await _completed_task(auth_client, db_session)
    r = await auth_client.post(f"/export-tasks/{tid}/send", json={"emails": ["x@y.com"]})
    assert r.status_code == 503


async def test_send_other_users_task_404(
    auth_client: AsyncClient, client: AsyncClient, db_session, mock_io, fake_pool, outbound_on
) -> None:
    tid = await _completed_task(auth_client, db_session)
    reg = await client.post(
        "/auth/register", json={"email": "other@test.com", "password": "password123"}
    )
    other = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    r = await client.post(f"/export-tasks/{tid}/send", json={"emails": ["x@y.com"]}, headers=other)
    assert r.status_code == 404


async def test_list_sends(
    auth_client: AsyncClient, db_session, mock_io, fake_pool, outbound_on
) -> None:
    tid = await _completed_task(auth_client, db_session)
    await auth_client.post(f"/export-tasks/{tid}/send", json={"emails": ["a@y.com"]})
    r = await auth_client.get(f"/export-tasks/{tid}/sends")
    assert r.status_code == 200
    sends = r.json()
    assert len(sends) == 1 and sends[0]["to_addresses"] == ["a@y.com"]


# ---------------- 服务层（投递） ----------------


async def _make_send_record(auth_client, db_session) -> ExportEmailSend:
    tid = await _completed_task(auth_client, db_session)
    task = await db_session.get(ExportTask, uuid.UUID(tid))
    rec = await create_send_record(db_session, task.user_id, task, [], ["proc@corp.com"], "请处理")
    return rec


async def test_run_send_small_attaches(auth_client: AsyncClient, db_session, mock_io) -> None:
    rec = await _make_send_record(auth_client, db_session)
    sent: dict = {}

    async def _loader(key: str) -> bytes:
        return b"small zip"

    async def _mailer(**kwargs):
        sent.update(kwargs)

    await run_send_task(db_session, rec.id, file_loader=_loader, send_mail=_mailer)
    refreshed = await db_session.get(ExportEmailSend, rec.id)
    assert refreshed.status == "sent"
    assert refreshed.delivery_mode == "attachment"
    assert refreshed.sent_at is not None
    # 附件带上了 ZIP
    assert len(sent["attachments"]) == 1
    assert sent["attachments"][0][2] == "application/zip"
    assert sent["to"] == ["proc@corp.com"]


async def test_run_send_large_uses_link(
    auth_client: AsyncClient, db_session, mock_io, monkeypatch
) -> None:
    rec = await _make_send_record(auth_client, db_session)
    monkeypatch.setattr(settings, "email_attach_max_bytes", 4)  # 强制走链接
    sent: dict = {}

    async def _loader(key: str) -> bytes:
        return b"this is a big zip payload"

    async def _mailer(**kwargs):
        sent.update(kwargs)

    async def _link(key, expires=None, download_filename=None):
        return f"https://r2.example/{key}?sig=x"

    await run_send_task(
        db_session, rec.id, file_loader=_loader, send_mail=_mailer, link_builder=_link
    )
    refreshed = await db_session.get(ExportEmailSend, rec.id)
    assert refreshed.status == "sent"
    assert refreshed.delivery_mode == "link"
    assert sent["attachments"] == []
    assert "https://r2.example/" in sent["body"]


async def test_run_send_failure_marks_failed(auth_client: AsyncClient, db_session, mock_io) -> None:
    rec = await _make_send_record(auth_client, db_session)

    async def _loader(key: str) -> bytes:
        return b"zip"

    async def _mailer(**kwargs):
        raise RuntimeError("smtp boom")

    await run_send_task(db_session, rec.id, file_loader=_loader, send_mail=_mailer)
    refreshed = await db_session.get(ExportEmailSend, rec.id)
    assert refreshed.status == "failed"
    assert refreshed.error_message == "发送失败，请稍后重试"  # 通用文案，不泄露内部细节


async def test_run_send_idempotent_on_sent(auth_client: AsyncClient, db_session, mock_io) -> None:
    rec = await _make_send_record(auth_client, db_session)
    calls: list[int] = []

    async def _loader(key: str) -> bytes:
        return b"zip"

    async def _mailer_ok(**kwargs):
        calls.append(1)

    async def _mailer_boom(**kwargs):
        raise AssertionError("已发送记录不应再次投递")

    await run_send_task(db_session, rec.id, file_loader=_loader, send_mail=_mailer_ok)
    await run_send_task(db_session, rec.id, file_loader=_loader, send_mail=_mailer_boom)
    refreshed = await db_session.get(ExportEmailSend, rec.id)
    assert refreshed.status == "sent"
    assert len(calls) == 1
