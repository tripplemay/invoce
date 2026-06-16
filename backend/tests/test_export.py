"""异步导出报销单测试（S3/队列已 mock）。"""

import uuid

import pytest
from httpx import AsyncClient

from app.models.export_task import ExportTask
from app.models.invoice import Invoice
from app.services.export import build_excel
from app.services.export_runner import run_export_task


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

    async def _enq(*a, **k):
        return None

    monkeypatch.setattr("app.core.storage.upload_bytes", _noop)
    monkeypatch.setattr("app.api.invoices.enqueue_extract", _enq)


async def _make_invoice(auth_client: AsyncClient, total: str = "100.00") -> str:
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
            "total_amount": total,
        },
    )
    return inv["id"]


def test_build_excel_returns_xlsx() -> None:
    inv = Invoice(
        file_key="u/a.pdf",
        source="manual",
        status="verified",
        reimbursement_status="unreimbursed",
        invoice_number="E1",
        seller_name="阿里云",
    )
    data = build_excel([inv])
    assert data[:2] == b"PK"  # xlsx 即 zip


async def test_create_task_enqueues_and_marks_submitted(
    auth_client: AsyncClient, mock_io, fake_pool
) -> None:
    iid = await _make_invoice(auth_client)
    r = await auth_client.post("/export-tasks", json={"invoice_ids": [iid], "mark_submitted": True})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["invoice_count"] == 1
    assert body["mark_submitted"] is True
    # 入队 run_export
    assert len(fake_pool.jobs) == 1
    name, args = fake_pool.jobs[0]
    assert name == "run_export" and args == (body["id"],)
    # 标记报销中立即生效
    got = await auth_client.get(f"/invoices/{iid}")
    assert got.json()["reimbursement_status"] == "submitted"


async def test_create_task_without_marking(auth_client: AsyncClient, mock_io, fake_pool) -> None:
    iid = await _make_invoice(auth_client)
    r = await auth_client.post(
        "/export-tasks", json={"invoice_ids": [iid], "mark_submitted": False}
    )
    assert r.status_code == 201
    got = await auth_client.get(f"/invoices/{iid}")
    assert got.json()["reimbursement_status"] == "unreimbursed"


async def test_create_task_empty_returns_404(auth_client: AsyncClient, mock_io, fake_pool) -> None:
    r = await auth_client.post("/export-tasks", json={"invoice_ids": [str(uuid.uuid4())]})
    assert r.status_code == 404
    assert fake_pool.jobs == []


async def test_list_tasks_newest_first(auth_client: AsyncClient, mock_io, fake_pool) -> None:
    iid = await _make_invoice(auth_client)
    await auth_client.post("/export-tasks", json={"invoice_ids": [iid]})
    r = await auth_client.get("/export-tasks")
    assert r.status_code == 200
    tasks = r.json()
    assert len(tasks) == 1 and tasks[0]["invoice_count"] == 1


async def test_download_before_completion_409(auth_client: AsyncClient, mock_io, fake_pool) -> None:
    iid = await _make_invoice(auth_client)
    t = (await auth_client.post("/export-tasks", json={"invoice_ids": [iid]})).json()
    r = await auth_client.get(f"/export-tasks/{t['id']}/download")
    assert r.status_code == 409


async def test_run_export_completes_then_download(
    auth_client: AsyncClient, db_session, mock_io, fake_pool, monkeypatch
) -> None:
    iid = await _make_invoice(auth_client)
    t = (await auth_client.post("/export-tasks", json={"invoice_ids": [iid]})).json()

    uploaded: dict = {}

    async def _loader(key: str) -> bytes:
        return b"%PDF-1.4 file"

    async def _uploader(key: str, data: bytes, ctype: str) -> None:
        uploaded["key"] = key
        uploaded["size"] = len(data)

    await run_export_task(db_session, uuid.UUID(t["id"]), file_loader=_loader, uploader=_uploader)

    task = await db_session.get(ExportTask, uuid.UUID(t["id"]))
    assert task.status == "completed"
    assert task.result_file_key == uploaded["key"]
    assert task.result_filename and task.result_filename.endswith(".zip")
    assert uploaded["size"] > 0

    async def _sign(key, expires=None, download_filename=None):
        assert download_filename == task.result_filename
        return f"https://r2.example/{key}?sig=x"

    monkeypatch.setattr("app.core.storage.presigned_get_url", _sign)
    r = await auth_client.get(f"/export-tasks/{t['id']}/download")
    assert r.status_code == 200
    assert r.json()["url"].startswith("https://r2.example/")


async def test_run_export_failure_marks_failed(
    auth_client: AsyncClient, db_session, mock_io, fake_pool
) -> None:
    iid = await _make_invoice(auth_client)
    t = (await auth_client.post("/export-tasks", json={"invoice_ids": [iid]})).json()

    async def _loader(key: str) -> bytes:
        return b"%PDF-1.4 file"

    async def _uploader(key: str, data: bytes, ctype: str) -> None:
        raise RuntimeError("upload boom")

    await run_export_task(db_session, uuid.UUID(t["id"]), file_loader=_loader, uploader=_uploader)
    task = await db_session.get(ExportTask, uuid.UUID(t["id"]))
    assert task.status == "failed"
    # 失败原因用通用文案（不泄露内部异常细节）
    assert task.error_message == "打包失败，请稍后重试"


async def test_download_other_users_task_404(
    auth_client: AsyncClient, client: AsyncClient, mock_io, fake_pool
) -> None:
    iid = await _make_invoice(auth_client)
    t = (await auth_client.post("/export-tasks", json={"invoice_ids": [iid]})).json()
    # 另一个用户登录后访问别人的任务 → 404
    reg = await client.post(
        "/auth/register", json={"email": "other@test.com", "password": "password123"}
    )
    other = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    r = await client.get(f"/export-tasks/{t['id']}/download", headers=other)
    assert r.status_code == 404


async def test_run_export_idempotent_on_completed(
    auth_client: AsyncClient, db_session, mock_io, fake_pool
) -> None:
    """已完成的任务被重复入队/重试 → 跳过，不再二次打包上传。"""
    iid = await _make_invoice(auth_client)
    t = (await auth_client.post("/export-tasks", json={"invoice_ids": [iid]})).json()
    uploads: list[str] = []

    async def _loader(key: str) -> bytes:
        return b"%PDF-1.4 file"

    async def _up_ok(key: str, data: bytes, ctype: str) -> None:
        uploads.append(key)

    async def _up_boom(key: str, data: bytes, ctype: str) -> None:
        raise AssertionError("已完成任务不应再次上传")

    await run_export_task(db_session, uuid.UUID(t["id"]), file_loader=_loader, uploader=_up_ok)
    await run_export_task(db_session, uuid.UUID(t["id"]), file_loader=_loader, uploader=_up_boom)
    task = await db_session.get(ExportTask, uuid.UUID(t["id"]))
    assert task.status == "completed"
    assert len(uploads) == 1


async def test_export_zip_lists_failed_originals() -> None:
    """原件下载失败时，zip 内补一份缺失清单，避免用户以为压缩包损坏。"""
    import io
    import zipfile

    from app.services.export import build_export_zip

    inv = Invoice(
        file_key="u/a.pdf",
        source="manual",
        status="verified",
        reimbursement_status="unreimbursed",
        seller_name="阿里云",
    )

    async def _boom(key: str) -> bytes:
        raise RuntimeError("dl fail")

    data = await build_export_zip([inv], _boom)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
    assert "invoices_export.xlsx" in names
    assert any("缺失原件清单" in n for n in names)
