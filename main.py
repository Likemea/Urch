# Urch/main.py
import config

try:
    import uvloop

    uvloop.install()
except ImportError:
    pass
import asyncio
import json
import os
import time
from database import db
from backup import backup_database

import discord
from discord.ext import commands, tasks

from utils import (
    get_user_ai_params,
    get_messages_for_context,
    append_message_for_context,
    DEFAULT_AI_PARAMS,
    update_message_in_history,
    delete_message_from_history,
    check_reaction_permission,
    get_context_for_message,
    get_original_author_for_message,
    get_message_ids_for_reply,
    process_autorolls,
    log_rare_roll,
)
from providers import (
    MODELS,
    call_model_direct,
    call_provider_stream,
    close_session,
)
from agent import run_agent_loop

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True


class UrchBot(commands.Bot):
    async def setup_hook(self):
        # Runs exactly once after login (unlike on_ready, which fires on every reconnect).
        await initialize_database()
        await load_extensions()
        autoroll_heartbeat.start()
        db_backup_loop.start()

    async def close(self):
        print("Shutting down bot and cleaning up resources...")
        for loop in (autoroll_heartbeat, db_backup_loop):
            loop.cancel()
        try:
            await close_session()
            print("✅ HTTP session closed.")
        except Exception as e:
            print(f"Error closing HTTP session: {e}")
        try:
            await db.close()
            print("✅ Database connection closed.")
        except Exception as e:
            print(f"Error closing database connection: {e}")
        await super().close()


bot = UrchBot(command_prefix="!", intents=intents)


async def initialize_database():
    print("Initializing SQLite database...")
    await db.initialize()
    from rate_limiter import rate_limiter
    from safeguard import check_safeguard

    bot.rate_limiter = rate_limiter
    bot.check_safeguard = check_safeguard
    print("✅ Database ready!")


async def build_contextual_system_message(user: discord.User, channel, guild=None):
    if user is None:
        return {
            "role": "system",
            "content": "<system>\nYou are Urch, an AI assistant developed by urghan2, Likemea, and Urch AI.\n</system>",
        }
    user_params = await get_user_ai_params(str(user.id))
    user_persona = user_params.get("user_persona", "")
    ai_persona = user_params.get("ai_persona", "")

    base_content = f"<system>\nYou are Urch, an AI assistant developed by urghan2, Likemea, and Urch AI.\n</system>"

    if isinstance(channel, discord.DMChannel):
        context = f"<context>In a DM with user: {user.name}\n</context>"
    else:
        guild_name = guild.name if guild else "Group Chat"
        channel_name = channel.name if hasattr(channel, "name") else "group-chat"
        member_count = guild.member_count if guild else "10"
        context = f"<context>In a Discord server.\nServer: {guild_name} (Members: {member_count})\nChannel: #{channel_name}\nUser: {user.name}\n</context>"

    extras = []
    if user_persona:
        extras.append(f"\n\n<user_info>\n{user_persona}\n</user_info>")
    if ai_persona:
        extras.append(f"\n\n<ai_info>\n{ai_persona}\n</ai_info>")

    full_content = f"{base_content} {context}{''.join(extras)}"

    return {"role": "system", "content": full_content}


# ───────────────────────────────
# EVENTS
# ───────────────────────────────
async def load_extensions():
    for filename in os.listdir("./commands"):
        if filename.endswith(".py") and filename != "__init__.py":
            ext = f"commands.{filename[:-3]}"
            if ext not in bot.extensions:
                await bot.load_extension(ext)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")


fails = [
    "001 Empty Find",
    "002 Image Fail",
    "003 Unknown Function",
    "004 Error Request",
    "005 Time Out",
    "006 Unknown Message",
    "007 Invalid Code",
    "008 Empty Response",
    "009 Broken Pipe",
]

ROUTER_BASE_PROMPT = """You are the Model Router.
Your job is to select the most appropriate model to handle the user query.
Prioritize models based on their descriptions and how well they match the nature of the user's query.

IMPORTANT: Models marked with [Tools] can natively browse the web, scrape webpages, execute sandboxed Python code, generate media (images and audio), and create forum posts.
These models should ideally also be [Reasoning] capable, but it's fine if they're not.
When the user's query involves:
- Current events, real-time facts, research, links, or verification -> Select a [Tools]-capable model.
- Calculations, data analysis, math, coding execution, or plotting charts -> Select a [Tools]-capable model (e.g., gemini-3.5-flash-lite, qwen3.8-27b).
- Multi-part or complex agentic reasoning -> Select a [Tools]-capable or [Reasoning]-capable model.
- Images attached in the prompt, image-related queries -> Select a [Vision]-capable model.
- Simple conversation, chat, or basic knowledge -> Select lightweight models.

You MUST output ONLY the ID (key) corresponding to the best model for the task (e.g., "gemini-3.5-flash-lite").

Recent Context is provided to help you resolve ambiguities or references.

Available Models:
{model_list}
"""

