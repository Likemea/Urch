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
from functions.audio_gen import generate_audio
from functions.forum_post import create_forum_post
from safeguard import check_safeguard


async def dispatch_tool_call(tool_name: str, arguments_json: str, context: dict) -> Tuple[str, Any]:
    """
    Parses arguments, routes to appropriate function, and returns (result_text, optional_file_object).
    Context dict holds shared state (e.g., 'files' list for Discord attachments, 'bot' reference).
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

        elif tool_name in ["generate_media", "generate_image", "generate_audio"]:
            media_type = str(args.get("media_type", "image")).lower()
            if tool_name == "generate_image":
                media_type = "image"
            elif tool_name == "generate_audio":
                media_type = "audio"

            bot = context.get("bot")
            safeguard_func = (
                getattr(bot, "check_safeguard", check_safeguard) if bot else check_safeguard
            )

            if media_type == "audio":
                input_text = args.get("input") or args.get("prompt", "")
                if not input_text:
                    return "Error: 'input' argument is required when media_type is 'audio'.", None

                try:
                    safeguard_result = await safeguard_func([], str(input_text), "")
                    verdict = safeguard_result.get("verdict", "safe").lower()
                    if verdict in ["unsafe_input", "unsafe_output", "unsafe_both"]:
                        reason = safeguard_result.get("reasoning", "Content flagged as unsafe.")
                        policy = safeguard_result.get("violated_policy", "Unspecified policy.")
                        return (
                            f"Error: Audio generation blocked by safeguard policy ({policy}): {reason}",
                            None,
                        )
                except Exception as e:
                    print(f"[Dispatcher] Audio safeguard evaluation error: {e}")

                voice = args.get("voice", "nova")
                speed = args.get("speed", 1.0)
                model = args.get("model", "openai/tts-1")

                discord_file = await generate_audio(
                    input_text=input_text, voice=voice, speed=speed, model=model
                )
                if discord_file:
                    context.setdefault("files", []).append(discord_file)
                    output_text = (
                        f"Successfully generated speech using '{model}', voice '{voice}', "
                        f"speed {speed} for text: '{input_text[:100]}...'. "
                        f"The audio file has been attached to the delivery queue."
                    )
                    return output_text, discord_file
                else:
                    return (
                        f"Error: Failed to generate audio using model '{model}' due to API error.",
                        None,
                    )

            elif media_type == "image":
                prompt = args.get("prompt") or args.get("input", "")
                if not prompt:
                    return "Error: 'prompt' argument is required when media_type is 'image'.", None

                try:
                    safeguard_result = await safeguard_func([], str(prompt), "")
                    verdict = safeguard_result.get("verdict", "safe").lower()
                    if verdict in ["unsafe_input", "unsafe_output", "unsafe_both"]:
                        reason = safeguard_result.get("reasoning", "Content flagged as unsafe.")
                        policy = safeguard_result.get("violated_policy", "Unspecified policy.")
                        return (
                            f"Error: Image generation blocked by safeguard policy ({policy}): {reason}",
                            None,
                        )
                except Exception as e:
                    print(f"[Dispatcher] Image safeguard evaluation error: {e}")

                model = args.get("model", "dreamshaper")
                discord_file = await generate_image(prompt=prompt, model=model)
                if discord_file:
                    context.setdefault("files", []).append(discord_file)
                    output_text = (
                        f"Successfully generated '{prompt}' using '{model}'."
                        f"The image has been attached to the delivery queue."
                    )
                    return output_text, discord_file
                else:
                    return (
                        f"Error: Failed to generate image using '{model}' due to API error.",
                        None,
                    )
            else:
                return (
                    f"Error: Unsupported media_type '{media_type}'. Valid media types are 'image' or 'audio'.",
                    None,
                )

        elif tool_name == "forum_post":
            title = args.get("title", "")
            description = args.get("description", "")
            tag = args.get("tag", None)

            bot = context.get("bot")
            if not bot:
                try:
                    import main

                    bot = getattr(main, "bot", None)
                except Exception:
                    bot = None

            user_id = context.get("user_id")
            result_str, thread = await create_forum_post(
                bot=bot, title=title, description=description, tag=tag, user_id=user_id
            )
            return result_str, thread

        else:
            return f"Error: Unknown tool '{tool_name}'.", None

    except Exception as e:
        return f"Error executing tool '{tool_name}': {str(e)}", None
