# Urch/functions/web_fetch.py
"""
Webpage scraping engine for Urch.
Uses aiohttp and trafilatura (with fallback) to extract clean, LLM-friendly text.
Enforces SSRF defense (with DNS pinning via custom resolver to prevent TOCTOU rebinding
and IPv6 transitional address unwrapping), 1MB max response stream cap, an 8-second
HTTP timeout, and 4,000-character truncation ceiling.
"""

import aiohttp
import aiohttp.abc
import asyncio
import contextvars
import ipaddress
import re
import socket
from typing import Optional
from urllib.parse import urljoin, urlsplit

try:
    import trafilatura
except ImportError:
    trafilatura = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 UrchBot/2.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}

_NAT64_NETS = (
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("64:ff9b:1::/48"),
)

_pinned_dns_var: contextvars.ContextVar[Optional[dict[tuple[str, int], list[dict]]]] = (
    contextvars.ContextVar("_pinned_dns_var", default=None)
)


def _is_safe_ip(ip_str: str) -> bool:
    """Returns True if the IP is public/safe (not loopback, private, link-local, NAT64, or reserved)."""
    try:
        if "%" in ip_str:
            ip_str = ip_str.split("%", 1)[0]
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            if not _is_safe_ip(str(ip.ipv4_mapped)):
                return False
        if ip.sixtofour is not None:
            if not _is_safe_ip(str(ip.sixtofour)):
                return False
        if ip.teredo is not None:
            server_ip, client_ip = ip.teredo
            if not (_is_safe_ip(str(server_ip)) and _is_safe_ip(str(client_ip))):
                return False
        if any(ip in net for net in _NAT64_NETS):
            embedded_v4 = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
            if not _is_safe_ip(str(embedded_v4)):
                return False
            return False

    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or not ip.is_global
    )


class _SafePinnedResolver(aiohttp.abc.AbstractResolver):
    """
    SSRF-safe aiohttp resolver that serves pre-validated DNS records pinned by
    _resolve_and_check_url, eliminating the TOCTOU window between validation and connect().
    """

    def __init__(self, pinned: dict[tuple[str, int], list[dict]]):
        self._pinned = pinned

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_UNSPEC) -> list[dict]:
        key = (host.lower(), port)
        if key in self._pinned and self._pinned[key]:
            return self._pinned[key]

        loop = asyncio.get_running_loop()
        addrinfo = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM, family=family)
        if not addrinfo:
            raise OSError(f"No DNS records found for '{host}'")

        records = []
        for entry in addrinfo:
            af, _, proto, _, sockaddr = entry
            ip_str = sockaddr[0]
            if not _is_safe_ip(ip_str):
                raise PermissionError(
                    f"Access to private/restricted IP addresses ({ip_str}) is forbidden."
                )
            records.append(
                {
                    "hostname": host,
                    "host": ip_str,
                    "port": port,
                    "family": af,
                    "proto": proto,
                    "flags": socket.AI_NUMERICHOST | socket.AI_NUMERICSERV,
                }
            )
        self._pinned[key] = records
        return records

    async def close(self) -> None:
        self._pinned.clear()


async def _resolve_and_check_url(url: str) -> tuple[bool, str]:
    """
    Validates URL scheme and resolves hostname, rejecting private/loopback/link-local/metadata IPs.
    Pins validated IP addresses into the active request context to prevent TOCTOU DNS rebinding.
    Returns (is_safe, error_message).
    """
    try:
        parsed = urlsplit(url)
    except Exception as e:
        return False, f"Invalid URL format: {e}"

    if parsed.scheme not in ("http", "https"):
        return False, f"URL scheme must be http or https (received: '{parsed.scheme}')"

    hostname = parsed.hostname
    if not hostname:
        return False, "URL missing valid hostname"

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as e:
        return False, f"Invalid URL port: {e}"

    pinned = _pinned_dns_var.get()

    # Check if hostname itself is directly an IP address literal
    try:
        ip = ipaddress.ip_address(hostname)
        if not _is_safe_ip(str(ip)):
            return False, f"Access to private/restricted IP addresses ({hostname}) is forbidden."
        if pinned is not None:
            af = socket.AF_INET6 if isinstance(ip, ipaddress.IPv6Address) else socket.AF_INET
            pinned[(hostname.lower(), port)] = [
                {
                    "hostname": hostname,
                    "host": str(ip),
                    "port": port,
                    "family": af,
                    "proto": socket.IPPROTO_TCP,
                    "flags": socket.AI_NUMERICHOST | socket.AI_NUMERICSERV,
                }
            ]
        return True, ""
    except ValueError:
        pass

    # Resolve hostname via getaddrinfo
    loop = asyncio.get_running_loop()
    try:
        addrinfo = await loop.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        return False, f"Failed to resolve hostname '{hostname}': {e}"
    except Exception as e:
        return False, f"DNS resolution error for '{hostname}': {e}"

    if not addrinfo:
        return False, f"No DNS records found for '{hostname}'"

    records = []
    for entry in addrinfo:
        af, _, proto, _, sockaddr = entry
        ip_str = sockaddr[0]
        if not _is_safe_ip(ip_str):
            return False, f"Access to private/restricted IP addresses ({ip_str}) is forbidden."
        records.append(
            {
                "hostname": hostname,
                "host": ip_str,
                "port": port,
                "family": af,
                "proto": proto,
                "flags": socket.AI_NUMERICHOST | socket.AI_NUMERICSERV,
            }
        )

    if pinned is not None:
        pinned[(hostname.lower(), port)] = records

    return True, ""


