"""SSRF 防护：拒绝指向私有/内网地址的 URL 与主机。"""

import ipaddress
import socket
from urllib.parse import urlparse


def _is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def is_safe_host(host: str) -> bool:
    """解析主机名，任一地址落在私有/内网段则判定不安全。"""
    if not host:
        return False
    # 字面 IP 直接判断
    try:
        ipaddress.ip_address(host)
        return not _is_private_ip(host)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    return all(not _is_private_ip(str(info[4][0])) for info in infos)


def is_blocked_literal_host(host: str) -> bool:
    """仅按字面判断（不做 DNS）：localhost 或字面私有 IP 视为被禁。"""
    h = (host or "").strip().lower()
    if h in ("", "localhost"):
        return True
    return _is_private_ip(h)


def is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    return is_safe_host(parsed.hostname)
