"""导出报销单测试（S3/队列已 mock）。"""

import uuid

import pytest
from httpx import AsyncClient

from app.models.invoice import Invoice
from app.services.export import build_excel


@pytest.fixture
def mock_io(monkeypatch):
    async def _noop(*a, **k):
        return None

    async def _dl(key):
        return b"%PDF-1.4 file"

    async def _enq(*a, **k):
        return None

    monkeypatch.setattr("app.core.storage.upload_bytes", _noop)
    monkeypatch.setattr("app.core.storage.download_bytes", _dl)
    monkeypatch.setattr("app.api.invoices.enqueue_extract", _enq)


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


async def test_export_zip_and_marks_submitted(auth_client: AsyncClient, mock_io) -> None:
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

    r = await auth_client.post(
        "/invoices/export", json={"invoice_ids": [inv["id"]], "mark_submitted": True}
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert r.content[:2] == b"PK"

    got = await auth_client.get(f"/invoices/{inv['id']}")
    assert got.json()["reimbursement_status"] == "submitted"


async def test_export_without_marking(auth_client: AsyncClient, mock_io) -> None:
    up = await auth_client.post(
        "/invoices/upload", files={"files": ("a.pdf", b"%PDF-1.4", "application/pdf")}
    )
    inv = up.json()[0]
    r = await auth_client.post(
        "/invoices/export", json={"invoice_ids": [inv["id"]], "mark_submitted": False}
    )
    assert r.status_code == 200
    got = await auth_client.get(f"/invoices/{inv['id']}")
    assert got.json()["reimbursement_status"] == "unreimbursed"


async def test_export_empty_returns_404(auth_client: AsyncClient, mock_io) -> None:
    r = await auth_client.post("/invoices/export", json={"invoice_ids": [str(uuid.uuid4())]})
    assert r.status_code == 404