def _clean_html_fallback(html: str) -> str:
    """Strips common non-content tags and returns normalized whitespace text."""
    cleaned = re.sub(
        r"<(script|style|svg|footer|header|nav|noscript|aside)[^>]*>.*?</\1>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = (
        cleaned.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )
    return " ".join(cleaned.split())


async def fetch_webpage(url: str) -> str:
    """
    Fetches a webpage, cleans its HTML, and returns readable extracted text
    truncated to 4,000 characters.
    Enforces SSRF protection (pinned DNS resolution + peername verification)
    and a 1 MB body limit to protect against OOM.
    """
    url = url.strip()
    pinned_records: dict[tuple[str, int], list[dict]] = {}
    token = _pinned_dns_var.set(pinned_records)

    try:
        is_safe, err_msg = await _resolve_and_check_url(url)
        if not is_safe:
            return f"Error: {err_msg}"

        timeout = aiohttp.ClientTimeout(total=8.0)
        max_redirects = 5
        current_url = url
        connector = aiohttp.TCPConnector(
            resolver=_SafePinnedResolver(pinned_records),
            force_close=True,
        )

        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                for _ in range(max_redirects):
                    async with session.get(
                        current_url,
                        headers=HEADERS,
                        allow_redirects=False,
                        timeout=timeout,
                    ) as resp:
                        peername = None
                        if resp.connection and resp.connection.transport:
                            peername = resp.connection.transport.get_extra_info("peername")
                        if peername:
                            peer_ip = peername[0]
                            if not _is_safe_ip(peer_ip):
                                return (
                                    f"Error: Access to private/restricted IP addresses "
                                    f"({peer_ip}) is forbidden."
                                )

                        if resp.status in (301, 302, 303, 307, 308):
                            location = resp.headers.get("Location")
                            if not location:
                                return f"Error: Redirect with no Location header from {current_url}"
                            next_url = urljoin(current_url, location)
                            is_safe, err_msg = await _resolve_and_check_url(next_url)
                            if not is_safe:
                                return f"Error: Redirect blocked: {err_msg}"
                            current_url = next_url
                            continue

                        if resp.status != 200:
                            return f"Error: HTTP {resp.status} when accessing {current_url}"

                        content_type = resp.headers.get("Content-Type", "").lower()
                        allowed_types = [
                            "text/html",
                            "text/plain",
                            "application/xhtml+xml",
                            "application/xml",
                            "application/json",
                        ]
                        if not any(t in content_type for t in allowed_types):
                            return (
                                f"Error: Unsupported Content-Type '{content_type}'. "
                                "Urch only extracts text/HTML pages."
                            )

                        # Stream-read up to 1 MB maximum to prevent OOM
                        max_bytes = 1024 * 1024
                        raw_bytes = await resp.content.read(max_bytes)
                        charset = resp.charset or "utf-8"
                        html_text = raw_bytes.decode(charset, errors="replace")
                        break
                else:
                    return f"Error: Exceeded maximum redirects ({max_redirects})"
        finally:
            await connector.close()

        def _extract_text_worker(html: str, target_url: str) -> str:
            res = None
            if trafilatura is not None:
                try:
                    res = trafilatura.extract(
                        html,
                        url=target_url,
                        include_links=True,
                        include_comments=False,
                        output_format="txt",
                    )
                except Exception:
                    res = None
            if not res:
                res = _clean_html_fallback(html)
            return (res or "").strip()

        extracted = await asyncio.to_thread(_extract_text_worker, html_text, current_url)

        if not extracted:
            return f"Notice: No readable text content could be extracted from {current_url}."

        if len(extracted) > 4000:
            extracted = extracted[:4000] + "\n\n... [Content truncated at 4000 characters]"

        return extracted

    except asyncio.TimeoutError:
        return f"Error: Request timed out (8.0s limit reached) while fetching {current_url}"
    except Exception as e:
        return f"Error fetching webpage {current_url}: {str(e)}"
    finally:
        _pinned_dns_var.reset(token)
