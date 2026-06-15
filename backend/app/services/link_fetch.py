"""正文内嵌「免登录发票直链」的抽取与安全下载。

背景：部分商家（典型是京东）的发票邮件无 PDF 附件，而是把发票 PDF 以**免登录预签名直链**
放在 HTML 正文里（如 `https://<bucket>.s3.cn-north-1.jdcloud-oss.com/digital-invoice/digital_*.pdf?Signature=...`，
有效期长达数十年 ≈ 永久）。我们抽出这类直链并把 PDF 拉回来，喂进与普通附件相同的归集管线。

安全模型（关键）：**域名白名单为主控**——只拉取已知发票 CDN，绝不无差别跟随陌生链接，
从根上规避 SSRF/钓鱼（监管反复预警「发票」钓鱼邮件）。在白名单之上再叠多层防御：
- 只允许 https；host 必须命中白名单后缀（带点边界，防 `jdcloud-oss.com.evil.com` 伪装）；
- netguard IP 兜底（解析地址落私有/内网段则拒绝）；
- follow_redirects=False（不跟任何重定向，防重定向 SSRF；京东直链本身无跳转）；
- 响应大小上限 + 拒绝 text/image content-type + 强制 `%PDF` 魔数；超时。
"""

import asyncio
import html as html_module
import re
from collections.abc import Awaitable, Callable
from urllib.parse import SplitResult, urlsplit

import httpx

from app.core import netguard

# 允许自动拉取的发票 CDN host 后缀（带前导点 → 强制点边界）。新来源验证通过后追加到此处即可扩展。
ALLOWED_HOST_SUFFIXES: tuple[str, ...] = (".jdcloud-oss.com",)

MAX_PDF_BYTES = 20 * 1024 * 1024  # 单张发票 PDF 上限
# 单封邮件最多处理的直链数：防恶意邮件塞大量链接放大出网/并发面（正常京东一封=1 张）。
MAX_LINKS_PER_EMAIL = 10
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; invoce-invoice-fetcher)"}

_HREF_RE = re.compile(r"""href=["'](https?://[^"']+)["']""", re.IGNORECASE)

LinkFetcher = Callable[[list[str]], Awaitable[list[bytes]]]


def is_allowed_host(host: str) -> bool:
    """host 是否命中白名单：精确等于 apex，或以「.<apex>」结尾（点边界防后缀伪装）。"""
    h = (host or "").strip().lower().rstrip(".")
    if not h:
        return False
    return any(h == suffix.lstrip(".") or h.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES)


def _accept_url(parsed: SplitResult) -> bool:
    """统一的可拉取性校验：https + 命中白名单 host + 端口仅 443（含缺省）。"""
    if parsed.scheme != "https" or not is_allowed_host(parsed.hostname or ""):
        return False
    try:
        port = parsed.port
    except ValueError:  # 端口非数字等畸形 URL
        return False
    return port in (None, 443)


def extract_invoice_pdf_links(html: str) -> list[str]:
    """从 HTML 正文抽出白名单内的发票 PDF 直链（https + 命中白名单 host + 路径以 .pdf 结尾）。

    会还原 &amp; 等 HTML 实体（否则 URL 查询参数/签名错乱）；保序去重。
    营销跳转链（tr.jd.com）、订阅链、以及 .xml 源数据链都不在此列。
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in _HREF_RE.findall(html or ""):
        url = html_module.unescape(raw)
        parsed = urlsplit(url)
        if not _accept_url(parsed) or not parsed.path.lower().endswith(".pdf"):
            continue
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


async def fetch_pdf(url: str, *, transport: httpx.AsyncBaseTransport | None = None) -> bytes | None:
    """安全下载单个白名单直链，校验通过返回 PDF 字节，任何不满足条件返回 None（绝不抛异常）。"""
    if not _accept_url(urlsplit(url)):
        return None
    # IP 兜底：解析落私有/内网段则拒绝。getaddrinfo 是阻塞调用，丢线程池避免阻塞事件循环。
    if not await asyncio.to_thread(netguard.is_safe_url, url):
        return None
    try:
        async with (
            httpx.AsyncClient(
                transport=transport, follow_redirects=False, timeout=_TIMEOUT, headers=_HEADERS
            ) as client,
            client.stream("GET", url) as resp,
        ):
            if resp.status_code != 200:
                return None
            ctype = resp.headers.get("content-type", "").lower()
            if ctype.startswith(("text/", "image/")):  # 提前挡掉登录页/营销页
                return None
            buf = bytearray()
            async for chunk in resp.aiter_bytes():
                buf.extend(chunk)  # 就地追加，避免副本
                if len(buf) > MAX_PDF_BYTES:
                    return None
    except (httpx.HTTPError, OSError):
        return None
    data = bytes(buf)
    return data if data[:4] == b"%PDF" else None


async def fetch_invoice_pdfs(urls: list[str]) -> list[bytes]:
    """并发拉取白名单直链（上限 MAX_LINKS_PER_EMAIL），跳过失败项，保序返回成功的 PDF 字节。"""
    capped = urls[:MAX_LINKS_PER_EMAIL]
    results = await asyncio.gather(*(fetch_pdf(u) for u in capped))
    return [data for data in results if data is not None]
