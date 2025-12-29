# Urch/main.py
import asyncio
import json
import os
import re
import time
import atexit
import datetime
from database import db
import aiosqlite

import discord
import requests
from discord.ext import commands, tasks
from discord import app_commands

from utils import (
    get_user_ai_params, 
    get_user_data, get_messages_for_context, append_message_for_context, 
    save_conversation_history, MODEL_LIST, 
    DEFAULT_AI_PARAMS, update_message_in_history, delete_message_from_history, 
    check_reaction_permission, get_context_for_message, get_unsummarized_messages, 
    update_last_summary_time, get_last_summary_time
)
from functions.web import web_search
from functions.image_gen import generate_image
from functions.memory import memory_manager

# ───────────────────────────────
# API KEYS & CONFIG
# ───────────────────────────────
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
headers_groq = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix='!', intents=intents)

atexit.register(lambda: save_conversation_history())

async def initialize_database():
    """Initialize SQLite database on startup"""
    print("Initializing SQLite database...")
    await db.initialize()
    print("✅ Database ready!")
    
async def build_contextual_system_message(user: discord.User, channel, guild=None, memories: list = None):
    # We use "[START/END]" for robust prompting adherence and to protect against adversarial prompts (within reason)
    if user is None:
        return {
            "role": "system",
            "content": "[START_SYSTEM_INSTRUCT]\nYou are Urch, an AI assistant developed by urghan2, Likemea, and Urch AI.\n[END_SYSTEM_INSTRUCT]"
        }
    # Fetch user params to inject Personas
    user_params = await get_user_ai_params(str(user.id))
    user_persona = user_params.get("user_persona", "")
    ai_persona = user_params.get("ai_persona", "")

    base_content = f"[START_SYSTEM_INSTRUCT]\nYou are Urch, an AI assistant developed by urghan2, Likemea, and Urch AI.\n"

    if isinstance(channel, discord.DMChannel):
        context = f"You are currently chatting with {user.name} in DM.\n[END_SYSTEM_INSTRUCT]"
    else:
        guild_name = guild.name if guild else "Group Chat"
        channel_name = channel.name if hasattr(channel, "name") else "group-chat"
        member_count = guild.member_count if guild else "10"
        context = f"You are in a Discord server.\nServer: {guild_name} (Members: {member_count})\nChannel: #{channel_name}\nUser: {user.name}\n[END_SYSTEM_INSTRUCT]"

    # Inject Personas if they exist
    extras = []
    if user_persona:
        extras.append(f"\n\n[START_USER_INFO]\n{user_persona}\n[END_USER_INFO]")
    if ai_persona:
        extras.append(f"\n\n[START_USER_INSTRUCT]\n{ai_persona}\n[END_USER_INSTRUCT]")
    
    # Inject RAG Memories
    if memories:
        mem_block = "\n".join([f"- {m}" for m in memories])
        extras.append(f"\n\n[START_MEMORIES]\n{mem_block}\n[END_MEMORIES]")
    
    full_content = f"{base_content} {context}{''.join(extras)}"

    return {
        "role": "system",
        "content": full_content
    }

# ───────────────────────────────
# BOT EVENTS & CORE DEFAULTS
# ───────────────────────────────
async def load_extensions():
    for filename in os.listdir('./commands'):
        if filename.endswith('.py') and filename != '__init__.py':
            await bot.load_extension(f'commands.{filename[:-3]}')

@bot.event
async def on_ready():
    await initialize_database()
    await load_extensions()
    print(f'Logged in as {bot.user}!')
    if not memory_task.is_running():
        memory_task.start()

fails = [
    "001 Empty Find",
    "002 Image Fail",
    "003 Unknown Function",
    "004 Error Request",
    "005 Time Out",
    "006 Unknown Message",
    "007 Invalid Code"
]