# ───────────────────────────────
# ROUTER
# ───────────────────────────────
# Internal caps for the router model
_ROUTER_CAPS = {"reasoning_effort": True, "tools": False, "response_format": False}


async def choose_model(user_prompt, history=None, user_params=None, image_url=None):
    """Returns the MODELS entry (dict) for the chosen model."""
    if user_params:
        preferred = user_params.get("model", "Auto")
        if preferred != "Auto" and preferred in MODELS:
            if not image_url or MODELS[preferred].get("vision"):
                print(f"User preferred model: {preferred}")
                return MODELS[preferred]
            print(
                f"User preferred model '{preferred}' does not support vision; routing to vision model."
            )

    routable_entries = []
    for key, info in MODELS.items():
        if info.get("routable"):
            if image_url and not info.get("vision"):
                continue
            desc = info.get("router_info", "No description available.")
            tools_flag = " [Tools]" if info.get("tools") else ""
            vision_flag = " [Vision]" if info.get("vision") else ""
            routable_entries.append(f"- {key}: {info['disp']}{tools_flag}{vision_flag} | {desc}")

    model_list_str = "\n".join(routable_entries)
    full_router_prompt = ROUTER_BASE_PROMPT.format(model_list=model_list_str)

    messages = [{"role": "system", "content": full_router_prompt}]
    if history:
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": f"User query: {user_prompt}"})

    payload = {
        "model": "qwen/qwen3.8-27b",
        "messages": messages,
        "temperature": 0.6,
        "reasoning_effort": "none",
        "max_completion_tokens": 64,
    }
    try:
        resp = await call_model_direct(
            "groq", "qwen/qwen3.8-27b", payload, caps=_ROUTER_CAPS, timeout=10
        )
        choice = resp["choices"][0]["message"]["content"].strip()
        chosen = MODELS.get(choice, MODELS["gemini-3.5-flash-lite"])
        if image_url and not chosen.get("vision"):
            return MODELS["gemini-3.5-flash-lite"]
        return chosen
    except Exception as e:
        print(f"Router error: {e}")
        return MODELS["gemini-3.5-flash-lite"]


