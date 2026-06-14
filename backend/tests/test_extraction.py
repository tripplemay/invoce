"""AI 抽取流程测试（网关/S3/PDF 已 mock）。"""

import httpx
import pytest
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


class _FakeResp:
    def __init__(self, status: int, payload: object = None) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "err", request=httpx.Request("POST", "http://x"), response=self
            )


def _fake_client_factory(statuses: list[int]):
    """构造一个按 statuses 顺序返回响应的假 httpx.AsyncClient。"""
    calls = {"n": 0}

    class _Client:
        def __init__(self, *a, **k) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a) -> bool:
            return False

        async def post(self, *a, **k):
            i = calls["n"]
            calls["n"] += 1
            status = statuses[i]
            if status == 200:
                return _FakeResp(
                    200, {"choices": [{"message": {"content": '{"seller_name":"x"}'}}]}
                )
            return _FakeResp(status)

    return _Client, calls


async def test_ai_retries_on_rate_limit(monkeypatch) -> None:
    """限流(402)后退避重试，最终成功。"""
    from app.core import ai

    client_cls, calls = _fake_client_factory([402, 200])
    monkeypatch.setattr(httpx, "AsyncClient", client_cls)
    result = await ai.extract_invoice_fields(b"img", "image/png")
    assert result == {"seller_name": "x"}
    assert calls["n"] == 2  # 首次 402 重试，第二次成功


async def test_ai_raises_on_non_retryable(monkeypatch) -> None:
    """非限流错误(400)立即抛出，不重试。"""
    from app.core import ai

    client_cls, calls = _fake_client_factory([400, 400])
    monkeypatch.setattr(httpx, "AsyncClient", client_cls)
    with pytest.raises(httpx.HTTPStatusError):
        await ai.extract_invoice_fields(b"img", "image/png")
    assert calls["n"] == 1  # 400 不重试


def test_ai_parse_json_lenient() -> None:
    from app.core.ai import _parse_json_lenient

    assert _parse_json_lenient('{"a": 1}') == {"a": 1}
    assert _parse_json_lenient('```json\n{"a": 2}\n```') == {"a": 2}
    assert _parse_json_lenient('前缀文字 {"a": 3} 后缀') == {"a": 3}


def test_image_for(monkeypatch) -> None:
    monkeypatch.setattr("app.services.extraction.pdf_first_page_png", lambda b: b"PNG")
    img, ct = _image_for("u/x.pdf", b"%PDF")
    assert img == b"PNG" and ct == "image/png"
    assert _image_for("u/x.png", b"raw")[1] == "image/png"
    assert _image_for("u/x.jpg", b"raw")[1] == "image/jpeg"
