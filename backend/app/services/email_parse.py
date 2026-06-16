"""邮件解析（纯函数，可测）：关键词匹配 + 提取标准发票文件（松散附件 / zip 内 PDF / 内嵌 Base64 图）。"""

import base64
import contextlib
import io
import re
import zipfile
from email.header import decode_header
from email.message import Message

KEYWORDS = ("发票", "电子发票", "行程单", "invoice")

# 非标准发票的噪音文件名关键词：汇总单 / 行程单·行程报销单 / 报销单 / 账单 / 对账单 /
# 运单·明细（运单明细、费用明细等清单类）等都不是标准发票，这类松散附件常与真发票同邮件出现
# （如美团“电子发票+行程单”、通行费“发票zip+汇总单”、顺丰“电子发票+发票运单明细”），需按文件名剔除。
_NOISE_FILENAME_KEYWORDS = ("汇总单", "行程", "报销单", "账单", "对账", "明细", "运单")

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
}

# zip 解压防护：避免畸形/恶意 zip 撑爆内存（原始包大小 / 扫描条目数 / 单 PDF / 聚合解压总量 / 取数）。
_MAX_ZIP_RAW_BYTES = 64 * 1024 * 1024
_MAX_ZIP_ENTRIES = 500
_MAX_ZIP_PDF_BYTES = 30 * 1024 * 1024
_MAX_ZIP_TOTAL_BYTES = 120 * 1024 * 1024
_MAX_ZIP_PDFS = 200


def is_noise_filename(filename: str | None) -> bool:
    """文件名是否为非标准发票（汇总单/行程单/账单等）。判定只看文件名本身（已 basename）。"""
    if not filename:
        return False
    return any(k in filename for k in _NOISE_FILENAME_KEYWORDS)


def _sniff_type(data: bytes) -> str | None:
    """按文件魔数识别类型，不信任邮件声明的 Content-Type（国产发票平台常用 octet-stream）。"""
    if data[:4] == b"%PDF":
        return "application/pdf"
    if data[:4] == b"PK\x03\x04":
        return "application/zip"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    return None


def _zip_member_basename(info: "zipfile.ZipInfo") -> str:
    """取 zip 条目的真实文件名（basename）：非 UTF-8 标志位时 zipfile 用 cp437 解码，需还原成 gbk。"""
    name = info.filename
    if not (info.flag_bits & 0x800):
        with contextlib.suppress(UnicodeEncodeError, UnicodeDecodeError):
            name = name.encode("cp437").decode("gbk")
    return name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]


_DATA_URI_RE = re.compile(r"data:(image/(?:png|jpe?g));base64,([A-Za-z0-9+/=\s]+)", re.IGNORECASE)
_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', re.IGNORECASE)


def _decode_bytes(data: bytes, charset: str | None) -> str:
    """容错解码：声明的 charset 非法(如 unknown-8bit)时逐个回退，绝不抛异常。"""
    for enc in (charset, "utf-8", "gbk", "latin-1"):
        if not enc:
            continue
        try:
            return data.decode(enc, errors="ignore")
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("latin-1", errors="ignore")


def decode_mime_header(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        decoded = decode_header(raw)
    except Exception:  # noqa: BLE001 头部畸形时退化为原文，绝不让一封坏邮件中断整批归集
        return str(raw)
    parts = []
    for value, charset in decoded:
        if isinstance(value, bytes | bytearray):
            parts.append(_decode_bytes(bytes(value), charset))
        else:
            parts.append(value)
    return "".join(parts)


def _norm_ctype(ctype: str) -> str:
    return "image/jpeg" if ctype.lower() in ("image/jpg",) else ctype.lower()


def matches_keywords(subject: str, body: str) -> bool:
    hay = f"{subject or ''} {body or ''}".lower()
    return any(k.lower() in hay for k in KEYWORDS)


def body_text(msg: Message) -> str:
    """收集 text/plain 与 text/html（粗略去标签）文本，用于关键词匹配。"""
    chunks: list[str] = []
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype in ("text/plain", "text/html"):
            payload = part.get_payload(decode=True)
            if not isinstance(payload, bytes | bytearray):
                continue
            text = bytes(payload).decode(part.get_content_charset() or "utf-8", errors="ignore")
            if ctype == "text/html":
                text = re.sub(r"<[^>]+>", " ", text)
            chunks.append(text)
    return " ".join(chunks)


def html_parts(msg: Message) -> list[str]:
    out: list[str] = []
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes | bytearray):
                out.append(
                    bytes(payload).decode(part.get_content_charset() or "utf-8", errors="ignore")
                )
    return out