ROUTER_SYSTEM_PROMPT = """You are the Model Router.
Your job is to select the most appropriate model to handle the user query.
Prioritize models based on their descriptions and how well they match the nature of the user's query.
You MUST output ONLY the number corresponding to the best model for the task.

Available Models:

1.  llama-3.1-8b (Weight: Lowest): Quick responses, chit-chat, simple Q&A, short code snippets, greetings, gibberish/nonsensical inputs.
2.  gpt-oss-20b (Weight: Low-Medium): Has Chain-of-Thought (CoT) reasoning for intermediate complexity, multi-step problem solving, and complex factual retrieval.
3.  gpt-oss-120b (Weight: Medium): Advanced complexity, native tool calling, and extended CoT reasoning. Great for agentic workflows!
4.  llama-3.3-70b (Weight: Medium-High): Solid reasoning, multilingual tasks, and general coding tasks.
5.  kimi-k2 (Weight: Medium-High): An alternative to llama-3.3-70b. Solid mix of facts & knowledge with creativity.
6.  llama-4-scout (Weight: High): Can process text + images (multimodal). Use ONLY when the user sends an image/visual data.
7.  llama-4-maverick (Weight: Highest): Advanced multimodal. Use for highly detailed image understanding, analysis, and visual reasoning.
"""

# ───────────────────────────────
# MODEL CALLS / RETRIES / ROUTER
# ───────────────────────────────
def call_model_with_retry(payload, retries=2):
    for attempt in range(retries):
        try:
            response = requests.post(GROQ_API_URL, headers=headers_groq, json=payload, timeout=20)
            response.raise_for_status()
            return response.json(), payload["model"]
        except requests.RequestException as e:
            print(f"Error on attempt {attempt+1} with {payload['model']}: {e}")
            print(payload)
            if attempt < retries - 1:
                time.sleep(2 + attempt * 2)
            else:
                print("⚠️ Falling back to llama-3.1-8b-instant")
                fallback_messages = payload.get("messages", [])
                fallback_payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": fallback_messages,
                    "temperature": payload.get("temperature", 0.7),
                    "top_p": payload.get("top_p", 0.4),
                    "max_completion_tokens": payload.get("max_completion_tokens", 512)
                }
                response = requests.post(GROQ_API_URL, headers=headers_groq, json=fallback_payload, timeout=20)
                response.raise_for_status()
                return response.json(), "llama-3.1-8b-instant"

def parse_function_call(response: str):
    try:
        json_block = re.search(r'(\{.*"function_call".*?\})', response, re.DOTALL)
        if json_block:
            try:
                obj = json.loads(json_block.group(1))
                fc = obj.get("function_call", {})
                return fc.get("name"), fc.get("arguments")
            except Exception:
                pass

        match = re.search(r'function_call\s*:\s*([a-zA-Z0-9_]+)\s*\(\s*(\{.*\})\s*\)', response, re.DOTALL)
        if match:
            fname = match.group(1)
            args_str = match.group(2)
            try:
                args = json.loads(args_str)
            except Exception:
                args = args_str
            return fname, args

        match2 = re.search(r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{.*\})\s*\}', response, re.DOTALL)
        if match2:
            return match2.group(1), json.loads(match2.group(2))

        return None, None
    except Exception as e:
        print("parse_function_call error:", e)
        return None, None

def choose_model(user_prompt, user_params=None):
    # 1. Check if user has a fixed model preference
    if user_params:
        preferred_model = user_params.get("model", "Auto")
        if preferred_model != "Auto" and preferred_model in MODEL_LIST:
            print(f"User preferred model: {preferred_model}")
            return MODEL_LIST[preferred_model]

    # 2. Otherwise, run the router
    payload = {
        "model": "qwen/qwen3-32b",
        "messages": [
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": f"User query: {user_prompt}"}
        ],
        "temperature": 0.7,
        "reasoning_effort": "none",
        "max_completion_tokens": 5
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers_groq, json=payload, timeout=10)
        response.raise_for_status()
        response_json = response.json()
        choice = response_json["choices"][0]["message"]["content"].strip()
        return MODEL_LIST.get(choice, MODEL_LIST["1"])
    except Exception as e:
        print(f"Router error: {e}")
        return MODEL_LIST["1"]

