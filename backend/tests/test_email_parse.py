"""邮件解析纯函数测试。"""

import base64
from email.message import EmailMessage

from app.services import email_parse


def _attachment_msg() -> EmailMessage:
    m = EmailMessage()
    m["Subject"] = "您的电子发票"
    m["From"] = "billing@corp.com"
    m.set_content("请查收发票")
    m.add_attachment(b"%PDF-1.4 fake", maintype="application", subtype="pdf", filename="inv.pdf")
    return m


def test_matches_keywords() -> None:
    assert email_parse.matches_keywords("您的电子发票", "正文")
    assert email_parse.matches_keywords("hello", "这是行程单请查收")
    assert email_parse.matches_keywords("Your Invoice", "")
    assert not email_parse.matches_keywords("会议通知", "今天开会")


def test_extract_attachments() -> None:
    files = email_parse.extract_attachments(_attachment_msg())
    assert len(files) == 1
    data, ctype = files[0]
    assert ctype == "application/pdf"
    assert data == b"%PDF-1.4 fake"


def test_extract_attachments_skips_noise() -> None:
    """同邮件含真发票 + 行程单时，只取发票，跳过行程单/汇总单等噪音文件。"""
    m = EmailMessage()
    m["Subject"] = "美团出行电子发票及行程报销单"
    m.set_content("请查收")
    m.add_attachment(b"%PDF-real", maintype="application", subtype="pdf", filename="电子发票1.pdf")
    m.add_attachment(b"%PDF-trip", maintype="application", subtype="pdf", filename="行程单.pdf")
    m.add_attachment(
        b"%PDF-sum", maintype="application", subtype="pdf", filename="汇总单(行程).pdf"
    )
    files = email_parse.extract_attachments(m)
    assert files == [(b"%PDF-real", "application/pdf")]


def test_extract_zip_pdfs() -> None:
    """从 zip 中只取 pdf/ 下的发票 PDF，忽略 ofd/xml，并跳过 zip 内的汇总单。"""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("pdf/1_invoice.pdf", b"%PDF-A")
        z.writestr("pdf/2_invoice.pdf", b"%PDF-B")
        z.writestr("ofd/1_invoice.ofd", b"OFDDATA")
        z.writestr("xml/1_invoice.xml", b"<xml/>")
        z.writestr("通行费电子票据汇总单.pdf", b"%PDF-noise")
    m = EmailMessage()
    m["Subject"] = "通行费电子发票"
    m.set_content("请查收")
    m.add_attachment(
        buf.getvalue(), maintype="application", subtype="zip", filename="通行费电子发票.zip"
    )
    files = email_parse.extract_zip_pdfs(m)
    assert sorted(d for d, _ in files) == [b"%PDF-A", b"%PDF-B"]
    assert all(ct == "application/pdf" for _, ct in files)


def test_extract_attachments_octet_stream_pdf() -> None:
    """声明为 application/octet-stream 的 PDF 也能按魔数识别并收下。"""
    m = EmailMessage()
    m["Subject"] = "电子发票"
    m.set_content("请查收")
    m.add_attachment(
        b"%PDF-1.4 data", maintype="application", subtype="octet-stream", filename="电子发票1.pdf"
    )
    assert email_parse.extract_attachments(m) == [(b"%PDF-1.4 data", "application/pdf")]


def test_extract_zip_noise_parent_dir_and_no_suffix() -> None:
    """zip 以 octet-stream + 无 .zip 后缀投递时按魔数识别；真发票在含噪音词父目录下仍按 basename 保留。"""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("行程报销批次/pdf/真发票001.pdf", b"%PDF-real")
        z.writestr("行程报销批次/行程单.pdf", b"%PDF-noise")
    m = EmailMessage()
    m["Subject"] = "电子发票"
    m.set_content("请查收")
    m.add_attachment(
        buf.getvalue(), maintype="application", subtype="octet-stream", filename="通行费电子发票"
    )
    # 父目录“行程报销批次”不应误伤真发票；basename 为“行程单.pdf”的才被剔除
    assert email_parse.extract_zip_pdfs(m) == [(b"%PDF-real", "application/pdf")]


def test_is_noise_filename() -> None:
    assert email_parse.is_noise_filename("通行费电子票据汇总单(票据).pdf")
    assert email_parse.is_noise_filename("悦道用车行程单.pdf")
    assert email_parse.is_noise_filename("信用卡电子账单.pdf")
    # 顺丰式"电子发票 + 发票运单明细"：运单明细/费用明细等清单类不是发票，应剔除
    assert email_parse.is_noise_filename("发票运单明细.pdf")
    assert email_parse.is_noise_filename("费用明细表.pdf")
    assert email_parse.is_noise_filename("顺丰运单.pdf")
    # 真发票本身（顺丰电子发票.pdf / 电子发票1.pdf）不应被误剔
    assert not email_parse.is_noise_filename("顺丰电子发票.pdf")
    assert not email_parse.is_noise_filename("悦道用车电子发票1.pdf")
    assert not email_parse.is_noise_filename(None)


def test_sf_email_keeps_invoice_drops_waybill_detail() -> None:
    """顺丰邮件含「顺丰电子发票.pdf」+「发票运单明细.pdf」：只保留真发票，剔除运单明细。"""
    m = EmailMessage()
    m["Subject"] = "顺丰电子发票出票通知"
    m.set_content("请查收")
    m.add_attachment(
        b"%PDF-invoice", maintype="application", subtype="pdf", filename="顺丰电子发票.pdf"
    )
    m.add_attachment(
        b"%PDF-waybill", maintype="application", subtype="pdf", filename="发票运单明细.pdf"
    )
    assert email_parse.extract_attachments(m) == [(b"%PDF-invoice", "application/pdf")]


def test_extract_inline_base64_images() -> None:
    raw = base64.b64encode(b"PNGDATA").decode()
    html = f'<html><body>发票<img src="data:image/png;base64,{raw}"/></body></html>'
    files = email_parse.extract_inline_base64_images(html)
    assert files == [(b"PNGDATA", "image/png")]


def test_extract_external_image_urls() -> None:
    html = '<img src="https://cdn.example.com/a.png"> 文字 <img src="http://x.cn/b.jpg">'
    urls = email_parse.extract_external_image_urls(html)
    assert urls == ["https://cdn.example.com/a.png", "http://x.cn/b.jpg"]


def test_decode_mime_header() -> None:
    encoded = "=?utf-8?b?5Y+R56Wo?="  # “发票”
    assert email_parse.decode_mime_header(encoded) == "发票"
    assert email_parse.decode_mime_header(None) == ""


def test_decode_mime_header_invalid_charset() -> None:
    """非法 charset（如 unknown-8bit）应容错回退、绝不抛异常（否则坏邮件会中断整批归集）。"""
    bad = "=?unknown-8bit?B?5Y+R56Wo?="  # 发票的 UTF-8 字节，却标了非法 charset
    assert email_parse.decode_mime_header(bad) == "发票"
