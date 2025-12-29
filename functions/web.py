# Urch/functions/web.py
from ddgs import DDGS

async def web_search(query: str, max_results=3):
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "url": r.get("href", ""),
                    "content": r.get("body", "")[:768]
                })
        return results if results else [{'url': '', 'content': 'No results found.'}]
    except Exception as e:
        return [{'url': '', 'content': f'Error occurred: {str(e)}'}]
