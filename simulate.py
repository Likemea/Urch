#!/usr/bin/env python3
"""
Urch Simulation REPL & Agent Runner
----------------------------------
Interactive testing pipeline and terminal harness for Urch.
Enables agents and developers to test bot commands, view components,
attachments, and database state locally without requiring a Discord client or user account.

Usage:
  Interactive REPL:
    python simulate.py

  Single or batch command execution:
    python simulate.py "roll"
    python simulate.py "roll" "click 1"
    python simulate.py "pixel size=64 pattern=stripes"
    python simulate.py "sort 5 bubble"
    python simulate.py "filter blur"
    python simulate.py "glitch intensity=7"

  Piped / Batch script execution:
    type commands.txt | python simulate.py
"""

import os
import io
import sys
import shlex
import inspect
import asyncio
from typing import Optional, Any, Dict, List, Union
from unittest.mock import AsyncMock, MagicMock

# Force UTF-8 encoding on standard I/O for cross-platform emoji and box drawing
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Output directory for generated simulator files (e.g. GIFs, PNGs)
SIM_OUTPUT_DIR = os.path.join(PROJECT_ROOT, ".sim_output")

# Load .env if present; supply safe dummy defaults for offline simulation
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, ".env"))

MOCK_ENV_DEFAULTS = {
    "APPLICATION_ID": "123456789012345678",
    "BOT_TOKEN": "mock_bot_token_for_simulation_only",
    "GROQ_API_KEY": "mock_groq_key",
    "POLLINATIONS_API_KEY": "mock_pollinations_key",
    "GOOGLE_API_KEY": "mock_google_key",
}
for key, val in MOCK_ENV_DEFAULTS.items():
    os.environ.setdefault(key, val)

import discord
from discord import app_commands
from discord.ext import commands
from database import db


# ─────────────────────────────────────────────────────────────────────────────
# Terminal Box & Embed Renderer
# ─────────────────────────────────────────────────────────────────────────────

def _wrap_text(text: str, max_len: int = 68) -> List[str]:
    """Wrap a block of text into lines no longer than max_len."""
    lines = []
    for raw_line in str(text).split("\n"):
        if not raw_line:
            lines.append("")
            continue
        words = raw_line.split(" ")
        current = ""
        for w in words:
            if not current:
                current = w
            elif len(current) + len(w) + 1 <= max_len:
                current += " " + w
            else:
                lines.append(current)
                current = w
        if current:
            lines.append(current)
    return lines


