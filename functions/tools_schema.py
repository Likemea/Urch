# Urch/functions/tools_schema.py
"""
Central JSON schema registry conforming to the OpenAI function calling specification.
Used by the agentic ReAct loop for tool-capable models.
"""

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using DuckDuckGo to find real-time information, facts, current events, and documentation. Returns titles, URLs, and text snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up on the web."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results to return (default: 3, max: 10).",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_webpage",
            "description": "Fetch and extract readable text content from a specific webpage URL. Use this after web_search to inspect full articles, documentation, release notes, or raw webpage text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The target webpage URL (must start with http:// or https://)."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "Execute Python 3 scripts for calculations, data analysis, and generating charts. Save plots to the local directory (e.g., plt.savefig('plot.png')). Outbound networking is disabled.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The complete, self-contained Python 3 script to execute."
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate an image via Pollinations.ai based on a descriptive prompt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "A detailed text prompt describing the image to generate."
                    },
                    "model": {
                        "type": "string",
                        "description": "Image model to use. Options: 'dreamshaper', 'flux'. Defaults to 'dreamshaper'.",
                        "default": "dreamshaper"
                    }
                },
                "required": ["prompt"]
            }
        }
    }
]
