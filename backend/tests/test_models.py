"""阶段0：校验模型 metadata 完整、枚举值与 PRD 一致（纯内存，不连数据库）。"""

from app.models import Base
from app.models.enums import (
    EmailSyncStatus,
    InvoiceSource,
    InvoiceStatus,
    ReimbursementStatus,
)


def test_all_tables_registered() -> None:
    expected = {
        "users",
        "email_accounts",
        "invoices",
        "seller_category_rules",
        "email_sync_logs",
    }
    assert expected <= set(Base.metadata.tables.keys())


def test_invoice_dedup_index_is_partial_and_nulls_not_distinct() -> None:
    invoices = Base.metadata.tables["invoices"]
    idx = next(i for i in invoices.indexes if i.name == "uq_invoice_dedup")
    assert idx.unique is True
    assert idx.dialect_options["postgresql"]["nulls_not_distinct"] is True
    # 偏索引条件存在
    assert idx.dialect_options["postgresql"]["where"] is not None


def test_enum_values_match_prd() -> None:
    assert {s.value for s in InvoiceStatus} == {"processing", "pending", "verified", "failed"}
    assert {s.value for s in ReimbursementStatus} == {"unreimbursed", "submitted", "reimbursed"}
    assert {s.value for s in InvoiceSource} == {"manual", "email_auto", "telegram"}
    assert {s.value for s in EmailSyncStatus} == {"SUCCESS", "FAILED", "IGNORED"}
