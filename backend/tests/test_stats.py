"""消费分析聚合端点 /invoices/stats 测试。"""

import uuid
from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.invoice import Invoice
from app.models.user import User


async def _user_id(db_session) -> uuid.UUID:
    user = await db_session.scalar(select(User).where(User.email == "user@test.com"))
    return user.id


async def _add(
    db_session,
    user_id,
    *,
    amount,
    issue_date,
    category=None,
    reimb="unreimbursed",
    status="pending",
) -> None:
    db_session.add(
        Invoice(
            user_id=user_id,
            file_key=f"k/{uuid.uuid4().hex}.pdf",
            source="manual",
            status=status,
            reimbursement_status=reimb,
            total_amount=amount,
            issue_date=issue_date,
            category=category,
        )
    )
    await db_session.commit()


async def test_stats_empty(auth_client: AsyncClient) -> None:
    s = (await auth_client.get("/invoices/stats")).json()
    assert s["total"] == 0 and s["count"] == 0
    assert s["by_category"] == [] and s["by_month"] == []
    assert s["by_reimbursement"]["unreimbursed"] == {"amount": 0.0, "count": 0}
    assert set(s["by_reimbursement"]) == {"unreimbursed", "submitted", "reimbursed"}


async def test_stats_aggregates(auth_client: AsyncClient, db_session) -> None:
    uid = await _user_id(db_session)
    await _add(
        db_session, uid, amount=Decimal("100"), issue_date=date(2026, 1, 15), category="餐饮"
    )
    await _add(
        db_session,
        uid,
        amount=Decimal("50"),
        issue_date=date(2026, 3, 10),
        category="餐饮",
        reimb="submitted",
    )
    await _add(
        db_session,
        uid,
        amount=Decimal("200"),
        issue_date=date(2026, 3, 20),
        category="差旅",
        reimb="reimbursed",
    )
    # processing/无金额 → 不计入
    await _add(db_session, uid, amount=None, issue_date=None, status="processing")

    s = (await auth_client.get("/invoices/stats")).json()
    assert s["total"] == 350.0
    assert s["count"] == 3
    assert s["by_reimbursement"]["unreimbursed"] == {"amount": 100.0, "count": 1}
    assert s["by_reimbursement"]["submitted"] == {"amount": 50.0, "count": 1}
    assert s["by_reimbursement"]["reimbursed"] == {"amount": 200.0, "count": 1}
    # 分类按金额降序：差旅 200 > 餐饮 150
    assert s["by_category"][0] == {"category": "差旅", "amount": 200.0, "count": 1}
    cats = {c["category"]: c for c in s["by_category"]}
    assert cats["餐饮"] == {"category": "餐饮", "amount": 150.0, "count": 2}
    # 月度连续补零：1 月 100、2 月补 0、3 月 250
    assert [m["month"] for m in s["by_month"]] == ["2026-01", "2026-02", "2026-03"]
    months = {m["month"]: m for m in s["by_month"]}
    assert months["2026-01"]["amount"] == 100.0
    assert months["2026-02"] == {"month": "2026-02", "amount": 0.0, "count": 0}
    assert months["2026-03"] == {"month": "2026-03", "amount": 250.0, "count": 2}


async def test_stats_date_range_filters(auth_client: AsyncClient, db_session) -> None:
    uid = await _user_id(db_session)
    await _add(db_session, uid, amount=Decimal("100"), issue_date=date(2026, 1, 15))
    await _add(db_session, uid, amount=Decimal("200"), issue_date=date(2026, 3, 15))
    s = (await auth_client.get("/invoices/stats?date_from=2026-03-01&date_to=2026-03-31")).json()
    assert s["total"] == 200.0 and s["count"] == 1
    assert [m["month"] for m in s["by_month"]] == ["2026-03"]


async def test_stats_unrecognized_category(auth_client: AsyncClient, db_session) -> None:
    uid = await _user_id(db_session)
    await _add(db_session, uid, amount=Decimal("10"), issue_date=date(2026, 1, 1), category=None)
    await _add(db_session, uid, amount=Decimal("20"), issue_date=date(2026, 1, 2), category="")
    s = (await auth_client.get("/invoices/stats")).json()
    cats = {c["category"]: c["amount"] for c in s["by_category"]}
    assert cats == {"未识别": 30.0}
