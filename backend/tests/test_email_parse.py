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
