"""导出报销单：生成对账 Excel + 原件重命名打包 ZIP。"""

import io
import re
import zipfile
from collections.abc import Awaitable, Callable, Sequence

from openpyxl import Workbook

from app.models.invoice import Invoice

FileLoader = Callable[[str], Awaitable[bytes]]

COLUMNS: list[tuple[str, str]] = [
    ("开票日期", "issue_date"),
    ("发票代码", "invoice_code"),
    ("发票号码", "invoice_number"),
    ("发票类型", "invoice_type"),
    ("开票方", "seller_name"),
    ("购买方", "buyer_name"),
    ("价税合计", "total_amount"),
    ("归属分类", "category"),
    ("报销状态", "reimbursement_status"),
]


def _sanitize(s: str | None) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s or "").strip("_")[:50] or "NA"


def _ext(file_key: str) -> str:
    for e in (".pdf", ".png", ".jpg", ".jpeg"):
        if file_key.lower().endswith(e):
            return e
    return ""


def build_excel(invoices: Sequence[Invoice]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "对账单"
    ws.append([c[0] for c in COLUMNS])
    for inv in invoices:
        ws.append(
            ["" if getattr(inv, attr) is None else str(getattr(inv, attr)) for _, attr in COLUMNS]
        )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def build_export_zip(invoices: Sequence[Invoice], file_loader: FileLoader) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("invoices_export.xlsx", build_excel(invoices))
        used: set[str] = set()
        for inv in invoices:
            try:
                content = await file_loader(inv.file_key)
            except Exception:  # noqa: BLE001 个别原件下载失败不阻断
                continue
            base = f"{inv.issue_date or 'NA'}_{_sanitize(inv.seller_name)}_{inv.total_amount or 0}"
            name = f"{base}{_ext(inv.file_key)}"
            idx = 1
            while name in used:
                name = f"{base}_{idx}{_ext(inv.file_key)}"
                idx += 1
            used.add(name)
            z.writestr(f"原件/{name}", content)
    return buf.getvalue()
