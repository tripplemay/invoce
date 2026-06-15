"""正文内嵌「免登录发票直链」的抽取与安全下载。

背景：部分商家（典型是京东）的发票邮件无 PDF 附件，而是把发票 PDF 以**免登录预签名直链**
放在 HTML 正文里（如 `https://<bucket>.s3.cn-north-1.jdcloud-oss.com/digital-invoice/digital_*.pdf?Signature=...`，
有效期长达数十年 ≈ 永久）。我们抽出这类直链并把 PDF 拉回来，喂进与普通附件相同的归集管线。

安全模型（关键）：**域名白名单为主控**——只拉取已知发票 CDN，绝不无差别跟随陌生链接，
从根上规避 SSRF/钓鱼（监管反复预警「发票」钓鱼邮件）。在白名单之上再叠多层防御：
- 只允许 http/https + host 命中白名单（精确或带点边界后缀，防 `*.evil.com` 伪装）+ 端口仅 80/443；
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

# 允许自动拉取的发票 CDN/下载端点（均实测免登录返回 %PDF）。域名白名单是 SSRF 主控边界，
# 只拉这些专用发票文件 host，绝不无差别跟链。新来源须先实测确认免登录直返 PDF 后再加。
#   - 后缀匹配（带前导点 → 强制点边界）：京东自营新版 *.jdcloud-oss.com、京东 POP *.jcloudcs.com；
#   - 精确匹配（无子域，避免 evilstorage.jd.com 这类误命中）：其余各家发票文件 host。
ALLOWED_HOST_EXACT: frozenset[str] = frozenset(
    {
        "storage.jd.com",  # 京东自营旧版
        "upload.fapiaoer.cn",  # 票易通（*.pdf 直链）
        "xz.bwfapiao.com",  # 百望 OSS（*.pdf，http）
        "inv.jss.com.cn",  # 诺诺/金税盘 文件服务（*.pdf）
        "einvoice.taobao.com",  # 阿里发票平台 token 下载 API
        "invoice.taobao.com",  # 阿里发票平台 token 下载 API
        "fp.baiwang.com",  # 百望直链下载端点（http）
        "fpkj.vpiaotong.com",  # 票通直链下载端点
    }
)
ALLOWED_HOST_SUFFIXES: tuple[str, ...] = (".jdcloud-oss.com", ".jcloudcs.com")
# 这些 host 的下载链接不以 .pdf 结尾（token/接口式端点），抽取时放行任意路径；fetch 仍以 %PDF 魔数兜底。
DOWNLOAD_ENDPOINT_HOSTS: frozenset[str] = frozenset(
    {"einvoice.taobao.com", "invoice.taobao.com", "fp.baiwang.com", "fpkj.vpiaotong.com"}
)
# 部分直链是 http（非 https，如 storage.jd.com / jcloudcs / 百望）。域名白名单是主控边界，故放行 http；
# 仍叠 netguard IP 兜底 + follow_redirects=False + %PDF 魔数 + 端口限，http 不放大 SSRF 面。
_ALLOWED_SCHEMES = ("https", "http")
_ALLOWED_PORTS = (None, 443, 80)

MAX_PDF_BYTES = 20 * 1024 * 1024  # 单张发票 PDF 上限
# 单封邮件最多处理的直链数：防恶意邮件塞大量链接放大出网/并发面（正常京东一封=1 张）。
MAX_LINKS_PER_EMAIL = 10
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; invoce-invoice-fetcher)"}

_HREF_RE = re.compile(r"""href=["'](https?://[^"']+)["']""", re.IGNORECASE)

LinkFetcher = Callable[[list[str]], Awaitable[list[bytes]]]


def is_allowed_host(host: str) -> bool:
    """host 是否命中白名单：精确命中 EXACT，或以白名单后缀「.<apex>」结尾（点边界防伪装）。"""
    h = (host or "").strip().lower().rstrip(".")
    if not h:
        return False
    return h in ALLOWED_HOST_EXACT or any(h.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES)


def _accept_url(parsed: SplitResult) -> bool:
    """统一的可拉取性校验：http/https + 命中白名单 host + 端口仅 80/443（含缺省）。"""
    if parsed.scheme not in _ALLOWED_SCHEMES or not is_allowed_host(parsed.hostname or ""):
        return False
    try:
        port = parsed.port
    except ValueError:  # 端口非数字等畸形 URL
        return False
    return port in _ALLOWED_PORTS


def extract_invoice_pdf_links(html: str) -> list[str]:
    """从 HTML 正文抽出白名单内的发票文件直链。命中条件：http/https + 命中白名单 host + 端口 80/443，
    且（路径以 .pdf 结尾 或 host 是 token/接口式下载端点）。

    会还原 &amp; 等 HTML 实体（否则 URL 查询参数/签名错乱）；保序去重。
    营销跳转链（tr.jd.com）、订阅链、以及 .xml 源数据链（与 .pdf 同 host）都不在此列。
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in _HREF_RE.findall(html or ""):
        url = html_module.unescape(raw)
        parsed = urlsplit(url)
        if not _accept_url(parsed):
            continue
        host = (parsed.hostname or "").strip().lower().rstrip(".")
        if not (parsed.path.lower().endswith(".pdf") or host in DOWNLOAD_ENDPOINT_HOSTS):
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
