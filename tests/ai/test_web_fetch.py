# tests/ai/test_web_fetch.py
"""
Tests for outbound web fetching SSRF defenses, IPv4-mapped/transitional IPv6 blocking,
and SafePinnedResolver TOCTOU DNS rebinding protection.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

import systems.ai.functions.web_fetch as web_fetch_module
from systems.ai.functions.web_fetch import (
    _SafePinnedResolver,
    _is_safe_ip,
    _pinned_dns_var,
    _resolve_and_check_url,
    fetch_webpage,
)


@pytest.mark.asyncio
async def test_web_fetch_ssrf_blocking():
    """Verifies that private, loopback, link-local and reserved IP addresses are blocked."""
    assert _is_safe_ip("127.0.0.1") is False
    assert _is_safe_ip("10.0.0.1") is False
    assert _is_safe_ip("192.168.1.1") is False
    assert _is_safe_ip("172.16.0.1") is False
    assert _is_safe_ip("169.254.169.254") is False
    assert _is_safe_ip("::1") is False
    assert _is_safe_ip("0.0.0.0") is False
    assert _is_safe_ip("8.8.8.8") is True

    safe, err = await _resolve_and_check_url("http://127.0.0.1:8080/secret")
    assert safe is False
    assert "forbidden" in err

    safe, err = await _resolve_and_check_url("http://169.254.169.254/computeMetadata/v1/")
    assert safe is False
    assert "forbidden" in err

    safe, err = await _resolve_and_check_url("ftp://example.com/file")
    assert safe is False
    assert "must be http or https" in err

    result = await fetch_webpage("http://127.0.0.1:5000")
    assert "Error: Access to private/restricted IP addresses" in result


def test_web_fetch_ipv4_mapped_and_transitional_ipv6_blocked():
    assert _is_safe_ip("::ffff:127.0.0.1") is False
    assert _is_safe_ip("::ffff:169.254.169.254") is False
    assert _is_safe_ip("::ffff:10.0.0.1") is False
    assert _is_safe_ip("::ffff:192.168.1.1") is False
    assert _is_safe_ip("64:ff9b::127.0.0.1") is False
    assert _is_safe_ip("64:ff9b::169.254.169.254") is False
    assert _is_safe_ip("2002:7f00:0001::1") is False
    assert _is_safe_ip("fe80::1%eth0") is False
    assert _is_safe_ip("::ffff:8.8.8.8") is True
    assert _is_safe_ip("2606:4700:4700::1111") is True


@pytest.mark.asyncio
async def test_web_fetch_dns_pinning_prevents_toctou_rebinding():
    pinned = {}
    token = _pinned_dns_var.set(pinned)
    try:
        fake_addrinfo = [(2, 1, 6, "", ("93.184.216.34", 80))]
        loop = asyncio.get_running_loop()
        with patch.object(loop, "getaddrinfo", AsyncMock(return_value=fake_addrinfo)) as mock_gai:
            ok, err = await _resolve_and_check_url("http://example.com/test")
            assert ok is True
            assert err == ""
            assert ("example.com", 80) in pinned
            assert mock_gai.call_count == 1

            resolver = _SafePinnedResolver(pinned)
            resolved = await resolver.resolve("example.com", 80)
            assert len(resolved) == 1
            assert resolved[0]["host"] == "93.184.216.34"
            assert mock_gai.call_count == 1

        evil_addrinfo = [(2, 1, 6, "", ("169.254.169.254", 80))]
        with patch.object(loop, "getaddrinfo", AsyncMock(return_value=evil_addrinfo)):
            resolver2 = _SafePinnedResolver({})
            with pytest.raises(PermissionError, match="forbidden"):
                await resolver2.resolve("rebind.attacker.com", 80)
    finally:
        _pinned_dns_var.reset(token)


@pytest.mark.asyncio
async def test_web_fetch_dns_rebinding_protection():
    """Verify fetch_webpage aborts if socket peer IP is private/loopback."""
    mock_transport = MagicMock()
    mock_transport.get_extra_info.return_value = ("127.0.0.1", 80)
    mock_connection = MagicMock()
    mock_connection.transport = mock_transport

    mock_resp = AsyncMock()
    mock_resp.connection = mock_connection
    mock_resp.status = 200

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch(
        "systems.ai.functions.web_fetch._resolve_and_check_url",
        AsyncMock(return_value=(True, None)),
    ):
        with patch("aiohttp.ClientSession", return_value=mock_session):
            res = await web_fetch_module.fetch_webpage("http://evil-rebind.com")
            assert "Access to private/restricted IP addresses" in res
