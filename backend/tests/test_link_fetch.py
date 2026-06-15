"""正文内嵌免登录发票直链：抽取(白名单)+ SSRF 防护下载 的纯/网络单元测试。

只允许拉取白名单内的发票 CDN(如京东 jdcloud-oss 预签名直链),绝不无差别跟随陌生链接,
从根上规避 SSRF/钓鱼;再叠 netguard IP 兜底、follow_redirects=False、大小上限、%PDF 魔数。
"""

import httpx
import pytest

from app.services import link_fetch

# ---- 真实京东发票邮件正文片段(脱敏):营销跳转链 + xml + 免登录预签名 PDF 直链 ----
_JD_HTML = (
    '<a href="https://tr.jd.com/jump/transfer?jump_kid=155&amp;jump_to=https%3A%2F%2Fwww.jd.com">访问京东</a>'
    '<a href="https://i-mkt.jd.com/subscribe/index?token=abc">订阅</a>'
    '<a href="https://eicore-invoice-26.s3.cn-north-1.jdcloud-oss.com/digital-invoice/'
    'invoice_xml_26627000000108901583.xml?AWSAccessKeyId=JDC_x&amp;Expires=2728203746&amp;Signature=aaa">XML</a>'
    '<a href="https://eicore-invoice-26.s3.cn-north-1.jdcloud-oss.com/digital-invoice/'
    'digital_26627000000108901583.pdf?AWSAccessKeyId=JDC_x&amp;Expires=2728203746&amp;Signature=bbb">下载PDF</a>'
)


def test_extract_keeps_only_allowlisted_pdf() -> None:
    """只抽白名单 host 下的 .pdf 直链：剔除营销跳转链(tr.jd.com)、订阅链、以及 .xml。"""
    links = link_fetch.extract_invoice_pdf_links(_JD_HTML)
    assert links == [
        "https://eicore-invoice-26.s3.cn-north-1.jdcloud-oss.com/digital-invoice/"
        "digital_26627000000108901583.pdf?AWSAccessKeyId=JDC_x&Expires=2728203746&Signature=bbb"
    ]


def test_extract_unescapes_amp() -> None:
    """href 中的 &amp; 必须还原成 &(否则 URL 参数错乱、签名失效)。"""
    (link,) = link_fetch.extract_invoice_pdf_links(_JD_HTML)
    assert "&amp;" not in link and "&Signature=bbb" in link


def test_extract_dedup_and_empty() -> None:
    assert link_fetch.extract_invoice_pdf_links("") == []
    assert link_fetch.extract_invoice_pdf_links("<p>无链接</p>") == []
    dup = _JD_HTML + _JD_HTML
    assert len(link_fetch.extract_invoice_pdf_links(dup)) == 1  # 去重


def test_extract_rejects_non_allowlist_and_spoof() -> None:
    html = (
        '<a href="https://evil.com/digital_1.pdf">e</a>'
        '<a href="https://jdcloud-oss.com.evil.com/x.pdf">spoof</a>'
        '<a href="http://eicore.s3.cn-north-1.jdcloud-oss.com/a.pdf">http(非https)</a>'
        '<a href="https://eicore.s3.cn-north-1.jdcloud-oss.com:9999/a.pdf">非标端口</a>'
    )
    assert link_fetch.extract_invoice_pdf_links(html) == []


def test_is_allowed_host() -> None:
    assert link_fetch.is_allowed_host("eicore-invoice-26.s3.cn-north-1.jdcloud-oss.com")
    assert link_fetch.is_allowed_host("jdcloud-oss.com")  # apex 也允许
    assert not link_fetch.is_allowed_host("jdcloud-oss.com.evil.com")  # 后缀伪装
    assert not link_fetch.is_allowed_host("xjdcloud-oss.com")  # 无点边界
    assert not link_fetch.is_allowed_host("evil.com")
    assert not link_fetch.is_allowed_host("")


