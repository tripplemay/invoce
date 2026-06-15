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
    # 内容随文件名变化，避免不同用例间 file_key 去重相互影响
    return await client.post(
        "/invoices/upload", files={"files": (name, b"%PDF-1.4 " + name.encode(), ctype)}
    )


async def test_upload_creates_processing_invoice(auth_client, mock_io) -> None:
    r = await _upload(auth_client)
    assert r.status_code == 201
    inv = r.json()[0]
    assert inv["status"] == "processing"
    assert inv["source"] == "manual"
    assert inv["reimbursement_status"] == "unreimbursed"

    lst = await auth_client.get("/invoices")
    assert len(lst.json()) == 1


async def test_list_orders_unreimbursed_newest_first(auth_client, mock_io) -> None:
    """默认排序：待报销优先，组内按时间最新在前；已流转的(报销中/已完成)排其后。"""
    a = (await _upload(auth_client, name="a.pdf")).json()[0]
    b = (await _upload(auth_client, name="b.pdf")).json()[0]
    c = (await _upload(auth_client, name="c.pdf")).json()[0]
    await auth_client.patch(f"/invoices/{a['id']}", json={"issue_date": "2026-03-01"})
    await auth_client.patch(f"/invoices/{b['id']}", json={"issue_date": "2026-05-01"})
    await auth_client.patch(f"/invoices/{c['id']}", json={"issue_date": "2026-01-01"})
    # B 日期最新，但推进到「报销中」后应排到所有待报销之后（状态优先于时间）
    await auth_client.patch(
        f"/invoices/{b['id']}/reimbursement-status", json={"reimbursement_status": "submitted"}
    )
    order = [i["id"] for i in (await auth_client.get("/invoices")).json()]
    # 待报销 A(3月) > C(1月)，最后才是报销中的 B
    assert order == [a["id"], c["id"], b["id"]]


async def test_upload_rejects_bad_magic(auth_client, mock_io) -> None:
    # 即使谎报 content_type 为 pdf，魔数不符也应拒绝
    r = await auth_client.post(
        "/invoices/upload", files={"files": ("x.pdf", b"plain text not a pdf", "application/pdf")}
    )
    assert r.status_code == 415


async def test_upload_zip_extracts_pdfs(auth_client, mock_io) -> None:
    """上传 ZIP（如京东批量下载包）应解出其中每张发票 PDF，并跳过汇总单等噪音。"""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("pdf/a.pdf", b"%PDF-1.4 A")
        z.writestr("pdf/b.pdf", b"%PDF-1.4 B")
        z.writestr("通行费电子票据汇总单.pdf", b"%PDF-noise")
    r = await auth_client.post(
        "/invoices/upload",
        files={"files": ("invoices.zip", buf.getvalue(), "application/zip")},
    )
    assert r.status_code == 201
    assert len(r.json()) == 2  # 2 张真发票，汇总单被噪音过滤
    assert all(i["source"] == "manual" for i in r.json())


async def test_upload_zip_dedups_identical_pdfs(auth_client, mock_io) -> None:
    """同一 ZIP 内两个字节完全相同的 PDF 只建 1 条（file_key 去重）。"""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.pdf", b"%PDF-1.4 SAME")
        z.writestr("b.pdf", b"%PDF-1.4 SAME")
    r = await auth_client.post(
        "/invoices/upload", files={"files": ("dup.zip", buf.getvalue(), "application/zip")}
    )
    assert r.status_code == 201 and len(r.json()) == 1


async def test_upload_dedup_skips_duplicate(auth_client, mock_io) -> None:
    """同一文件重复上传：第二次靠 file_key 去重，不再新建。"""
    await _upload(auth_client, name="x.pdf")
    r2 = await _upload(auth_client, name="x.pdf")
    assert r2.status_code == 201 and r2.json() == []
    lst = await auth_client.get("/invoices")
    assert len(lst.json()) == 1


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
        files={"files": ("a.pdf", b"%PDF-1.4", "application/pdf")},
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