async def generate_response(prompt, conversation_history, user_id, image_url=None, user=None, channel=None, guild=None, memories=None):
    system_msg = await build_contextual_system_message(user, channel, guild, memories)
    
    user_params = await get_user_ai_params(user_id) or DEFAULT_AI_PARAMS
    
    chosen_model = choose_model(prompt if not image_url else f"{prompt} [User attached an image]", user_params=user_params)
    print(f"Picked model: {chosen_model['id']}")

    messages = [system_msg]
    for m in conversation_history:
        messages.append({"role": m["role"], "content": m["content"]})

    if chosen_model["id"] in [
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-maverick-17b-128e-instruct"
    ] and image_url:
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]}
        ]

    payload = {
        "model": chosen_model["id"],
        "messages": messages,
        "temperature": user_params.get("temperature", 0.7),
        "top_p": user_params.get("top_p", 1),
        "max_completion_tokens": user_params.get("max_completion_tokens", 512)
    }

    if chosen_model["id"] == "openai/gpt-oss-120b":
        payload["reasoning_effort"] = "medium"
        payload["tools"] = [{"type": "code_interpreter"}]

    start = time.perf_counter()
    try:
        response_json, model_used = call_model_with_retry(payload)
        elapsed = time.perf_counter() - start
        assistant_response = response_json["choices"][0]["message"]["content"].strip()

        return {
            "raw_response": assistant_response,
            "display_response": f"{assistant_response}\n",
            "model_used": model_used,
            "elapsed": elapsed
        }
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
        
async def do_agentic(prompt: str):
    """
    Decides IF a tool is needed, WHICH tool, and WHAT arguments.
    Returns a dict: {"tool": "web_search"|"generate_image"|"none", "args": "query"}
    """
    try:
        router_prompt = (
            "You are an intelligent tool orchestrator.\n"
            "Analyze the user's request and determine the best tool to use.\n\n"
            "Tools:\n"
            "1. web_search(query: str, results: OptionalInt[1-5]): Use for current events, news, facts, documentation, or retrieving specific info from the internet.\n"
            "2. generate_image(prompt): Use ONLY when the user specifically asks to draw, paint, generate, or create an image/picture.\n"
            "3. none: Don't need any tool"
            "\n\n"
            "Instructions:\n"
            "- Do NOT assume web search is needed for general knowledge.\n"
            "- If using a tool, you MUST generate the optimal query/prompt for that tool based on the user's intent.\n"
            "- Output strictly valid JSON in this format: {\"tool\": \"tool_name\", \"args\": \"optimized_query_string\"}\n"
            "- IF YOU PICK NONE, PLEASE OUTPUT ONLY none"
        )
        
        payload = {
            "model": "qwen/qwen3-32b",
            "messages": [
                {"role": "system", "content": router_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_completion_tokens": 200,
            "reasoning_effort": "none",
            "response_format": {"type": "json_object"}
        }
        
        response = requests.post(GROQ_API_URL, headers=headers_groq, json=payload, timeout=10)
        response.raise_for_status()
        response_json = response.json()
        content = response_json["choices"][0]["message"]["content"].strip()
        
        print(f"Agentic Planner Output: {content}")
        
        try:
            result = json.loads(content)
            # Normalize keys just in case
            tool = result.get("tool", "none").lower()
            args = result.get("args", "")
            return {"tool": tool, "args": args}
        except json.JSONDecodeError:
            print("Failed to parse Agentic JSON")
            return {"tool": "none", "args": ""}

    except Exception as e:
        print("Router error:", e)
        return {"tool": "none", "args": ""}

async def generate_text(prompt, conversation_history, user_id, image_url=None, user=None, channel=None, guild=None, memories=None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, generate_response, prompt, conversation_history, user_id, image_url, user, channel, guild, memories)

# ───────────────────────────────
# MEMORY TASK LOOP
# ───────────────────────────────
@tasks.loop(minutes=1)
async def memory_task():
    async with aiosqlite.connect(db.db_path) as db_conn:
        async with db_conn.execute("SELECT user_id FROM users") as cursor:
            user_ids = [row[0] async for row in cursor]
    
    for user_id in user_ids:
        # 0. Check Settings
        params = await get_user_ai_params(user_id)
        if not params.get("memory_enabled", True):
            continue
            
        freq_minutes = params.get("memory_frequency", 10)
        
        # Check time diff
        last_time_str = await get_last_summary_time(user_id)
        if last_time_str:
            try:
                last = datetime.datetime.fromisoformat(last_time_str)
                diff = datetime.datetime.now() - last
                if diff.total_seconds() / 60 < freq_minutes:
                    continue # Too soon
            except ValueError:
                pass

        # 1. Get unsummarized messages
        new_msgs = await get_unsummarized_messages(user_id)
        
        # Only process if we have a decent chunk of new context
        if len(new_msgs) > 6:
            print(f"[Memory Task] Summarizing {len(new_msgs)} messages for user {user_id}")
            
            # 2. Create summarization prompt
            convo_text = "\n".join([f"{m['role']}: {m['content']}" for m in new_msgs])
            
            summary_prompt = (
                "Summarize the following conversation snippets into concise, factual memory points about the conversation. "
                "Ignore trivial chit-chat. Focus on preferences, facts, names, and specific requests. "
                "Output ONLY the bullet points.\n\n"
                f"{convo_text}"
            )
            
            # 3. Call llama-3.1-8b-instant
            try:
                user_obj = bot.get_user(int(user_id))
                if not user_obj:
                    try:
                        user_obj = await bot.fetch_user(int(user_id))
                    except discord.NotFound:
                        # print(f"[Memory Task] User {user_id} not found, skipping summary.")
                        continue
                    except Exception as e:
                        # print(f"[Memory Task] Failed to fetch user {user_id}: {e}")
                        continue
                        
                # We construct a payload from scratch because we do not want the summarizer to be distracted by the original contextual system message
                payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": summary_prompt},
                        {"role": "user", "content": convo_text}
                    ],
                    "temperature": 0.7,
                    "max_completion_tokens": 500
                }
                response = requests.post(GROQ_API_URL, headers=headers_groq, json=payload, timeout=10)
                response.raise_for_status()
                response_json = response.json()
                response = response_json["choices"][0]["message"]["content"].strip().lower()        
                
                if response:
                    summary = response
                    
                    # 4. Store in Memory Vector DB
                    memory_manager.add_memory(user_id, summary, source="auto_summary")
                    
                    # 5. Update timestamp so we don't process these again
                    await update_last_summary_time(user_id)
                    
            except Exception as e:
                print(f"[Memory Task] Error summarizing for {user_id}: {e}")

    
