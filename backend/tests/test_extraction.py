"""AI 抽取流程测试（网关/S3/PDF 已 mock）。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.invoice import Invoice
from app.models.seller_category_rule import SellerCategoryRule
from app.models.user import User
from app.services.extraction import _image_for, _parse_date, _parse_decimal, run_extraction


async def _make_user_invoice(db_session: AsyncSession, file_key: str = "u/abc.jpg"):
    user = User(email="ex@b.com", password_hash=hash_password("password123"))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    inv = Invoice(
        user_id=user.id,
        file_key=file_key,
        source="manual",
        status="processing",
        reimbursement_status="unreimbursed",
    )
    db_session.add(inv)
    await db_session.commit()
    await db_session.refresh(inv)
    return user, inv


async def test_extraction_fills_fields(db_session, monkeypatch) -> None:
    _, inv = await _make_user_invoice(db_session)

    async def fake_download(key):
        return b"imgbytes"

    async def fake_extract(image, ctype):
        return {
            "invoice_code": None,
            "invoice_number": "NO123",
            "issue_date": "2026-05-01",
            "invoice_type": "全电",
            "seller_name": "滴滴出行",
            "buyer_name": "张三",
            "total_amount": "88.50",
            "category": "差旅出行",
            "confidence": 0.95,
        }

    monkeypatch.setattr("app.core.storage.download_bytes", fake_download)
    monkeypatch.setattr("app.core.ai.extract_invoice_fields", fake_extract)

    await run_extraction(db_session, inv.id)
    await db_session.refresh(inv)
    assert inv.status == "pending"
    assert inv.invoice_number == "NO123"
    assert str(inv.total_amount) == "88.50"
    assert inv.category == "差旅出行"
    assert inv.issue_date.isoformat() == "2026-05-01"


async def test_extraction_applies_seller_rule(db_session, monkeypatch) -> None:
    user, inv = await _make_user_invoice(db_session)
    db_session.add(SellerCategoryRule(user_id=user.id, seller_name="滴滴出行", category="我的差旅"))
    await db_session.commit()

    async def fake_download(key):
        return b"x"

    async def fake_extract(image, ctype):
        return {"seller_name": "滴滴出行", "category": "差旅出行", "invoice_number": "N1"}

    monkeypatch.setattr("app.core.storage.download_bytes", fake_download)
    monkeypatch.setattr("app.core.ai.extract_invoice_fields", fake_extract)

    await run_extraction(db_session, inv.id)
    await db_session.refresh(inv)
    assert inv.category == "我的差旅"  # 规则覆盖 AI 结果


async def test_extraction_failure_marks_failed(db_session, monkeypatch) -> None:
    _, inv = await _make_user_invoice(db_session)

    async def boom(key):
        raise RuntimeError("s3 down")

    monkeypatch.setattr("app.core.storage.download_bytes", boom)
    await run_extraction(db_session, inv.id)
    await db_session.refresh(inv)
    assert inv.status == "failed"


def test_parse_helpers() -> None:
    assert _parse_date("2026-05-01").isoformat() == "2026-05-01"
    assert _parse_date("bad") is None
    assert _parse_date(None) is None
    assert str(_parse_decimal("12.50")) == "12.50"
    assert _parse_decimal("abc") is None
    assert _parse_decimal(None) is None


def test_image_for(monkeypatch) -> None:
    monkeypatch.setattr("app.services.extraction.pdf_first_page_png", lambda b: b"PNG")
    img, ct = _image_for("u/x.pdf", b"%PDF")
    assert img == b"PNG" and ct == "image/png"
    assert _image_for("u/x.png", b"raw")[1] == "image/png"
    assert _image_for("u/x.jpg", b"raw")[1] == "image/jpeg"
