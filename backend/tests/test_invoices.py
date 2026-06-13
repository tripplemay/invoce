"""发票上传/防重/流转/预览测试（S3 与队列已 mock）。"""

import pytest
from httpx import AsyncClient


@pytest.fixture
def mock_io(monkeypatch):
    async def _noop_upload(*a, **k):
        return None

    async def _fake_presign(*a, **k):
        return "https://example.com/presigned"

    async def _noop_enqueue(*a, **k):
        return None

    monkeypatch.setattr("app.core.storage.upload_bytes", _noop_upload)
    monkeypatch.setattr("app.core.storage.presigned_get_url", _fake_presign)
    monkeypatch.setattr("app.api.invoices.enqueue_extract", _noop_enqueue)


async def _upload(client: AsyncClient, name: str = "inv.pdf", ctype: str = "application/pdf"):
    return await client.post("/invoices/upload", files={"files": (name, b"%PDF-1.4 data", ctype)})


async def test_upload_creates_processing_invoice(auth_client, mock_io) -> None:
    r = await _upload(auth_client)
    assert r.status_code == 201
    inv = r.json()[0]
    assert inv["status"] == "processing"
    assert inv["source"] == "manual"
    assert inv["reimbursement_status"] == "unreimbursed"

    lst = await auth_client.get("/invoices")
    assert len(lst.json()) == 1


async def test_upload_rejects_unsupported_type(auth_client, mock_io) -> None:
    r = await _upload(auth_client, name="x.txt", ctype="text/plain")
    assert r.status_code == 415


async def test_dedup_blocks_on_save(auth_client, mock_io) -> None:
    a = (await _upload(auth_client)).json()[0]
    b = (await _upload(auth_client, name="b.pdf")).json()[0]
    # A 校对入库
    ra = await auth_client.patch(
        f"/invoices/{a['id']}",
        json={"invoice_code": None, "invoice_number": "X12345", "issue_date": "2026-05-01"},
    )
    assert ra.status_code == 200 and ra.json()["status"] == "verified"
    # B 填入相同号码 -> 防重拦截
    rb = await auth_client.patch(f"/invoices/{b['id']}", json={"invoice_number": "X12345"})
    assert rb.status_code == 409
    assert "重复报销风险" in rb.json()["detail"]


async def test_check_duplicate_endpoint(auth_client, mock_io) -> None:
    a = (await _upload(auth_client)).json()[0]
    await auth_client.patch(f"/invoices/{a['id']}", json={"invoice_number": "N888"})
    r = await auth_client.post("/invoices/check-duplicate", json={"invoice_number": "N888"})
    assert r.json()["duplicate"] is True
    r2 = await auth_client.post("/invoices/check-duplicate", json={"invoice_number": "OTHER"})
    assert r2.json()["duplicate"] is False


async def test_reimbursement_status_forward_only(auth_client, mock_io) -> None:
    inv = (await _upload(auth_client)).json()[0]
    fwd = await auth_client.patch(
        f"/invoices/{inv['id']}/reimbursement-status", json={"reimbursement_status": "submitted"}
    )
    assert fwd.status_code == 200 and fwd.json()["reimbursement_status"] == "submitted"
    back = await auth_client.patch(
        f"/invoices/{inv['id']}/reimbursement-status", json={"reimbursement_status": "unreimbursed"}
    )
    assert back.status_code == 409


async def test_preview_returns_presigned_url(auth_client, mock_io) -> None:
    inv = (await _upload(auth_client)).json()[0]
    r = await auth_client.get(f"/invoices/{inv['id']}/preview")
    assert r.status_code == 200
    assert r.json()["url"].startswith("https://")
    assert r.json()["expires_in"] == 60


async def test_invoices_require_auth(client) -> None:
    assert (await client.get("/invoices")).status_code == 401


async def test_invoice_isolation(client, mock_io) -> None:
    ra = await client.post("/auth/register", json={"email": "o1@b.com", "password": "password123"})
    ta = ra.json()["access_token"]
    up = await client.post(
        "/invoices/upload",
        files={"files": ("a.pdf", b"x", "application/pdf")},
        headers={"Authorization": f"Bearer {ta}"},
    )
    iid = up.json()[0]["id"]
    rb = await client.post("/auth/register", json={"email": "o2@b.com", "password": "password123"})
    tb = rb.json()["access_token"]
    got = await client.get(f"/invoices/{iid}", headers={"Authorization": f"Bearer {tb}"})
    assert got.status_code == 404


async def test_category_correction_learns_rule(auth_client, mock_io, db_session) -> None:
    from sqlalchemy import select

    from app.models.seller_category_rule import SellerCategoryRule

    inv = (await _upload(auth_client)).json()[0]
    await auth_client.patch(
        f"/invoices/{inv['id']}",
        json={"invoice_number": "R1", "seller_name": "小米", "category": "运动爱好"},
    )
    rule = (await db_session.scalars(select(SellerCategoryRule))).first()
    assert rule is not None
    assert rule.seller_name == "小米" and rule.category == "运动爱好"