# ───────────────────────────────
# MESSAGE HANDLING
# ───────────────────────────────
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user in message.mentions or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                has_image = message.attachments and message.attachments[0].content_type and message.attachments[0].content_type.startswith('image')
                has_text = bool(message.content.strip())

                image_url = None
                prompt = None
                is_dm = isinstance(message.channel, discord.DMChannel)
                user_id_str = str(message.author.id)
                guild_id = str(message.guild.id) if message.guild else None

                if has_image:
                    image_url = message.attachments[0].url
                    prompt = message.content.strip() or "Please describe the image."
                    await append_message_for_context(user_id_str, is_dm, "user", f"[Image attached] {prompt}", guild_id, message_ids=[message.id], author_id=message.author.id)

                elif has_text:
                    prompt = message.content.strip()
                    await append_message_for_context(user_id_str, is_dm, "user", prompt, guild_id, message_ids=[message.id], author_id=message.author.id)

                else:
                    return

                messages_copy = await get_messages_for_context(user_id_str, is_dm, guild_id)
                
                # ───────────────────────────────
                # RAG RETRIEVAL
                # ───────────────────────────────
                relevant_memories = []
                user_params = await get_user_ai_params(user_id_str)
                if is_dm and user_params.get("memory_enabled", True):
                    threshold = user_params.get("memory_probability", 0.35)
                    relevant_memories = memory_manager.get_relevant_memories(user_id_str, prompt, threshold=threshold)

                # ───────────────────────────────
                # AGENTIC TOOL SELECTION
                # ───────────────────────────────
                user_params = await get_user_ai_params(user_id_str)
                reasoning_setting = user_params.get("reasoning", "Auto")
                
                # Default final prompt is just the user text
                final_prompt = prompt
                file_to_send = None

                # Determine if we should check for tools
                check_tools = True
                if reasoning_setting == "False":
                    check_tools = False
                
                if check_tools:
                    # Run the Planner
                    plan = await do_agentic(prompt)
                    tool_name = plan.get("tool")
                    tool_args = plan.get("args")

                    if tool_name == "web_search" and tool_args:
                        status_msg = await send_status(message.channel, f"* 🔎 **'{tool_args}'**")
                        search_results = await web_search(tool_args)
                        
                        context_str = "\n".join([f"- {r['url']}: {r['content']}" for r in search_results])
                        final_prompt = f"{prompt}\n\n[Web Search Results for '{tool_args}']:\n{context_str}"
                        
                        await edit_status(status_msg, f"* ✅ Found {len(search_results)} results.")
                        try:
                            await status_msg.delete()
                        except:
                            pass
                            
                    elif tool_name == "generate_image" and tool_args:
                        status_msg = await send_status(message.channel, f"* 🎨 **'{tool_args}'**")
                        
                        # Generate the image
                        discord_file = await generate_image(tool_args)
                        
                        if discord_file:
                            file_to_send = discord_file
                            # Notify the final model that an image was sent
                            final_prompt = f"{prompt}\n\n[System: You have successfully generated an image based on the prompt '{tool_args}'. The image has been sent to the user. Briefly mention it in your response.]"
                            await edit_status(status_msg, f"* ✅")
                        else:
                            final_prompt = f"{prompt}\n\n[System: Attempted to generate image but failed due to API error.]"
                            await edit_status(status_msg, f"* ❌")
                            
                        try:
                            await status_msg.delete()
                        except:
                            pass

                    # Update the context provided to the final model (for this turn only)
                    messages_copy[-1]["content"] = final_prompt

                # ───────────────────────────────
                # FINAL GENERATION
                # ───────────────────────────────
                response = await generate_response(final_prompt, messages_copy, user_id_str, image_url=image_url, user=message.author, channel=message.channel, guild=message.guild, memories=relevant_memories)

                if response and "raw_response" in response:
                    raw = response["raw_response"]                        
                    # Pass the generated file (if any) to be sent along with the text
                    sent_msgs = await send_long_message(message.channel, content=response["display_response"], reference=message, mention_author=False, file=file_to_send)
                    
                    sent_ids = [m.id for m in sent_msgs]
                    await append_message_for_context(user_id_str, is_dm, "assistant", raw, guild_id, message_ids=sent_ids)
                    return
        
                if response and "error" in response:
                    err = response["error"]
                    sent_msgs = await message.channel.send(err)
                    await append_message_for_context(user_id_str, is_dm, "assistant", err, guild_id, message_ids=[sent_msgs.id])
                    return
        
                sent_msgs = await message.channel.send(fails[3])
                await append_message_for_context(user_id_str, is_dm, "assistant", fails[3], guild_id, message_ids=[sent_msgs.id])
            
            except asyncio.TimeoutError:
                await message.channel.send("⚠️ Request timed out")
            except Exception as e:
                print("Unhandled exception in on_message:", e)
                await message.channel.send(f"⚠️ Unexpected error occurred: {e}")

