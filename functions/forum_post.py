# Urch/functions/forum_post.py
from typing import Optional, Tuple
import time
import discord
from safeguard import check_safeguard

FORUM_CHANNEL_ID = 1444006879461376121
TARGET_GUILD_ID = 1444003568263630900

# Rate limit: at most 1 forum post per user per hour (3600 seconds)
_forum_post_timestamps: dict[str, float] = {}


async def create_forum_post(
    bot: discord.Client,
    title: str,
    description: str,
    tag: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Tuple[str, Optional[discord.Thread]]:
    """
    Creates a new post (thread) in the designated forum channel (#urch-bot)
    with optional tag matching ('problem' or 'suggestion').
    Enforces per-user rate limiting (1/hr), safety evaluation, and user attribution.
    """
    if not bot:
        return "Error: Bot client is not available in execution context.", None

    if not title or not title.strip():
        return "Error: A non-empty 'title' is required to create a forum post.", None

    if not description or not description.strip():
        return "Error: A non-empty 'description' is required to create a forum post.", None

    now = time.time()
    if user_id:
        last_time = _forum_post_timestamps.get(str(user_id), 0.0)
        if now - last_time < 3600:
            remaining = int(3600 - (now - last_time))
            return (
                f"Error: Rate limit exceeded. You can create at most 1 forum post per hour (wait {remaining}s).",
                None,
            )

    # Pre-execution safeguard evaluation
    try:
        safeguard_result = await check_safeguard([], f"Forum post title: {title}", description)
        verdict = safeguard_result.get("verdict", "safe").lower()
        if verdict in ["unsafe_input", "unsafe_output", "unsafe_both"]:
            reason = safeguard_result.get("reasoning", "Content flagged as unsafe.")
            policy = safeguard_result.get("violated_policy", "Unspecified policy.")
            return f"Error: Forum post blocked by safeguard policy ({policy}): {reason}", None
    except Exception as e:
        print(f"[ForumPost] Safeguard evaluation error: {e}")

    title_str = title.strip()[:100]
    content_str = description.strip()
    if user_id:
        content_str += f"\n\n*Requested by <@{user_id}>*"

    channel = bot.get_channel(FORUM_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(FORUM_CHANNEL_ID)
        except Exception as e:
            return f"Error: Could not retrieve forum channel (ID: {FORUM_CHANNEL_ID}): {e}", None

    if not isinstance(channel, discord.ForumChannel):
        return f"Error: Channel {FORUM_CHANNEL_ID} is not a ForumChannel (type: {type(channel).__name__}).", None

    applied_tags = []
    if tag:
        tag_lower = str(tag).strip().lower()
        matched_tag = None
        for available_tag in channel.available_tags:
            if available_tag.name.lower() == tag_lower or tag_lower in available_tag.name.lower():
                matched_tag = available_tag
                break

        if matched_tag:
            applied_tags.append(matched_tag)

    try:
        thread_with_message = await channel.create_thread(
            name=title_str,
            content=content_str,
            applied_tags=applied_tags,
        )
        thread = thread_with_message.thread
        if user_id:
            _forum_post_timestamps[str(user_id)] = now

        tag_info = f" with tag '{tag}'" if applied_tags else ""
        return (
            f"Successfully created forum post '{title_str}' in #{channel.name}{tag_info}. "
            f"Post URL: {thread.jump_url}",
            thread,
        )
    except Exception as e:
        return f"Error creating forum post: {e}", None
