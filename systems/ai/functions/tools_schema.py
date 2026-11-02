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
                        "description": "The search query to look up on the web.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results to return (default: 3, max: 10).",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
        },
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
                        "description": "The target webpage URL (must start with http:// or https://).",
                    }
                },
                "required": ["url"],
            },
        },
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
                        "description": "The complete, self-contained Python 3 script to execute.",
                    }
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_media",
            "description": "Generate media (image or audio) based on input specifications. When media_type is 'image', provide 'prompt' (and optionally 'model'). When media_type is 'audio', provide 'input' (and optionally 'voice' and 'speed').",
            "parameters": {
                "type": "object",
                "properties": {
                    "media_type": {
                        "type": "string",
                        "enum": ["image", "audio"],
                        "description": "The type of media to generate ('image' or 'audio').",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "A detailed text prompt describing the image to generate (required if media_type is 'image').",
                    },
                    "input": {
                        "type": "string",
                        "description": "The text to convert into speech/audio (required if media_type is 'audio').",
                    },
                    "model": {
                        "type": "string",
                        "description": "Model to use for image generation (e.g. 'dreamshaper', 'flux') or text-to-speech (defaults to 'openai/tts-1').",
                    },
                    "voice": {
                        "type": "string",
                        "description": "Voice for speech. (e.g. 'nova', 'alloy', 'echo', 'fable', 'onyx', 'shimmer'). Defaults to 'nova'.",
                        "default": "nova",
                    },
                    "speed": {
                        "type": "number",
                        "description": "Speaker speed. Minimum 0.25, maximum 4.0, default 1.0.",
                        "default": 1.0,
                    },
                },
                "required": ["media_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forum_post",
            "description": "Create a new post in the #urch-bot forum channel for community assistance, bug reporting, or feature suggestions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the forum post.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed body content/description of the forum post.",
                    },
                    "tag": {
                        "type": "string",
                        "enum": ["problem", "suggestion"],
                        "description": "Optional category tag for the forum post ('problem' or 'suggestion').",
                    },
                },
                "required": ["title", "description"],
            },
        },
    },
]