async def generate_response(
    prompt,
    conversation_history,
    user_id,
    image_url=None,
    user=None,
    channel=None,
    guild=None,
    stream=False,
    message_obj=None,
    status_message=None,
):
    system_msg = await build_contextual_system_message(user, channel, guild)

    user_params = await get_user_ai_params(user_id) or DEFAULT_AI_PARAMS

    rl = getattr(bot, "rate_limiter", None)

    # Cheap pre-gate BEFORE the router LLM call, so spam doesn't cost a router request.
    # Peeks against the most lenient tier: if this fails, every tier would fail.
    if rl:
        try:
            allowed, wait_time, reason = rl.peek(user_id)
            if not allowed:
                msg = (
                    reason
                    if wait_time <= 0
                    else f"⏳ Slow down! {reason} Try again in {wait_time:.1f}s."
                )
                return {"error": msg}
        except Exception as e:
            print(f"Rate limiter pre-check error: {e}")

    # 2 turns of chat for routing
    recent_history = conversation_history[-5:-1] if len(conversation_history) > 1 else []

    chosen_model = await choose_model(
        prompt if not image_url else f"{prompt} [User attached an image]",
        history=recent_history,
        user_params=user_params,
        image_url=image_url,
    )
    chosen_key = next((k for k, v in MODELS.items() if v is chosen_model), "gemini-3.5-flash-lite")
    print(
        f"Picked model: {chosen_model['id']} (key={chosen_key}, provider={chosen_model['provider']})"
    )

    # Authoritative, consuming check against the chosen model's tier.
    if rl:
        try:
            allowed, wait_time, reason = rl.check(user_id, model_id=chosen_model["id"])
            if not allowed:
                msg = (
                    reason
                    if wait_time <= 0
                    else f"⏳ Slow down! {reason} Try again in {wait_time:.1f}s."
                )
                return {"error": msg}
        except Exception as e:
            print(f"Rate limiter error: {e}")

    messages = [system_msg]
    for m in conversation_history:
        messages.append({"role": m["role"], "content": m["content"]})

    # vision replaces last user message with visual content if model supports it
    if image_url:
        if chosen_model.get("vision"):
            vision_turn = {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
            if messages and messages[-1]["role"] == "user":
                messages[-1] = vision_turn
            else:
                messages.append(vision_turn)
        else:
            text_turn = f"{prompt}\n[Image URL: {image_url}]"
            if messages and messages[-1]["role"] == "user":
                messages[-1] = {"role": "user", "content": text_turn}
            else:
                messages.append({"role": "user", "content": text_turn})

    # for streaming requests without tools
    is_dm = isinstance(channel, discord.DMChannel)
    guild_id = str(guild.id) if guild else None
    if (
        stream
        and not chosen_model.get("tools")
        and chosen_model.get("provider") == "pollinations"
        and message_obj
    ):
        payload = {
            "messages": messages,
            "temperature": user_params.get("temperature", 0.7),
            "top_p": user_params.get("top_p", 1),
            "max_completion_tokens": user_params.get("max_completion_tokens", 1000),
        }
        is_regeneration = hasattr(message_obj, "author") and message_obj.author == bot.user
        return await handle_streaming_response(
            chosen_key,
            payload,
            message_obj,
            user_id,
            is_dm,
            guild_id,
            prompt=prompt,
            conversation_history=conversation_history,
            existing_msg=message_obj if is_regeneration else None,
        )

    user_params_copy = dict(user_params)
    user_params_copy["user_id"] = str(user_id)
    return await run_agent_loop(
        chosen_key, messages, user_params_copy, status_message=status_message, bot=bot
    )


async def handle_streaming_response(
    chosen_key,
    payload,
    message,
    user_id_str,
    is_dm,
    guild_id,
    prompt=None,
    conversation_history=None,
    existing_msg=None,
):
    """
    Yields chunks, updates message every 1s,
    appends final content to history. Performs safeguard check before finishing.
    """
    cursor = "<:urch:1441878088332869783>"
    full_content = ""
    last_update_time = time.time()
    start_time = time.perf_counter()

    if existing_msg:
        target_msg = existing_msg
        try:
            await target_msg.edit(content="" + cursor)
        except:
            pass
    else:
        target_msg = await message.channel.send(
            "" + cursor, reference=message, mention_author=False
        )

    try:
        async for chunk in call_provider_stream(chosen_key, payload):
            full_content += chunk

            if time.time() - last_update_time >= 1.2:
                if full_content.strip():
                    display = full_content
                    if len(display) > 1900:
                        display = display[-1900:]

                    try:
                        await target_msg.edit(content=display + cursor)
                    except Exception as e:
                        print(f"Stream edit error: {e}")

                    last_update_time = time.time()

        final_content = full_content.strip()
        if not final_content:
            final_content = fails[7]

        recent_context = conversation_history[-5:] if conversation_history else []
        safeguard_result = await check_safeguard(
            recent_context, prompt or "Unknown Prompt", final_content
        )
        verdict = safeguard_result.get("verdict", "safe").lower()

        if verdict in ["unsafe_input", "unsafe_output", "unsafe_both"]:
            reason = safeguard_result.get("reasoning", "Unknown reason.")
            policy = safeguard_result.get("violated_policy", "Unspecified policy.")
            warning_text = (
                "Sorry, something went wrong. Please try again." 
            )

            channel_id = str(message.channel.id) if message and message.channel else None
            await target_msg.edit(content=warning_text)
            if existing_msg:
                await update_message_in_history(
                    user_id_str,
                    is_dm,
                    guild_id,
                    target_msg.id,
                    warning_text,
                    channel_id=channel_id,
                )
            else:
                await append_message_for_context(
                    user_id_str,
                    is_dm,
                    "assistant",
                    warning_text,
                    guild_id,
                    message_ids=[target_msg.id],
                    author_id=user_id_str,
                    channel_id=channel_id,
                )

            return {
                "raw_response": warning_text,
                "model_used": MODELS[chosen_key]["id"],
                "elapsed": time.perf_counter() - start_time,
                "streamed": True,
                "blocked": True,
            }

        # Safe - Final update
        channel_id = str(message.channel.id) if message and message.channel else None
        sent_ids = [target_msg.id]
        if len(final_content) > 2000:
            chunks = split_message(final_content)
            await target_msg.edit(content=chunks[0])
            for chunk in chunks[1:]:
                extra_msg = await message.channel.send(chunk)
                sent_ids.append(extra_msg.id)
        else:
            await target_msg.edit(content=final_content)

        if existing_msg:
            await update_message_in_history(
                user_id_str,
                is_dm,
                guild_id,
                existing_msg.id,
                full_content,
                new_message_ids=sent_ids,
                channel_id=channel_id,
            )
        else:
            await append_message_for_context(
                user_id_str,
                is_dm,
                "assistant",
                full_content,
                guild_id,
                message_ids=sent_ids,
                author_id=user_id_str,
                channel_id=channel_id,
            )

        return {
            "raw_response": full_content,
            "model_used": MODELS[chosen_key]["id"],
            "elapsed": time.perf_counter() - start_time,
            "streamed": True,
        }
    except Exception as e:
        error_msg = f"⚠️ Streaming error: {e}"
        print(f"Streaming error: {e}")
        try:
            await target_msg.edit(content=error_msg)
        except:
            pass
        return {"error": error_msg}


# ───────────────────────────────
# SAFEGUARD
# ───────────────────────────────
from safeguard import check_safeguard, _SAFEGUARD_CAPS


# ───────────────────────────────
# AUTOROLL
# ───────────────────────────────
@tasks.loop(seconds=10)
async def autoroll_heartbeat():
    try:
        active_ids = await db.get_active_rollers()
        if not active_ids:
            return

        rare_hits = await process_autorolls(active_ids)

        for user_id, rarity_name, one_in, total_luck in rare_hits:
            try:
                user = bot.get_user(int(user_id))
                if not user:
                    user = await bot.fetch_user(int(user_id))

                if user:
                    await log_rare_roll(bot, user, rarity_name, one_in, total_luck)

                await db.add_rare_hit(user_id, rarity_name, one_in, total_luck)
            except Exception as e:
                print(f"[Autoroll] Failed to log rare roll for {user_id}: {e}")

    except Exception as e:
        print(f"[Autoroll] Heartbeat error: {e}")


@autoroll_heartbeat.before_loop
async def _before_autoroll():
    await bot.wait_until_ready()


# ───────────────────────────────
# DATABASE BACKUPS
# ───────────────────────────────
@tasks.loop(hours=24)
async def db_backup_loop():
    try:
        path = await backup_database()
        if path:
            print(f"[Backup] Database backed up to {path}")
    except Exception as e:
        print(f"[Backup] Failed: {e}")


# ───────────────────────────────
# MESSAGES
# ───────────────────────────────
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user in message.mentions or isinstance(message.channel, discord.DMChannel):
        has_image = (
            message.attachments
            and message.attachments[0].content_type
            and message.attachments[0].content_type.startswith("image")
        )
        has_text = bool(message.content.strip())

        if not has_image and not has_text:
            return

        user_id_str = str(message.author.id)
        is_dm = isinstance(message.channel, discord.DMChannel)
        channel_id = str(message.channel.id)
        guild_id = str(message.guild.id) if message.guild else None

        # Check rate limiter BEFORE sending status or appending to history (Bug 6 fix)
        allowed, wait_time, reason = bot.rate_limiter.peek(user_id_str)
        if not allowed:
            if wait_time > 0:
                await message.channel.send(f"⏳ Slow down! Try again in {wait_time:.1f}s.")
            else:
                await message.channel.send(reason or "⛔ Requests are temporarily paused.")
            return

        async with message.channel.typing():
            try:
                image_url = None
                prompt = None

                if has_image:
                    image_url = message.attachments[0].url
                    raw_prompt = message.content.strip() or "Please describe the image."
                    prompt = raw_prompt
                    stored_content = f"[Image: {image_url}] {raw_prompt}"
                    await append_message_for_context(
                        user_id_str,
                        is_dm,
                        "user",
                        stored_content,
                        guild_id,
                        channel_id=channel_id,
                        message_ids=[message.id],
                        author_id=message.author.id,
                    )
                else:
                    prompt = message.content.strip()
                    await append_message_for_context(
                        user_id_str,
                        is_dm,
                        "user",
                        prompt,
                        guild_id,
                        channel_id=channel_id,
                        message_ids=[message.id],
                        author_id=message.author.id,
                    )

                messages_copy = await get_messages_for_context(
                    user_id_str, is_dm, guild_id, channel_id=channel_id
                )

                status_msg = await send_status(message.channel, "<:urch:1441878088332869783>")

                response = await generate_response(
                    prompt,
                    messages_copy,
                    user_id_str,
                    image_url=image_url,
                    user=message.author,
                    channel=message.channel,
                    guild=message.guild,
                    stream=False,
                    message_obj=message,
                    status_message=status_msg,
                )

                if response and "raw_response" in response:
                    raw = response["raw_response"]
                    files_to_send = response.get("files", [])

                    recent_context = messages_copy[-5:-1] if len(messages_copy) > 1 else []
                    safeguard_result = await check_safeguard(recent_context, prompt, raw)
                    verdict = safeguard_result.get("verdict", "safe").lower()

                    if verdict in ["unsafe_input", "unsafe_output", "unsafe_both"]:
                        reason = safeguard_result.get("reasoning", "Unknown reason.")
                        policy = safeguard_result.get("violated_policy", "Unspecified policy.")
                        warning_text = "Sorry, something went wrong. Please try again."

                        sent_ids = await reply_via_status(status_msg, message.channel, warning_text)

                        await append_message_for_context(
                            user_id_str,
                            is_dm,
                            "assistant",
                            warning_text,
                            guild_id,
                            channel_id=channel_id,
                            message_ids=sent_ids,
                            author_id=user_id_str,
                        )
                        return

                    if files_to_send:
                        if status_msg:
                            try:
                                await status_msg.delete()
                            except Exception:
                                pass
                        sent_msgs = await send_long_message(
                            message.channel,
                            content=raw,
                            reference=message,
                            mention_author=False,
                            files=files_to_send,
                        )
                        sent_ids = [m.id for m in sent_msgs]
                    else:
                        chunks = split_message(raw)
                        if not chunks:
                            chunks = ["*(Empty response)*"]
                        try:
                            if status_msg:
                                await status_msg.edit(content=chunks[0])
                                sent_msgs = [status_msg]
                                for chunk in chunks[1:]:
                                    extra_msg = await message.channel.send(content=chunk)
                                    sent_msgs.append(extra_msg)
                                sent_ids = [m.id for m in sent_msgs]
                            else:
                                sent_msgs = await send_long_message(
                                    message.channel,
                                    content=raw,
                                    reference=message,
                                    mention_author=False,
                                )
                                sent_ids = [m.id for m in sent_msgs]
                        except Exception:
                            sent_msgs = await send_long_message(
                                message.channel,
                                content=raw,
                                reference=message,
                                mention_author=False,
                            )
                            sent_ids = [m.id for m in sent_msgs]

                    await append_message_for_context(
                        user_id_str,
                        is_dm,
                        "assistant",
                        raw,
                        guild_id,
                        channel_id=channel_id,
                        message_ids=sent_ids,
                        author_id=user_id_str,
                    )
                    return

                if response and "error" in response:
                    err = response["error"]
                    await reply_via_status(status_msg, message.channel, err)
                    # Deliberately do not append error responses to conversation history
                    return

                fallback_text = fails[3]
                sent_ids = await reply_via_status(status_msg, message.channel, fallback_text)
                await append_message_for_context(
                    user_id_str,
                    is_dm,
                    "assistant",
                    fallback_text,
                    guild_id,
                    channel_id=channel_id,
                    message_ids=sent_ids,
                    author_id=user_id_str,
                )

            except asyncio.TimeoutError:
                await message.channel.send("⚠️ Request timed out")
            except Exception as e:
                print("Unhandled exception in on_message:", e)
                await message.channel.send(f"⚠️ Unexpected error occurred: {e}")


@bot.event
async def on_message_edit(before, after):
    if before.author == bot.user:
        return

    is_dm = isinstance(before.channel, discord.DMChannel)
    user_id_str = str(before.author.id)
    guild_id = str(before.guild.id) if before.guild else None
    channel_id = str(before.channel.id)

    if before.content != after.content:
        await update_message_in_history(
            user_id_str, is_dm, guild_id, before.id, after.content, channel_id=channel_id
        )


@bot.event
async def on_message_delete(message):
    if message.author == bot.user:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    user_id_str = str(message.author.id)
    guild_id = str(message.guild.id) if message.guild else None
    channel_id = str(message.channel.id)

    await delete_message_from_history(
        user_id_str, is_dm, guild_id, message.id, channel_id=channel_id
    )


@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    channel = bot.get_channel(payload.channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(payload.channel_id)
        except discord.Forbidden:
            return

    try:
        message = await channel.fetch_message(payload.message_id)
    except discord.NotFound:
        return

    if message.author.id != bot.user.id:
        return

    is_dm = isinstance(channel, discord.DMChannel)
    reactor_id = payload.user_id
    reactor_id_str = str(reactor_id)
    channel_id = str(channel.id)
    guild_id = str(payload.guild_id) if payload.guild_id else None

    orig_author_id = await get_original_author_for_message(
        reactor_id_str, is_dm, guild_id, message.id, channel_id=channel_id
    )
    if not orig_author_id and message.reference and message.reference.resolved:
        ref_msg = message.reference.resolved
        if hasattr(ref_msg, "author") and ref_msg.author:
            orig_author_id = str(ref_msg.author.id)
    user_id_str = str(orig_author_id) if orig_author_id else reactor_id_str

    emoji = str(payload.emoji)

    if emoji == "❌":
        try:
            allowed = False
            if is_dm:
                allowed = True
            elif payload.member and payload.member.guild_permissions.administrator:
                allowed = True

            if not allowed:
                allowed = await check_reaction_permission(
                    user_id_str, is_dm, guild_id, message.id, reactor_id, channel_id=channel_id
                )

            if allowed:
                deleted_ids = await delete_message_from_history(
                    user_id_str, is_dm, guild_id, message.id, channel_id=channel_id
                )
                target_ids = set(deleted_ids) if deleted_ids else {message.id}
                target_ids.add(message.id)
                for mid in target_ids:
                    try:
                        if mid == message.id:
                            await message.delete()
                        else:
                            m_chunk = await channel.fetch_message(mid)
                            await m_chunk.delete()
                    except Exception:
                        pass

        except Exception as e:
            print(f"Error handling delete reaction: {e}")

    elif emoji == "♻️":
        try:
            allowed = False
            if is_dm:
                allowed = True
            elif payload.member and payload.member.guild_permissions.administrator:
                allowed = True
            if not allowed:
                allowed = await check_reaction_permission(
                    user_id_str, is_dm, guild_id, message.id, reactor_id, channel_id=channel_id
                )

            if allowed:
                if not is_dm:
                    await message.remove_reaction(payload.emoji, discord.Object(id=reactor_id))
                prompt, context = await get_context_for_message(
                    user_id_str, is_dm, guild_id, message.id, channel_id=channel_id
                )

                if prompt and context is not None:
                    image_url = None
                    if prompt.startswith("[Image: ") and "] " in prompt:
                        img_part, raw_p = prompt.split("] ", 1)
                        image_url = img_part[len("[Image: ") :]
                        prompt_to_send = raw_p
                    elif prompt.startswith("[Image attached] "):
                        prompt_to_send = prompt[len("[Image attached] ") :]
                    else:
                        prompt_to_send = prompt

                    context.append({"role": "user", "content": prompt})

                    target_uid_int = int(user_id_str) if str(user_id_str).isdigit() else reactor_id
                    user_obj = bot.get_user(target_uid_int) or await bot.fetch_user(target_uid_int)

                    # Delete previous split chunk messages
                    old_ids = await get_message_ids_for_reply(
                        user_id_str, is_dm, guild_id, message.id, channel_id=channel_id
                    )
                    for old_mid in old_ids:
                        if old_mid != message.id:
                            try:
                                extra_msg = await channel.fetch_message(old_mid)
                                await extra_msg.delete()
                            except Exception:
                                pass

                    response = await generate_response(
                        prompt_to_send,
                        context,
                        user_id_str,
                        image_url=image_url,
                        user=user_obj,
                        channel=channel,
                        guild=message.guild,
                        stream=True,
                        message_obj=message,
                    )

                    if response and "raw_response" in response:
                        if response.get("streamed"):
                            return

                        new_content = response.get("display_response", response.get("raw_response"))
                        raw = response["raw_response"]
                        files_to_send = response.get("files", [])

                        recent_context = context[-7:-1] if len(context) > 1 else []
                        safeguard_result = await check_safeguard(
                            recent_context, prompt_to_send, raw
                        )
                        verdict = safeguard_result.get("verdict", "safe").lower()

                        if verdict in ["unsafe_input", "unsafe_output", "unsafe_both"]:
                            reason = safeguard_result.get("reasoning", "Unknown reason.")
                            policy = safeguard_result.get("violated_policy", "Unspecified policy.")

                            warning_text = "Sorry, something went wrong. Please try again."
                            await message.edit(content=warning_text, attachments=[])
                            await update_message_in_history(
                                user_id_str,
                                is_dm,
                                guild_id,
                                message.id,
                                warning_text,
                                channel_id=channel_id,
                            )
                            return

                        if not new_content or not new_content.strip():
                            new_content = fails[7]

                        sent_ids = [message.id]
                        chunks = split_message(new_content)
                        if not chunks:
                            chunks = ["*(Empty response)*"]

                        if files_to_send:
                            try:
                                await message.edit(content=chunks[0], attachments=files_to_send)
                            except Exception:
                                await message.edit(content=chunks[0], attachments=[])
                                extra_file_msg = await message.channel.send(
                                    files=files_to_send,
                                    reference=message,
                                    mention_author=False,
                                )
                                sent_ids.append(extra_file_msg.id)
                        else:
                            await message.edit(content=chunks[0], attachments=[])

                        for chunk in chunks[1:]:
                            extra_msg = await message.channel.send(
                                content=chunk,
                                reference=message,
                                mention_author=False,
                            )
                            sent_ids.append(extra_msg.id)

                        await update_message_in_history(
                            user_id_str,
                            is_dm,
                            guild_id,
                            message.id,
                            raw,
                            new_message_ids=sent_ids,
                            channel_id=channel_id,
                        )
                    else:
                        await message.edit(
                            content=f"⚠️ Regeneration failed: {response.get('error', 'Unknown')}",
                            attachments=[],
                        )
                else:
                    await message.channel.send(
                        "⚠️ Could not find context for regeneration (message might be too old).",
                        delete_after=5,
                    )

        except Exception as e:
            print(f"Error handling regenerate reaction: {e}")
            try:
                await message.channel.send(f"⚠️ Error: {e}", delete_after=5)
            except:
                pass


# ───────────────────────────────
# HELPERS
# ───────────────────────────────
def split_message(message, limit=2000):
    if not message:
        return ["*(Empty response)*"]
    if len(message) <= limit:
        return [message]
    chunks = []
    while len(message) > 0:
        if len(message) <= limit:
            chunks.append(message)
            break
        split_index = message.rfind(" ", 0, limit)
        if split_index <= 0:
            split_index = limit
        chunks.append(message[:split_index])
        message = message[split_index:].lstrip()
    return chunks


async def send_long_message(
    channel, content, reference=None, mention_author=False, file=None, files=None
):
    sent_messages = []
    chunks = split_message(content)
    if not chunks:
        chunks = ["*(Empty response)*"]
    for i, chunk in enumerate(chunks):
        if i == 0:
            if files:
                msg = await channel.send(
                    content=chunk, reference=reference, mention_author=mention_author, files=files
                )
            elif file:
                msg = await channel.send(
                    content=chunk, reference=reference, mention_author=mention_author, file=file
                )
            else:
                msg = await channel.send(
                    content=chunk, reference=reference, mention_author=mention_author
                )
            sent_messages.append(msg)
        else:
            msg = await channel.send(content=chunk)
            sent_messages.append(msg)
    return sent_messages


async def send_status(channel, text):
    try:
        return await channel.send(text)
    except Exception as e:
        print("send_status:", e)
        return None


async def reply_via_status(status_msg, channel, text) -> list[int]:
    """Edit the status message with `text`, falling back to a new message.
    Returns the IDs of the message(s) holding the reply."""
    if status_msg:
        try:
            await status_msg.edit(content=text)
            return [status_msg.id]
        except Exception as e:
            print("reply_via_status edit failed:", e)
    msg = await channel.send(text)  # send() returns a single Message, not a list
    return [msg.id]


async def edit_status(msg, text):
    if not msg:
        return
    try:
        await msg.edit(content=text)
    except Exception as e:
        print("edit_status:", e)


if __name__ == "__main__":
    bot.run(config.BOT_TOKEN)