def _format_size(num_bytes: int) -> str:
    """Format bytes into readable size string."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    else:
        return f"{num_bytes / (1024 * 1024):.2f} MB"


def render_response(content: Optional[str] = None,
                    embed: Optional[discord.Embed] = None,
                    embeds: Optional[List[discord.Embed]] = None,
                    view: Optional[discord.ui.View] = None,
                    file: Optional[discord.File] = None,
                    files: Optional[List[discord.File]] = None) -> None:
    """Renders messages, embeds, files, and interactive view components to terminal."""
    target_embeds = list(embeds) if embeds else ([embed] if embed else [])
    target_files = list(files) if files else ([file] if file else [])

    if content:
        print(f"\n💬 Response:\n{content}")

    for emb in target_embeds:
        title = emb.title or "Embed"
        print(f"\n┌─ {title} " + "─" * max(2, 66 - len(title)) + "┐")

        if emb.description:
            for line in _wrap_text(emb.description, 68):
                print(f"│ {line:<68} │")

        if emb.fields:
            if emb.description:
                print("│ " + " " * 68 + " │")
            for field in emb.fields:
                header = f"• {field.name}: {field.value}"
                for line in _wrap_text(header, 68):
                    print(f"│ {line:<68} │")

        if emb.footer and emb.footer.text:
            print("│ " + " " * 68 + " │")
            footer_line = f"ℹ️  {emb.footer.text}"
            for line in _wrap_text(footer_line, 68):
                print(f"│ {line:<68} │")

        print("└" + "─" * 70 + "┘")

    # Render attached files
    if target_files:
        os.makedirs(SIM_OUTPUT_DIR, exist_ok=True)
        print("  📎 Generated Attachments:")
        for idx, f in enumerate(target_files, 1):
            fname = getattr(f, "filename", f"file_{idx}")
            fp = getattr(f, "fp", None)
            size_str = "unknown size"
            if fp:
                try:
                    pos = fp.tell()
                    fp.seek(0, io.SEEK_END)
                    sz = fp.tell()
                    fp.seek(pos)
                    size_str = _format_size(sz)

                    # Save copy to .sim_output for user/agent inspection
                    out_path = os.path.join(SIM_OUTPUT_DIR, fname)
                    with open(out_path, "wb") as out_f:
                        fp.seek(0)
                        out_f.write(fp.read())
                        fp.seek(pos)
                    print(f"    [{idx}] {fname} ({size_str}) -> saved to .sim_output/{fname}")
                except Exception:
                    print(f"    [{idx}] {fname} ({size_str})")
            else:
                print(f"    [{idx}] {fname}")

    # Render interactive UI buttons/components
    if view and getattr(view, "children", None):
        print("  Buttons / Components:")
        for idx, child in enumerate(view.children, 1):
            label = getattr(child, "label", None) or getattr(child, "emoji", None) or f"Item #{idx}"
            style_name = child.style.name if hasattr(child, "style") else "default"
            status = " (disabled)" if getattr(child, "disabled", False) else ""
            print(f"    [{idx}] {label} [{style_name}]{status}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Simulation Session & Mock Objects
# ─────────────────────────────────────────────────────────────────────────────

def _create_sample_png() -> bytes:
    """Generates a small in-memory sample PNG image for testing attachments."""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (96, 96), color=(50, 100, 150))
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 85, 85], outline=(255, 255, 255), width=2)
        draw.text((20, 40), "Urch AI", fill=(255, 255, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        # Minimal 1x1 transparent PNG fallback if Pillow is unavailable
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00"
            b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
        )


class MockAttachment:
    """Mock discord.Attachment supporting local files or synthetic test images."""

    def __init__(self, filename: str = "sample.png", data: Optional[Union[bytes, str]] = None, content_type: str = "image/png"):
        self.filename = filename
        self.content_type = content_type

        if data is None:
            self._data = _create_sample_png()
        elif isinstance(data, (str, os.PathLike)) and os.path.exists(data):
            with open(data, "rb") as f:
                self._data = f.read()
            self.filename = os.path.basename(str(data))
            if self.filename.lower().endswith(".gif"):
                self.content_type = "image/gif"
            elif self.filename.lower().endswith((".jpg", ".jpeg")):
                self.content_type = "image/jpeg"
        elif isinstance(data, bytes):
            self._data = data
        else:
            self._data = _create_sample_png()

        self.size = len(self._data)

    async def read(self) -> bytes:
        return self._data


class MockAvatar:
    """Mock user avatar asset with fallback image fetching."""

    def __init__(self, url: str = "https://cdn.discordapp.com/embed/avatars/0.png"):
        self.url = url

    async def read(self) -> bytes:
        return _create_sample_png()


class MockUser:
    def __init__(self, user_id: str, name: str = "DevTester"):
        self.id = int(user_id)
        self.name = name
        self.display_name = name
        self.mention = f"<@{user_id}>"
        self.bot = False
        self.display_avatar = MockAvatar()
        self.avatar = self.display_avatar

    def __str__(self):
        return f"{self.name}#{self.id}"


class MockGuild:
    def __init__(self, guild_id: int = 999888777, name: str = "Urch Dev Server"):
        self.id = guild_id
        self.name = name
        self.member_count = 42


class MockChannel:
    def __init__(self, channel_id: int = 111222333, name: str = "bot-testing"):
        self.id = channel_id
        self.name = name

    async def send(self, content=None, **kwargs):
        render_response(
            content=content,
            embed=kwargs.get("embed"),
            embeds=kwargs.get("embeds"),
            view=kwargs.get("view"),
            file=kwargs.get("file"),
            files=kwargs.get("files"),
        )


class SimulationSession:
    """Maintains active user context, loaded bot, and currently active UI View."""

    def __init__(self, user_id: str = "123456789", user_name: str = "DevTester"):
        self.user = MockUser(user_id, user_name)
        self.guild = MockGuild()
        self.channel = MockChannel()
        self.bot: Optional[commands.Bot] = None
        self.current_view: Optional[discord.ui.View] = None
        self.current_embed: Optional[discord.Embed] = None
        self.current_content: Optional[str] = None
        self.initialized = False

    async def initialize(self):
        """Initializes the database and loads all Urch command extensions."""
        if self.initialized:
            return

        print("⚡ Initializing database & command registry...")
        await db.initialize()

        # Wire safeguards and rate limiters
        try:
            from rate_limiter import rate_limiter
            from safeguard import check_safeguard
            bot_rate_limiter = rate_limiter
            bot_check_safeguard = check_safeguard
        except Exception:
            bot_rate_limiter = None
            bot_check_safeguard = None

        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        intents.reactions = True

        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.bot.rate_limiter = bot_rate_limiter
        self.bot.check_safeguard = bot_check_safeguard

        # Load command modules from commands/
        commands_dir = os.path.join(PROJECT_ROOT, "commands")
        count = 0
        if os.path.isdir(commands_dir):
            for file in sorted(os.listdir(commands_dir)):
                if file.endswith(".py") and file != "__init__.py":
                    mod_name = f"commands.{file[:-3]}"
                    try:
                        await self.bot.load_extension(mod_name)
                        count += 1
                    except Exception as err:
                        print(f"⚠️  Could not load {mod_name}: {err}")

        self.initialized = True
        print(f"✅ Loaded {count} extensions. Session ready as {self.user.name} (ID: {self.user.id}).")

    def create_interaction(self, command: Optional[Any] = None) -> discord.Interaction:
        """Creates a mock discord.Interaction wired into this session's state."""
        inter = MagicMock(spec=discord.Interaction)
        inter.user = self.user
        inter.guild = self.guild
        inter.channel = self.channel
        inter.client = self.bot
        inter.command = command

        response_done = False

        async def defer(ephemeral=False, thinking=False):
            nonlocal response_done
            response_done = True

        async def send_message(content=None, embed=None, embeds=None, view=None, file=None, files=None, ephemeral=False, **kwargs):
            nonlocal response_done
            response_done = True
            self.current_content = content
            self.current_embed = embed
            if view is not None:
                self.current_view = view
            render_response(content=content, embed=embed, embeds=embeds, view=self.current_view, file=file, files=files)

        async def edit_message(content=None, embed=None, embeds=None, view=None, **kwargs):
            nonlocal response_done
            response_done = True
            if content is not None:
                self.current_content = content
            if embed is not None:
                self.current_embed = embed
            if view is not None:
                self.current_view = view
            render_response(content=self.current_content, embed=self.current_embed, embeds=embeds, view=self.current_view)

        async def followup_send(content=None, embed=None, embeds=None, view=None, file=None, files=None, ephemeral=False, **kwargs):
            self.current_content = content
            self.current_embed = embed
            if view is not None:
                self.current_view = view
            render_response(content=content, embed=embed, embeds=embeds, view=self.current_view, file=file, files=files)

        async def edit_original_response(content=None, embed=None, embeds=None, view=None, **kwargs):
            if content is not None:
                self.current_content = content
            if embed is not None:
                self.current_embed = embed
            if view is not None:
                self.current_view = view
            render_response(content=self.current_content, embed=self.current_embed, embeds=embeds, view=self.current_view)

        inter.response.defer = AsyncMock(side_effect=defer)
        inter.response.send_message = AsyncMock(side_effect=send_message)
        inter.response.edit_message = AsyncMock(side_effect=edit_message)
        inter.response.is_done = MagicMock(side_effect=lambda: response_done)
        inter.followup.send = AsyncMock(side_effect=followup_send)
        inter.edit_original_response = AsyncMock(side_effect=edit_original_response)

        return inter

    # ─────────────────────────────────────────────────────────────────────────
    # Command & Component Dispatch
    # ─────────────────────────────────────────────────────────────────────────

    async def execute_click(self, target_arg: str):
        """Simulates clicking a button or component on the active view."""
        if not self.current_view or not getattr(self.current_view, "children", None):
            print("⚠️  No active view or buttons available to click.")
            return

        target_child = None
        children = self.current_view.children

        # 1. Try 1-based numerical index
        if target_arg.isdigit():
            idx = int(target_arg) - 1
            if 0 <= idx < len(children):
                target_child = children[idx]
            else:
                print(f"❌ Component index [{target_arg}] out of range (1 to {len(children)}).")
                return
        else:
            # 2. Try match by label or emoji (case-insensitive substring or exact match)
            clean_target = target_arg.strip("'\"").lower()
            for child in children:
                lbl = getattr(child, "label", None)
                emoji = getattr(child, "emoji", None)
                if (lbl and clean_target in lbl.lower()) or (emoji and clean_target in str(emoji).lower()):
                    target_child = child
                    break

        if not target_child:
            print(f"❌ Could not find button matching '{target_arg}'. Available choices:")
            for idx, c in enumerate(children, 1):
                lbl = getattr(c, "label", "") or getattr(c, "emoji", "")
                print(f"    [{idx}] {lbl}")
            return

        if getattr(target_child, "disabled", False):
            print(f"⚠️  Button '{getattr(target_child, 'label', target_arg)}' is currently disabled.")
            return

        click_inter = self.create_interaction()
        try:
            print(f"🖱️ Clicking: [{getattr(target_child, 'label', 'Component')}]...")
            await target_child.callback(click_inter)
        except Exception as e:
            print(f"❌ Error during component callback: {type(e).__name__}: {e}")

    async def execute_command(self, raw_input: str):
        """Parses a natural input line and dispatches it to the bot or session."""
        line = raw_input.strip()
        if not line or line.startswith("#"):
            return

        # Strip optional leading slash or exclamation mark
        if line.startswith(("/", "!")):
            line = line[1:].strip()

        try:
            tokens = shlex.split(line, posix=False)
        except Exception:
            tokens = line.split()

        if not tokens:
            return

        cmd_name = tokens[0].lower()
        args = tokens[1:]

        # Built-in Harness Commands
        if cmd_name in ("exit", "quit", "q"):
            return "EXIT"

        if cmd_name == "click":
            if not args:
                print("Usage: click <button_number | 'Button Label'>")
                return
            await self.execute_click(" ".join(args))
            return

        if cmd_name == "user":
            if args:
                self.user = MockUser(args[0], f"User_{args[0][:4]}")
                print(f"👤 Switched active user to: {self.user.id}")
            else:
                print(f"👤 Active user: {self.user.name} (ID: {self.user.id})")
            return

        if cmd_name == "view":
            if self.current_embed or self.current_view or self.current_content:
                render_response(content=self.current_content, embed=self.current_embed, view=self.current_view)
            else:
                print("ℹ️  No active view or embed stored in session.")
            return

        if cmd_name in ("help", "commands"):
            self.show_help()
            return

        # Lookup in bot.tree (App Commands / Groups)
        app_cmds = {c.name.lower(): c for c in self.bot.tree.get_commands()}
        matched_cmd = app_cmds.get(cmd_name)

        # Handle Command Groups (e.g., 'recipes view', 'recipes craft')
        if isinstance(matched_cmd, app_commands.Group):
            if args and args[0].lower() in {sc.name.lower(): sc for sc in matched_cmd.commands}:
                sub_name = args[0].lower()
                sub_cmd = next(sc for sc in matched_cmd.commands if sc.name.lower() == sub_name)
                args = args[1:]
                await self._invoke_app_command(sub_cmd, args)
                return
            else:
                print(f"ℹ️  '{cmd_name}' is a command group. Subcommands: {[c.name for c in matched_cmd.commands]}")
                return

        if matched_cmd and isinstance(matched_cmd, app_commands.Command):
            await self._invoke_app_command(matched_cmd, args)
            return

        # Lookup in bot.commands (Traditional Prefix Commands)
        prefix_cmd = self.bot.get_command(cmd_name)
        if prefix_cmd:
            await self._invoke_prefix_command(prefix_cmd, args)
            return

        print(f"❓ Unknown command: '{cmd_name}'. Type 'help' to see available commands.")

    async def _invoke_app_command(self, cmd: app_commands.Command, raw_args: List[str]):
        """Binds and converts arguments, then calls an app_command."""
        kwargs: Dict[str, Any] = {}
        positional_params = [p for p in cmd.parameters if p.name != "self"]
        pos_idx = 0

        for arg in raw_args:
            # Check for key=value
            if "=" in arg:
                k, v = arg.split("=", 1)
                k = k.strip()
                v = v.strip("'\"")
                param = next((p for p in cmd.parameters if p.name == k), None)
                if param:
                    kwargs[k] = self._convert_param(param, v)
                    continue

            # Positional binding
            if pos_idx < len(positional_params):
                param = positional_params[pos_idx]
                kwargs[param.name] = self._convert_param(param, arg.strip("'\""))
                pos_idx += 1
            else:
                if len(positional_params) == 0:
                    print(f"ℹ️  Note: Command '{cmd.name}' takes no parameters; ignoring '{arg}'.")
                break

        # Supply smart mock defaults for required attachment parameters if not provided
        for param in positional_params:
            if param.name not in kwargs and getattr(param, "type", None) == discord.AppCommandOptionType.attachment:
                if param.required:
                    kwargs[param.name] = MockAttachment()

        inter = self.create_interaction(command=cmd)
        try:
            await cmd._do_call(inter, kwargs)
        except Exception as e:
            print(f"❌ Error executing '{cmd.name}': {type(e).__name__}: {e}")

    async def _invoke_prefix_command(self, cmd: commands.Command, raw_args: List[str]):
        """Invokes a prefix-style command."""
        ctx = MagicMock(spec=commands.Context)
        ctx.bot = self.bot
        ctx.author = self.user
        ctx.guild = self.guild
        ctx.channel = self.channel

        async def send(content=None, embed=None, view=None, file=None, files=None, **kwargs):
            self.current_content = content
            self.current_embed = embed
            if view:
                self.current_view = view
            render_response(content=content, embed=embed, view=self.current_view, file=file, files=files)

        ctx.send = AsyncMock(side_effect=send)

        try:
            await cmd.callback(cmd.cog, ctx, *raw_args) if cmd.cog else await cmd.callback(ctx, *raw_args)
        except Exception as e:
            print(f"❌ Error executing prefix command '{cmd.name}': {type(e).__name__}: {e}")

    def _convert_param(self, param: app_commands.Parameter, val: str) -> Any:
        """Converts string input into the target app_command parameter type."""
        ptype = getattr(param, "type", None)

        # Handle Choice matching
        choices = getattr(param, "choices", None)
        if choices:
            matched = next(
                (c for c in choices if c.name.lower() == val.lower() or str(c.value).lower() == val.lower()),
                None
            )
            cb = getattr(getattr(param, "command", None), "_callback", None)
            ann = cb.__annotations__.get(param.name) if cb and hasattr(cb, "__annotations__") else None
            wants_choice = ann is not None and "Choice" in str(ann)

            if wants_choice:
                if matched:
                    return matched
                return app_commands.Choice(name=val.title(), value=val)
            else:
                return matched.value if matched else val

        try:
            if ptype == discord.AppCommandOptionType.integer:
                return int(val)
            elif ptype == discord.AppCommandOptionType.number:
                return float(val)
            elif ptype == discord.AppCommandOptionType.boolean:
                return val.lower() in ("true", "1", "yes", "y")
            elif ptype == discord.AppCommandOptionType.attachment:
                return MockAttachment(data=val)
            elif ptype == discord.AppCommandOptionType.user:
                return MockUser(val if val.isdigit() else "9999", val)
            else:
                return str(val)
        except Exception:
            return val

    def show_help(self):
        """Displays available simulation commands and registered bot commands."""
        print("\n" + "=" * 65)
        print("🎮 Urch Simulation Harness Commands:")
        print("  <bot command> [args]  Execute any bot command (e.g., 'roll', 'setluck 5.0')")
        print("  click <num | 'label'> Click a button on the active view (e.g., 'click 1')")
        print("  user <user_id>        Inspect or switch the current simulated user")
        print("  view                  Re-display active embed and button choices")
        print("  exit / quit           Exit the simulation session")
        print("\n🤖 Available Bot Slash Commands:")
        for cmd in sorted(self.bot.tree.get_commands(), key=lambda c: c.name):
            if isinstance(cmd, app_commands.Group):
                sub = ", ".join(c.name for c in cmd.commands)
                print(f"  /{cmd.name:<15} (Group: {sub})")
            elif hasattr(cmd, "parameters"):
                p_str = " ".join(f"<{p.name}>" if p.required else f"[{p.name}]" for p in cmd.parameters)
                print(f"  /{cmd.name:<15} {p_str}")
        print("=" * 65 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point & REPL Loop
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    session = SimulationSession()
    await session.initialize()

    # Clean shutdown helper
    async def cleanup():
        print("\nCleaning up resources...")
        try:
            from providers import close_session
            await close_session()
        except Exception:
            pass
        await db.close()

    # Mode 1: Command line arguments passed -> Run & Exit
    if len(sys.argv) > 1:
        for cmd_line in sys.argv[1:]:
            print(f"\n>>> {cmd_line}")
            res = await session.execute_command(cmd_line)
            if res == "EXIT":
                break
        await cleanup()
        return

    # Mode 2: Piped Stdin (batch execution)
    if not sys.stdin.isatty():
        print("📥 Reading commands from standard input...")
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            print(f"\n>>> {line}")
            res = await session.execute_command(line)
            if res == "EXIT":
                break
        await cleanup()
        return

    # Mode 3: Interactive REPL
    print("\n" + "═" * 65)
    print("  URCH NIGHTLY SIMULATOR - Local Agent & Interactive REPL")
    print("  Type any command (e.g. 'roll', 'inventory', 'help') or 'exit'")
    print("═" * 65 + "\n")

    try:
        while True:
            try:
                line = input(f"urch [{session.user.id}]> ")
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n(Use 'exit' or Ctrl+D to quit)")
                continue

            res = await session.execute_command(line)
            if res == "EXIT":
                break
    finally:
        await cleanup()
        print("👋 Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
