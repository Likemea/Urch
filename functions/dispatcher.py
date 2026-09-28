# Urch/functions/dispatcher.py
"""
Asynchronous executor and dispatcher mapping LLM function calls to tool implementations.
Manages argument parsing, execution safety, and delivery queue attachments.
"""

import json
from typing import Any, Tuple
from functions.web_search import web_search
from functions.web_fetch import fetch_webpage
from functions.code_interpreter import run_sandboxed_python
from functions.image_gen import generate_image


async def dispatch_tool_call(tool_name: str, arguments_json: str, context: dict) -> Tuple[str, Any]:
    """
    Parses arguments, routes to appropriate function, and returns (result_text, optional_file_object).
    Context dict holds shared state (e.g., 'files' list for Discord attachments).
    """
    if isinstance(arguments_json, dict):
        args = arguments_json
    else:
        try:
            args = json.loads(arguments_json) if arguments_json else {}
        except Exception:
            return "Error: Invalid JSON arguments provided.", None

    if not isinstance(args, dict):
        return "Error: Invalid JSON arguments provided. Expected an object.", None

    try:
        if tool_name == "web_search":
            query = args.get("query", "")
            max_results = args.get("max_results", 3)
            try:
                max_results = int(max_results)
            except (ValueError, TypeError):
                max_results = 3
            output_text = await web_search(query, max_results=max_results)
            return output_text, None

        elif tool_name == "fetch_webpage":
            url = args.get("url", "")
            output_text = await fetch_webpage(url)
            return output_text, None

        elif tool_name == "execute_code":
            code = args.get("code", "")
            output_text, generated_files = await run_sandboxed_python(code)
            if generated_files:
                context.setdefault("files", []).extend(generated_files)
            return output_text, generated_files

        elif tool_name == "generate_image":
            prompt = args.get("prompt", "")
            model = args.get("model", "dreamshaper")
            discord_file = await generate_image(prompt=prompt, model=model)
            if discord_file:
                context.setdefault("files", []).append(discord_file)
                output_text = (
                    f"Successfully generated image using model '{model}' for prompt '{prompt}'. "
                    f"The image has been attached to the delivery queue."
                )
                return output_text, discord_file
            else:
                return (
                    f"Error: Failed to generate image using model '{model}' due to an API error.",
                    None,
                )

        else:
            return f"Error: Unknown tool '{tool_name}'.", None

    except Exception as e:
        return f"Error executing tool '{tool_name}': {str(e)}", None
