# Urch/functions/web_fetch.py
"""
Webpage scraping engine for Urch.
Uses aiohttp and trafilatura (with fallback) to extract clean, LLM-friendly text.
Enforces an 8-second HTTP timeout and 4,000-character truncation ceiling.
"""

import aiohttp
import asyncio
import re
from typing import Optional

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

def _clean_html_fallback(html: str) -> str:
    """Strips common non-content tags and returns normalized whitespace text."""
    cleaned = re.sub(
        r"<(script|style|svg|footer|header|nav|noscript|aside)[^>]*>.*?</\1>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE
    )
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = cleaned.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return " ".join(cleaned.split())

async def fetch_webpage(url: str) -> str:
    """
    Fetches a webpage, cleans its HTML, and returns readable extracted text
    truncated to 4,000 characters.
    """
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        return f"Error: URL must start with http:// or https:// (received: '{url}')"

    timeout = aiohttp.ClientTimeout(total=8.0)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=HEADERS, allow_redirects=True) as resp:
                if resp.status != 200:
                    return f"Error: HTTP {resp.status} when accessing {url}"

                content_type = resp.headers.get("Content-Type", "").lower()
                allowed_types = ["text/html", "text/plain", "application/xhtml+xml", "application/xml", "application/json"]
                if not any(t in content_type for t in allowed_types):
                    return f"Error: Unsupported Content-Type '{content_type}'. Urch only extracts text/HTML pages."

                raw_bytes = await resp.read()
                charset = resp.charset or "utf-8"
                html_text = raw_bytes.decode(charset, errors="replace")

        extracted: Optional[str] = None
        if trafilatura is not None:
            extracted = trafilatura.extract(
                html_text,
                url=url,
                include_links=True,
                include_comments=False,
                output_format="txt"
            )

        if not extracted:
            extracted = _clean_html_fallback(html_text)

        extracted = extracted.strip()
        if not extracted:
            return f"Notice: No readable text content could be extracted from {url}."

        if len(extracted) > 4000:
            extracted = extracted[:4000] + "\n\n... [Content truncated at 4000 characters]"

        return extracted

    except asyncio.TimeoutError:
        return f"Error: Request timed out (8.0s limit reached) while fetching {url}"
    except Exception as e:
        return f"Error fetching webpage {url}: {str(e)}"