@bot.event
async def on_message_edit(before, after):
    if before.author == bot.user:
        return

    # Check context
    is_dm = isinstance(before.channel, discord.DMChannel)
    user_id_str = str(before.author.id)
    guild_id = str(before.guild.id) if before.guild else None

    # Update conversation history
    if before.content != after.content:
        await update_message_in_history(user_id_str, is_dm, guild_id, before.id, after.content)

@bot.event
async def on_message_delete(message):
    # Check context
    is_dm = isinstance(message.channel, discord.DMChannel)
    user_id_str = str(message.author.id)
    guild_id = str(message.guild.id) if message.guild else None

    # Remove from conversation history
    await delete_message_from_history(user_id_str, is_dm, guild_id, message.id)

@bot.event
async def on_raw_reaction_add(payload):
    # Ignore bot's own reactions
    if payload.user_id == bot.user.id:
        return

    # Fetch channel/message (Universal Logic)
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

    # Ensure message is from the bot
    if message.author.id != bot.user.id:
        return

    is_dm = isinstance(channel, discord.DMChannel)
    user_id_str = str(payload.user_id)
    guild_id = str(payload.guild_id) if payload.guild_id else None

    emoji = str(payload.emoji)

    # ───────────────────────────────
    # ❌ DELETE LOGIC
    # ───────────────────────────────
    if emoji == '❌':
        try:
            # Determine permission
            allowed = False
            if is_dm:
                allowed = True
            elif payload.member and payload.member.guild_permissions.administrator:
                allowed = True
            
            # Prompter check
            if not allowed:
                allowed = await check_reaction_permission(user_id_str, is_dm, guild_id, message.id, payload.user_id)
            
            if allowed:
                await delete_message_from_history(user_id_str, is_dm, guild_id, message.id)
                await message.delete()

        except Exception as e:
            print(f"Error handling delete reaction: {e}")

    # ───────────────────────────────
    # ♻ REGENERATE LOGIC
    # ───────────────────────────────
    elif emoji == '♻️':
        try:
            # Determine permission (Same as delete - only prompter or admin)
            allowed = False
            if is_dm:
                allowed = True
            elif payload.member and payload.member.guild_permissions.administrator:
                allowed = True
            if not allowed:
                allowed = await check_reaction_permission(user_id_str, is_dm, guild_id, message.id, payload.user_id)

            if allowed:
                if not is_dm:
                    await message.remove_reaction(payload.emoji, discord.Object(id=payload.user_id))
                # Get context needed for regeneration
                prompt, context = await get_context_for_message(user_id_str, is_dm, guild_id, message.id)
                
                if prompt and context is not None:                    
                    # CRITICAL FIX: Add the prompt back to context so the model sees it!
                    context.append({"role": "user", "content": prompt})

                    # Fetch user for personas
                    user_obj = bot.get_user(payload.user_id) or await bot.fetch_user(payload.user_id)
                    
                    # Generate new response
                    # Pass memory retrieval here too if we want consistency, but simple regen might skip it for speed
                    response = await generate_response(prompt, context, user_id_str, user=user_obj, channel=channel, guild=message.guild)
                    
                    if response and "raw_response" in response:
                        new_content = response["display_response"]
                        
                        if new_content and new_content.strip():
                            # Edit the Discord message
                            await message.edit(content=new_content)
                            
                            # Update the history for this message
                            await update_message_in_history(user_id_str, is_dm, guild_id, message.id, response["raw_response"])
                        else:
                             await message.edit(content="⚠️ Error: Model returned empty response.")
                    else:
                        await message.edit(content=f"⚠️ Regeneration failed: {response.get('error', 'Unknown')}")
                else:
                    await message.channel.send("⚠️ Could not find context for regeneration (message might be too old).", delete_after=5)

        except Exception as e:
            print(f"Error handling regenerate reaction: {e}")
            # Check if the message still exists before trying to send error
            try:
                await message.channel.send(f"⚠️ Error: {e}", delete_after=5)
            except:
                pass

# ───────────────────────────────
# HELPERS
# ───────────────────────────────
def split_message(message, limit=2000):
    if len(message) <= limit:
        return [message]
    chunks = []
    while len(message) > 0:
        split_index = message.rfind(' ', 0, limit)
        if split_index == -1:
            split_index = limit
        chunks.append(message[:split_index])
        message = message[split_index:].lstrip()
    return chunks

async def send_long_message(channel, content, reference=None, mention_author=False, file=None):
    sent_messages = []
    for i, chunk in enumerate(split_message(content)):
        if i == 0:
            msg = await channel.send(content=chunk, reference=reference, mention_author=mention_author, file=file)
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

async def edit_status(msg, text):
    if not msg:
        return
    try:
        await msg.edit(content=text)
    except Exception as e:
        print("edit_status:", e)

bot.run(os.environ.get('BOT_TOKEN'))