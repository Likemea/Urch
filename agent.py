# Urch/agent.py

import time
import uuid
import discord
from typing import Optional
from functions.tools_schema import AGENT_TOOLS
from functions.dispatcher import dispatch_tool_call
from providers import MODELS, FALLBACK_MODEL_KEY, call_provider

MAX_STEPS = 5

def _format_status_for_tools(tool_names: list[str]) -> str:
    """Creates a user-friendly status update string for active tool calls."""
    if not tool_names:
        return "* 💡 Thinking..."
    
    parts = []
    for name in tool_names:
        if name == "web_search":
            parts.append("🔎 Searching")
        elif name == "fetch_webpage":
            parts.append("🌐 Reading page")
        elif name == "execute_code":
            parts.append("🐍 Running script")
        elif name == "generate_image":
            parts.append("🎨 Generating image")
        else:
            parts.append(f"🛠️ Executing {name}")
            
    return "* " + ", ".join(parts) + "..."

async def _safe_update_status(status_msg: Optional[discord.Message], text: str):
    """Safely edits the status indicator message if available."""
    if not status_msg:
        return
    try:
        await status_msg.edit(content=text)
    except Exception as e:
        print(f"[Agent] Status message edit failed: {e}")

async def run_agent_loop(
    chosen_key: str,
    base_messages: list,
    user_params: dict,
    status_message: Optional[discord.Message] = None
) -> dict:
    """
    Executes an autonomous ReAct loop using native function calling.
    Iterates up to MAX_STEPS = 5 times resolving tool calls until the model
    produces a final response or reaches loop.
    """
    start_time = time.perf_counter()
    model_info = MODELS.get(chosen_key, MODELS[FALLBACK_MODEL_KEY])
    model_used = model_info["id"]

    tooling_setting = user_params.get("tooling", "Auto")
    supports_tools = bool(model_info.get("tools", False)) and (tooling_setting != "False")

    messages = [dict(m) if isinstance(m, dict) else m for m in base_messages]

    payload = {
        "messages": messages,
        "temperature": user_params.get("temperature", 0.7),
        "top_p": user_params.get("top_p", 1),
        "max_completion_tokens": user_params.get("max_completion_tokens", 1000),
    }

    reasoning_val = user_params.get("reasoning", "none")
    if reasoning_val != "none" and model_info.get("reasoning_effort"):
        payload["reasoning_effort"] = reasoning_val

    if supports_tools:
        payload["tools"] = AGENT_TOOLS
        payload["tool_choice"] = "auto"

    context = {"files": []}
    final_text = ""
    terminated_normally = False

    for step in range(MAX_STEPS):
        try:
            resp, used_id = await call_provider(chosen_key, payload)
            model_used = used_id
        except Exception as e:
            print(f"[Agent] Provider call failed at step {step + 1}: {e}")
            final_text = f"⚠️ Inference error encountered: {str(e)}"
            break

        choices = resp.get("choices", [])
        if not choices:
            final_text = "⚠️ Empty response received from provider."
            break

        assistant_message = choices[0].get("message", {})
        content = assistant_message.get("content") or ""
        tool_calls = assistant_message.get("tool_calls") or []

        assistant_turn = {
            "role": "assistant",
            "content": content if content else None,
        }
        if tool_calls:
            assistant_turn["tool_calls"] = tool_calls
        payload["messages"].append(assistant_turn)

        # Condition A: No tool calls (terminal response reached)
        if not tool_calls or not supports_tools:
            final_text = content
            terminated_normally = True
            break

        # Condition B: Tool calls present
        tool_names = [
            tc.get("function", {}).get("name", "unknown")
            for tc in tool_calls if isinstance(tc, dict)
        ]
        status_text = _format_status_for_tools(tool_names)
        await _safe_update_status(status_message, status_text)

        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue

            call_id = tc.get("id") or f"call_{uuid.uuid4().hex[:8]}"
            fn_info = tc.get("function", {})
            fn_name = fn_info.get("name", "")
            fn_args = fn_info.get("arguments", "{}")

            print(f"[Agent] Step {step + 1} invoking tool: {fn_name}({fn_args[:100]}...)")
            tool_output, _ = await dispatch_tool_call(fn_name, fn_args, context)

            payload["messages"].append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": fn_name,
                "content": str(tool_output),
            })

    # Step ceiling reached with unresolved tools: finalize answer
    if not terminated_normally and supports_tools and not final_text:
        await _safe_update_status(status_message, "* 📝 Responding")
        final_payload = dict(payload)
        final_payload.pop("tools", None)
        final_payload.pop("tool_choice", None)
        final_payload["messages"] = list(payload["messages"]) + [
            {
                "role": "user",
                "content": "Summarize your findings so far into a final, comprehensive response for the user based on the tool outputs above."
            }
        ]
        try:
            resp, used_id = await call_provider(chosen_key, final_payload)
            model_used = used_id
            if resp.get("choices"):
                final_text = resp["choices"][0]["message"].get("content") or ""
            else:
                final_text = "*(Agent reached maximum steps but received no final response)*"
        except Exception as e:
            final_text = f"*(Agent reached maximum steps ({MAX_STEPS}) but encountered an error finalizing response: {e})*"

    elapsed = time.perf_counter() - start_time
    print(f"[Agent] Loop finished in {elapsed:.2f}s using {model_used}. Generated {len(context.get('files', []))} files.")

    return {
        "raw_response": final_text,
        "display_response": f"{final_text}\n" if final_text else "",
        "files": context.get("files", []),
        "model_used": model_used,
        "elapsed": elapsed,
    }