_PDF_URL = "https://eicore-invoice-26.s3.cn-north-1.jdcloud-oss.com/digital-invoice/digital_1.pdf?Signature=b"


@pytest.fixture
def allow_netguard(monkeypatch):
    # 避免单元测试真做 DNS：netguard IP 兜底在此放行(白名单 host 已是主控)
    monkeypatch.setattr(link_fetch.netguard, "is_safe_url", lambda url: True)


async def test_fetch_pdf_ok(allow_netguard) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"%PDF-1.4 data", headers={"content-type": "application/pdf"}
        )

    data = await link_fetch.fetch_pdf(_PDF_URL, transport=httpx.MockTransport(handler))
    assert data == b"%PDF-1.4 data"


async def test_fetch_pdf_rejects_non_allowlist_host_without_network() -> None:
    # host 不在白名单 → 直接 None,不发起任何请求(transport 不会被调用)
    def handler(_req):  # pragma: no cover - 不应被调用
        raise AssertionError("should not fetch non-allowlisted host")

    assert (
        await link_fetch.fetch_pdf("https://evil.com/x.pdf", transport=httpx.MockTransport(handler))
        is None
    )


async def test_fetch_pdf_rejects_nonstandard_port_without_network() -> None:
    # 白名单 host 但非 443 端口 → 拒绝,不发起请求
    def handler(_req):  # pragma: no cover - 不应被调用
        raise AssertionError("should not fetch non-443 port")

    url = "https://x.jdcloud-oss.com:8443/a.pdf"
    assert await link_fetch.fetch_pdf(url, transport=httpx.MockTransport(handler)) is None


async def test_fetch_pdf_rejects_html_content(allow_netguard) -> None:
    def handler(_req):
        return httpx.Response(
            200, content=b"<html>login</html>", headers={"content-type": "text/html"}
        )

    assert await link_fetch.fetch_pdf(_PDF_URL, transport=httpx.MockTransport(handler)) is None


async def test_fetch_pdf_rejects_non_pdf_magic(allow_netguard) -> None:
    # content-type 谎称 pdf,但魔数不是 %PDF → 拒绝
    def handler(_req):
        return httpx.Response(200, content=b"NOTPDF", headers={"content-type": "application/pdf"})

    assert await link_fetch.fetch_pdf(_PDF_URL, transport=httpx.MockTransport(handler)) is None


async def test_fetch_pdf_rejects_redirect(allow_netguard) -> None:
    # follow_redirects=False:302 不被跟随,直接判失败(防重定向 SSRF)
    def handler(_req):
        return httpx.Response(302, headers={"location": "https://internal/x"})

    assert await link_fetch.fetch_pdf(_PDF_URL, transport=httpx.MockTransport(handler)) is None


async def test_fetch_pdf_rejects_oversize(allow_netguard, monkeypatch) -> None:
    monkeypatch.setattr(link_fetch, "MAX_PDF_BYTES", 8)

    def handler(_req):
        return httpx.Response(
            200, content=b"%PDF" + b"x" * 100, headers={"content-type": "application/pdf"}
        )

    assert await link_fetch.fetch_pdf(_PDF_URL, transport=httpx.MockTransport(handler)) is None


async def test_fetch_pdf_swallows_transport_error(allow_netguard) -> None:
    def handler(_req):
        raise httpx.ConnectError("boom")

    assert await link_fetch.fetch_pdf(_PDF_URL, transport=httpx.MockTransport(handler)) is None


async def test_fetch_invoice_pdfs_skips_failures(monkeypatch) -> None:
    async def fake_fetch(url, **_kw):
        return b"%PDF-ok" if "good" in url else None

    monkeypatch.setattr(link_fetch, "fetch_pdf", fake_fetch)
    out = await link_fetch.fetch_invoice_pdfs(
        ["https://x.jdcloud-oss.com/good.pdf", "https://x.jdcloud-oss.com/bad.pdf"]
    )
    assert out == [b"%PDF-ok"]
