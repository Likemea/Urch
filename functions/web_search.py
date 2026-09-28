# Urch/functions/web_search.py
"""
Search engine integration using DuckDuckGo (ddgs).
Returns structured titles, URLs, and snippets.
"""

import asyncio
from ddgs import DDGS


def _ddgs_search_sync(query: str, max_results: int = 3) -> list[dict]:
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(
                {
                    "title": r.get("title", "No Title"),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
            )
    return results


async def web_search(query: str, max_results: int = 3) -> str:
    """
    Searches DuckDuckGo and returns formatted results containing title, URL,
    and snippet for each match.
    """
    query = query.strip()
    if not query:
        return "Error: Empty search query provided."

    try:
        raw_results = await asyncio.to_thread(_ddgs_search_sync, query, max_results)
        if not raw_results:
            return f"No search results found for query: '{query}'."

        formatted_entries = []
        for i, item in enumerate(raw_results, 1):
            title = item.get("title", "No title")
            url = item.get("url", "")
            snippet = item.get("snippet", "").strip()
            formatted_entries.append(f"[{i}] {title}\nURL: {url}\nSnippet: {snippet}")

        return "\n\n".join(formatted_entries)
    except Exception as e:
        return f"Error executing web search for '{query}': {str(e)}"