def extract_attachments(msg: Message) -> list[tuple[bytes, str]]:
    """提取松散的 PDF / 图片发票附件。

    按文件魔数识别类型（不信任声明的 Content-Type，国产发票平台常以 octet-stream 投递），
    跳过汇总单/行程单/账单等噪音文件名；zip 附件交由 extract_zip_pdfs 处理。
    """
    files: list[tuple[bytes, str]] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        raw_fn = part.get_filename()
        filename = decode_mime_header(raw_fn) if raw_fn else None
        disposition = part.get_content_disposition()
        # 只看“附件类”部件：显式 attachment 或带文件名（排除正文 text 部件）。
        if disposition != "attachment" and not filename:
            continue
        if is_noise_filename(filename):
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes | bytearray) or not payload:
            continue
        data = bytes(payload)
        sniffed = _sniff_type(data)
        if sniffed == "application/pdf":
            files.append((data, "application/pdf"))
        elif sniffed in ("image/png", "image/jpeg") and disposition == "attachment":
            # 图片仅收真正的附件，排除 HTML 内联 cid 图（签名/logo/banner 常被误当发票）。
            files.append((data, sniffed))
        # zip / 其它类型在此忽略。
    return files


def describe_candidate_files(msg: Message) -> list[str]:
    """诊断用：列出邮件里“像附件”的部件及判定结果（文件名 / 魔数 / 是否噪音 / 大小）。

    仅用于“收到邮件但 0 入库”时给出可读原因（OFD/噪音文件名/非 PDF 魔数/内联图等），不参与入库决策。
    """
    out: list[str] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        raw_fn = part.get_filename()
        filename = decode_mime_header(raw_fn) if raw_fn else None
        disposition = part.get_content_disposition()
        if disposition != "attachment" and not filename:
            continue  # 正文部件
        payload = part.get_payload(decode=True)
        size = len(payload) if isinstance(payload, bytes | bytearray) else 0
        sniff = _sniff_type(bytes(payload)) if size else None
        if is_noise_filename(filename):
            reason = "噪音文件名(明细/账单等)被剔"
        elif sniff == "application/pdf":
            reason = "PDF✓"
        elif sniff == "application/zip":
            reason = "zip(取其中PDF)"
        elif sniff in ("image/png", "image/jpeg"):
            reason = "图片附件✓" if disposition == "attachment" else "内联图忽略"
        else:
            reason = f"非PDF/图(魔数={sniff or '未知'})"
        out.append(f"{filename or part.get_content_type()}[{reason},{size}B]")
    return out


def extract_zip_pdfs(msg: Message) -> list[tuple[bytes, str]]:
    """从 zip 附件中解出标准发票 PDF。

    中国电子发票常把同一批发票的 pdf/ofd/xml 打包成 zip（如通行费电子发票.zip，一个 zip 可能含多张发票）。
    只取其中的 PDF（OFD/XML 忽略，PDF 足够 AI 识别），并按文件名跳过 zip 内的汇总单/行程单等噪音。
    """
    files: list[tuple[bytes, str]] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes | bytearray):
            continue
        for pdf in pdfs_from_zip_bytes(bytes(payload)):
            files.append((pdf, "application/pdf"))
    return files


def pdfs_from_zip_bytes(data: bytes) -> list[bytes]:
    """从 zip 原始字节解出标准发票 PDF（邮件附件与手动上传 ZIP 共用）。

    按魔数识别 zip（不依赖后缀），按 basename(含 GBK 解码) 跳过汇总单/行程单等噪音，
    并设原始包大小 / 扫描条目数 / 单 PDF / 聚合解压总量 / 取数 多重上限，防畸形 zip 撑爆内存。
    """
    pdfs: list[bytes] = []
    if data[:4] != b"PK\x03\x04" or len(data) > _MAX_ZIP_RAW_BYTES:
        return pdfs
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        infos = archive.infolist()[:_MAX_ZIP_ENTRIES]
    except (zipfile.BadZipFile, OSError):
        return pdfs
    total = 0
    for info in infos:
        member = _zip_member_basename(info)
        if not member.lower().endswith(".pdf") or is_noise_filename(member):
            continue
        if info.file_size > _MAX_ZIP_PDF_BYTES:
            continue  # 防 zip 炸弹：跳过解压后异常大的条目
        try:
            pdf = archive.read(info)
        except (zipfile.BadZipFile, RuntimeError, OSError):
            continue  # 加密/损坏的条目跳过，不阻断其它发票
        if not pdf:
            continue
        total += len(pdf)
        if total > _MAX_ZIP_TOTAL_BYTES:
            break  # 聚合解压超预算，停止
        pdfs.append(pdf)
        if len(pdfs) >= _MAX_ZIP_PDFS:
            break
    return pdfs


def extract_inline_base64_images(html: str) -> list[tuple[bytes, str]]:
    files: list[tuple[bytes, str]] = []
    for m in _DATA_URI_RE.finditer(html):
        ctype = _norm_ctype(m.group(1))
        try:
            data = base64.b64decode(re.sub(r"\s", "", m.group(2)))
            files.append((data, ctype))
        except (ValueError, TypeError):
            continue
    return files


def extract_external_image_urls(html: str) -> list[str]:
    return _IMG_SRC_RE.findall(html)
