"""Worker 任务测试：heartbeat 与 extract_invoice 委托。"""

from app.worker.settings import extract_invoice, heartbeat, shutdown, startup


async def test_heartbeat() -> None:
    assert await heartbeat({}) == "ok"


async def test_extract_invoice_delegates(monkeypatch) -> None:
    called: dict = {}

    async def fake_run(session, invoice_id):
        called["id"] = invoice_id

    monkeypatch.setattr("app.worker.settings.run_extraction", fake_run)

    ctx: dict = {}
    await startup(ctx)
    try:
        assert await extract_invoice(ctx, "abc-id") == "ok"
    finally:
        await shutdown(ctx)
    assert called["id"] == "abc-id"
