# Urch/commands/safety.py
import time
import discord
import asyncio
from discord import app_commands
from discord.ext import commands
from database import db

OWNER_ID = 477168479812845568

def format_uptime(seconds: float) -> str:
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    m = int((seconds % 3600) // 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


class SafetyCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="safety", description="🔒 Owner control panel")
    async def safety(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("⛔ This command is restricted.", ephemeral=True)
            return
        
        view = SafetyDashboard(self.bot)
        embed = await view.build_overview_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ───────────────────────────────
# MAIN DASHBOARD VIEW
# ───────────────────────────────

class SafetyDashboard(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=600)
        self.bot = bot
    
    def _get_rl(self):
        return getattr(self.bot, 'rate_limiter', None)
    
    async def build_overview_embed(self) -> discord.Embed:
        rl = self._get_rl()
        stats = rl.get_stats() if rl else {}
        
        uptime = format_uptime(stats.get("uptime_seconds", 0))
        active = stats.get("active_users", 0)
        total_req = stats.get("total_requests", 0)
        total_denied = stats.get("total_denied", 0)
        multiplier = stats.get("dynamic_multiplier", 1.0)
        kill = stats.get("kill_switch", False)
        
        # DB stats
        try:
            db_stats = await db.get_conversation_stats()
            db_rows = db_stats.get("total_rows", "?")
        except Exception:
            db_rows = "?"
        
        desc = f"**Uptime:** {uptime}\n"
        desc += f"**Active Users (1m):** {active}\n"
        desc += f"**Total Requests:** {total_req}\n"
        desc += f"**Denied Requests:** {total_denied}\n"
        desc += f"**Dynamic Multiplier:** ×{multiplier}\n"
        desc += f"**Conversation DB Rows:** {db_rows}\n"
        desc += f"**Kill Switch:** {'🔴 ACTIVE' if kill else '🟢 Off'}\n"
        desc += f"**Guilds:** {len(self.bot.guilds)}"
        
        embed = discord.Embed(title="🛡️ Safety Control Panel", description=desc, color=discord.Color.red() if kill else discord.Color.dark_green())
        return embed
    
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", row=0)
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.build_overview_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Rate Limits", style=discord.ButtonStyle.primary, emoji="⏱", row=0)
    async def rate_limits_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RateLimitPanel(self.bot, self)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Database", style=discord.ButtonStyle.primary, emoji="🗄️", row=0)
    async def database_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DatabasePanel(self.bot, self)
        embed = await view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="User Data", style=discord.ButtonStyle.primary, emoji="👥", row=0)
    async def user_data_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = UserManagerPanel(self.bot, self)
        embed = await view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Kill Switch", style=discord.ButtonStyle.danger, emoji="⛔", row=1)
    async def kill_switch_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        rl = self._get_rl()
        if rl:
            rl.kill_switch = not rl.kill_switch
            state = "🔴 ACTIVATED" if rl.kill_switch else "🟢 Deactivated"
            embed = await self.build_overview_embed()
            embed.set_footer(text=f"Kill switch {state}")
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Toggle Limiter", style=discord.ButtonStyle.secondary, emoji="🔘", row=1)
    async def toggle_limiter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        rl = self._get_rl()
        if rl:
            rl.enabled = not rl.enabled
            state = "🟢 Enabled" if rl.enabled else "🔴 Disabled"
            embed = await self.build_overview_embed()
            embed.set_footer(text=f"Rate limiter {state}")
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()


# ───────────────────────────────
# RATE LIMIT PANEL
# ───────────────────────────────

class RateLimitPanel(discord.ui.View):
    def __init__(self, bot, parent):
        super().__init__(timeout=600)
        self.bot = bot
        self.parent = parent
    
    def _get_rl(self):
        return getattr(self.bot, 'rate_limiter', None)
    
    def build_embed(self) -> discord.Embed:
        rl = self._get_rl()
        stats = rl.get_stats() if rl else {}
        tiers = stats.get("tier_limits", {})
        
        desc = f"**Status:** {'🟢 Enabled' if stats.get('enabled') else '🔴 Disabled'}\n"
        desc += f"**Dynamic Scaling:** {'🟢 On' if stats.get('dynamic_enabled') else '🔴 Off'}\n"
        desc += f"**Current Multiplier:** ×{stats.get('dynamic_multiplier', 1.0)}\n\n"
        
        for tier_name, limits in tiers.items():
            emoji = {"light": "⚡", "medium": "🔘", "heavy": "🧠"}.get(tier_name, "•")
            desc += f"{emoji} **{tier_name.title()}**: {limits['rps']} RPS / {limits['rpm']} RPM\n"
        
        embed = discord.Embed(title="⏱ Rate Limit Configuration", description=desc, color=discord.Color.blue())
        return embed
    
    @discord.ui.button(label="Edit Light", style=discord.ButtonStyle.secondary, emoji="⚡", row=0)
    async def edit_light(self, interaction: discord.Interaction, button: discord.ui.Button):
        rl = self._get_rl()
        tier = rl.tier_limits.get("light", {}) if rl else {}
        await interaction.response.send_modal(TierEditModal("light", tier.get("rps", 1.0), tier.get("rpm", 20), self))
    
    @discord.ui.button(label="Edit Medium", style=discord.ButtonStyle.secondary, emoji="🔘", row=0)
    async def edit_medium(self, interaction: discord.Interaction, button: discord.ui.Button):
        rl = self._get_rl()
        tier = rl.tier_limits.get("medium", {}) if rl else {}
        await interaction.response.send_modal(TierEditModal("medium", tier.get("rps", 0.5), tier.get("rpm", 12), self))
    
    @discord.ui.button(label="Edit Heavy", style=discord.ButtonStyle.secondary, emoji="🧠", row=0)
    async def edit_heavy(self, interaction: discord.Interaction, button: discord.ui.Button):
        rl = self._get_rl()
        tier = rl.tier_limits.get("heavy", {}) if rl else {}
        await interaction.response.send_modal(TierEditModal("heavy", tier.get("rps", 0.33), tier.get("rpm", 8), self))
    
    @discord.ui.button(label="Toggle Dynamic", style=discord.ButtonStyle.primary, emoji="📊", row=1)
    async def toggle_dynamic(self, interaction: discord.Interaction, button: discord.ui.Button):
        rl = self._get_rl()
        if rl:
            rl.dynamic_enabled = not rl.dynamic_enabled
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="↩", row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent.build_overview_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent)


class TierEditModal(discord.ui.Modal):
    def __init__(self, tier_name: str, current_rps: float, current_rpm: int, panel):
        super().__init__(title=f"Edit {tier_name.title()} Tier")
        self.tier_name = tier_name
        self.panel = panel
        
        self.rps_input = discord.ui.TextInput(
            label="Requests Per Second (0.1 - 5.0)",
            placeholder=str(current_rps),
            default=str(current_rps),
            max_length=5,
            required=True
        )
        self.rpm_input = discord.ui.TextInput(
            label="Requests Per Minute (1 - 60)",
            placeholder=str(current_rpm),
            default=str(current_rpm),
            max_length=3,
            required=True
        )
        self.add_item(self.rps_input)
        self.add_item(self.rpm_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            rps = max(0.1, min(5.0, float(self.rps_input.value)))
            rpm = max(1, min(60, int(self.rpm_input.value)))
            
            rl = getattr(interaction.client, 'rate_limiter', None)
            if rl:
                rl.set_tier_limit(self.tier_name, rps=rps, rpm=rpm)
            
            embed = self.panel.build_embed()
            embed.set_footer(text=f"✅ Updated {self.tier_name}: {rps} RPS / {rpm} RPM")
            await interaction.response.edit_message(embed=embed, view=self.panel)
        except ValueError:
            await interaction.response.send_message("❌ Invalid number format.", ephemeral=True)


# ───────────────────────────────
# DATABASE PANEL
# ───────────────────────────────

class DatabasePanel(discord.ui.View):
    def __init__(self, bot, parent):
        super().__init__(timeout=600)
        self.bot = bot
        self.parent = parent
    
    async def build_embed(self) -> discord.Embed:
        try:
            stats = await db.get_conversation_stats()
        except Exception:
            stats = {"total_rows": "?", "top_guilds": [], "top_users": []}
        
        desc = f"**Total Conversation Rows:** {stats.get('total_rows', '?')}\n\n"
        
        top_guilds = stats.get("top_guilds", [])
        if top_guilds:
            desc += "**Top Guilds (by row count):**\n"
            for gid, cnt in top_guilds[:5]:
                guild = self.bot.get_guild(int(gid)) if gid else None
                name = guild.name if guild else f"ID:{gid}"
                desc += f"• {name}: {cnt} rows\n"
            desc += "\n"
        
        top_users = stats.get("top_users", [])
        if top_users:
            desc += "**Top Users (by row count):**\n"
            for uid, cnt in top_users[:5]:
                try:
                    user = self.bot.get_user(int(uid))
                    name = user.name if user else f"ID:{uid}"
                except Exception:
                    name = f"ID:{uid}"
                desc += f"• {name}: {cnt} rows\n"
        
        embed = discord.Embed(title="🗄️ Database Overview", description=desc, color=discord.Color.dark_grey())
        return embed
    
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", row=0)
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Purge All History", style=discord.ButtonStyle.danger, emoji="🗑️", row=0)
    async def purge_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PurgeConfirmView(self.bot, self)
        embed = discord.Embed(
            title="⚠️ Confirm Purge",
            description="This will delete **ALL** conversation history rows.\nThis cannot be undone!",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Purge Server (Discord)", style=discord.ButtonStyle.danger, emoji="🧹", row=1)
    async def purge_server_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GuildPurgeModal(self.bot))

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="↩", row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent.build_overview_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent)


class PurgeConfirmView(discord.ui.View):
    def __init__(self, bot, parent):
        super().__init__(timeout=30)
        self.bot = bot
        self.parent = parent
    
    @discord.ui.button(label="Yes, Purge Everything", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            async with db._lock:
                async with db.conn.execute("DELETE FROM conversation_history"):
                    await db.conn.commit()
            embed = await self.parent.build_embed()
            embed.set_footer(text="✅ All conversation history has been purged.")
            await interaction.response.edit_message(embed=embed, view=self.parent)
        except Exception as e:
            await interaction.response.edit_message(
                embed=discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red()),
                view=self.parent
            )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent)

class PurgeStatusView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=600) 
        self.is_cancelled = False

    @discord.ui.button(label="Stop Purge", style=discord.ButtonStyle.danger, emoji="🛑")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.is_cancelled = True
        
        button.disabled = True
        button.label = "Stopping... (Waiting for current channel to finish)"
        button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

class GuildPurgeModal(discord.ui.Modal, title="Purge Server Messages"):
    guild_id_input = discord.ui.TextInput(
        label="Guild ID",
        placeholder="Paste the server ID here...",
        min_length=17,
        max_length=20,
        required=True
    )
    
    limit_input = discord.ui.TextInput(
        label="Message Search Limit (Per Channel)",
        placeholder="e.g., 2000",
        default="2000",
        max_length=5,
        required=True
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        guild_id_str = self.guild_id_input.value
        
        try:
            search_limit = int(self.limit_input.value)
        except ValueError:
            return await interaction.response.send_message("❌ Search limit must be an integer.", ephemeral=True)
        
        try:
            guild = self.bot.get_guild(int(guild_id_str))
            if not guild:
                return await interaction.response.send_message("❌ I am not in that server.", ephemeral=True)

            await interaction.response.defer(ephemeral=True)

            # We removed the DB fetching here. We are going in blind and scanning!
            total_deleted = 0
            channels_processed = 0
            
            status_embed = discord.Embed(
                title=f"🧹 Purging: {guild.name}",
                description=f"Scanning up to {search_limit} messages per channel...\nPreparing channel list...",
                color=discord.Color.blue()
            )
            
            status_view = PurgeStatusView()
            status_msg = await interaction.followup.send(embed=status_embed, view=status_view, ephemeral=True)

            # Gather ALL possible text sources securely
            channels_to_scan = []
            channels_to_scan.extend(getattr(guild, 'text_channels', []))
            channels_to_scan.extend(getattr(guild, 'voice_channels', []))
            channels_to_scan.extend(getattr(guild, 'stage_channels', []))
            channels_to_scan.extend(getattr(guild, 'forum_channels', []))
            
            # Handle Threads (Active + Archived)
            channels_to_scan.extend(getattr(guild, 'threads', []))
            for channel in getattr(guild, 'text_channels', []):
                try:
                    async for thread in channel.archived_threads(limit=None):
                        channels_to_scan.append(thread)
                except Exception:
                    continue
            
            total_channels = len(channels_to_scan)
            last_update_time = time.time()
            last_update_deleted = 0
            last_update_channels = 0

            def build_progress_bar(current, total, length=15):
                percent = current / total if total > 0 else 1.0
                filled = int(length * percent)
                bar = "█" * filled + "░" * (length - filled)
                return f"`[{bar}] {int(percent * 100)}%`"

            # Execution Loop
            for channel in channels_to_scan:
                if status_view.is_cancelled:
                    break
                
                try:
                    perms = channel.permissions_for(guild.me)
                    if not perms.read_message_history:
                        channels_processed += 1
                        continue

                    # ONLY check if the bot sent it. No DB required.
                    deleted = await channel.purge(
                        limit=search_limit, 
                        check=lambda m: m.author.id == self.bot.user.id,
                        bulk=True
                    )
                    
                    if deleted:
                        total_deleted += len(deleted)
                    
                except discord.Forbidden:
                    pass 
                except discord.HTTPException as e:
                    if e.status == 429:
                        await asyncio.sleep(e.retry_after or 5.0)
                except Exception:
                    pass 
                
                channels_processed += 1
                
                # Progress updates 
                current_time = time.time()
                time_since_last = current_time - last_update_time
                channels_since_last = channels_processed - last_update_channels
                deleted_since_last = total_deleted - last_update_deleted
                
                # UPDATE LOGIC: 
                # Has it been at least 3s AND (did we scan 5+ channels OR delete 50+ msgs)?
                # OR has it been 8s? (The "heartbeat" check so the user doesn't think it froze)
                
                needs_update = (time_since_last >= 3.0 and (channels_since_last >= 5 or deleted_since_last >= 50)) or (time_since_last >= 8.0)

                if needs_update:
                    progress_bar = build_progress_bar(channels_processed, total_channels)
                    status_embed.description = (
                        f"{progress_bar}\n\n"
                        f"**Channels Scanned:** {channels_processed} / {total_channels}\n"
                        f"**Messages Deleted:** `{total_deleted}`\n"
                        f"*(Searching up to {search_limit} msgs per channel)*"
                    )
                    try:
                        await status_msg.edit(embed=status_embed)
                        last_update_time = current_time
                        last_update_deleted = total_deleted
                        last_update_channels = channels_processed
                    except discord.HTTPException:
                        pass
                
                if len(deleted) > 0:
                    await asyncio.sleep(1.0)
                else:
                    await asyncio.sleep(0.1)

            # Final Report
            if status_view.is_cancelled:
                status_embed.title = "🛑 Purge Aborted"
                status_embed.color = discord.Color.orange()
                status_embed.description = (
                    f"**Operation manually stopped.**\n\n"
                    f"Wiped **{total_deleted}** messages across **{channels_processed}** sources before stopping.\n"
                    f"⚠️ *Database entries for this server were NOT cleared because the operation did not finish.*"
                )
                await status_msg.edit(embed=status_embed, view=None)
            else:
                # Wipe the entire guild from DB, regardless of purge results
                try:
                    async with db._lock:
                        async with db.conn.execute("DELETE FROM conversation_history WHERE guild_id = ?", (guild_id_str,)):
                            await db.conn.commit()
                    db_wiped_msg = f"\nAll database entries for Guild `{guild_id_str}` have been cleared."
                except Exception as e:
                    db_wiped_msg = f"\n⚠️ *Failed to clear database entries: {e}*"
                
                status_embed.title = "✅ Purge Complete"
                status_embed.color = discord.Color.green()
                
                if total_deleted > 0:
                    status_embed.description = (
                        f"{build_progress_bar(1, 1)}\n\n"
                        f"Successfully wiped **{total_deleted}** messages across **{channels_processed}** sources."
                        f"{db_wiped_msg}"
                    )
                else:
                    status_embed.description = (
                        f"{build_progress_bar(1, 1)}\n\n"
                        f"Processed **{channels_processed}** sources but found **0** messages to delete."
                        f"{db_wiped_msg}"
                    )
                await status_msg.edit(embed=status_embed, view=None)

        except ValueError:
            await interaction.followup.send("❌ Invalid ID format.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Operation stopped gracefully due to unexpected error: {e}", ephemeral=True)


# ───────────────────────────────
# USER MANAGEMENT PANEL
# ───────────────────────────────

KEY_TO_TABLE = {
    "roll_count": "users",
    "highscore": "users",
    "luck_multi": "users",
    "max_luck": "users",
    "clover_multi": "users",
    "clover_every": "users",
    "clovers_earned": "users",
    "luck_override": "users",
    "autoroll_active": "users",
    "max_completion_tokens": "user_params",
    "temperature": "user_params",
    "top_p": "user_params",
    "model": "user_params",
    "reasoning": "user_params",
}

class UserManagerPanel(discord.ui.View):
    def __init__(self, bot, parent):
        super().__init__(timeout=600)
        self.bot = bot
        self.parent = parent
    
    async def build_embed(self) -> discord.Embed:
        try:
            stats = await db.get_general_stats()
        except Exception:
            stats = {"total_users": "?", "total_inventory_items": "?", "total_clovers": "?"}
        
        desc = f"**Total Users:** {stats.get('total_users', '?')}\n"
        desc += f"**Total Items Discovered:** {stats.get('total_inventory_items', '?')}\n"
        desc += f"**Total Clovers in Economy:** {stats.get('total_clovers', '?')}\n\n"
        desc += "Use the buttons below to manage specific user data or apply global changes."
        
        embed = discord.Embed(title="👥 User Data Management", description=desc, color=discord.Color.blue())
        return embed
    
    @discord.ui.button(label="Inspect User", style=discord.ButtonStyle.secondary, emoji="🔍", row=0)
    async def inspect_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UserInspectModal(self))
        
    @discord.ui.button(label="Modify Value", style=discord.ButtonStyle.secondary, emoji="✏️", row=0)
    async def modify_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UserModifyModal(self))
        
    @discord.ui.button(label="Delete User", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UserDeleteModal(self))
        
    @discord.ui.button(label="Global Reset", style=discord.ButtonStyle.danger, emoji="🧨", row=1)
    async def reset_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = GlobalResetConfirmView(self.bot, self)
        embed = discord.Embed(
            title="☢️ DANGER: Global Reset",
            description="This will wipe **ALL** user progress, luck, items, and settings.\n\n**THIS ACTION IS IRREVERSIBLE.**",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="↩", row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent.build_overview_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent)

class UserInspectModal(discord.ui.Modal, title="Inspect User Data"):
    user_id_input = discord.ui.TextInput(label="User ID", placeholder="Enter Discord ID...", min_length=17, max_length=20, required=True)
    
    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction: discord.Interaction):
        user_id = self.user_id_input.value
        try:
            data = await db.get_user_data(user_id)
            params = await db.get_user_params(user_id)
            
            if not data:
                return await interaction.response.send_message(f"❌ No user data found for `{user_id}`.", ephemeral=True)
            
            # Format main data
            main_info = f"**Rolls:** {data.get('roll_count', 0)}\n"
            main_info += f"**Luck Multi:** {data.get('luck_multi', 1.0)}x\n"
            main_info += f"**Max Luck:** {data.get('max_luck', 1.0)}x\n"
            main_info += f"**Clovers:** {data.get('currencies', {}).get('clovers', 0)}\n"
            main_info += f"**Autoroll:** {'Enabled' if data.get('autoroll_active') else 'Disabled'}"
            
            # Format params
            param_info = f"**Model:** {params.get('model', 'Auto')}\n"
            param_info += f"**Temp:** {params.get('temperature', 0.75)}\n"
            param_info += f"**Tokens:** {params.get('max_completion_tokens', 1000)}\n"
            param_info += f"**Persona:** {params.get('active_persona', 'Default')}"
            
            embed = discord.Embed(title=f"👤 Data for {user_id}", color=discord.Color.green())
            embed.add_field(name="Main Stats", value=main_info, inline=True)
            embed.add_field(name="AI Params", value=param_info, inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

class UserModifyModal(discord.ui.Modal, title="Modify User/Global Value"):
    scope_input = discord.ui.TextInput(label="Scope (User ID or 'global')", placeholder="global", default="global", required=True)
    key_input = discord.ui.TextInput(label="Key (e.g. temperature, luck_multi)", placeholder="temperature", required=True)
    value_input = discord.ui.TextInput(label="New Value", placeholder="1.0", required=True)
    
    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction: discord.Interaction):
        scope = self.scope_input.value.lower()
        key = self.key_input.value.lower()
        raw_val = self.value_input.value
        
        user_id = None if scope == "global" else scope
        
        table = KEY_TO_TABLE.get(key)
        if not table:
            return await interaction.response.send_message(f"❌ Unknown key: `{key}`. Check `KEY_TO_TABLE` in code.", ephemeral=True)
        
        # Try to infer type
        try:
            if "." in raw_val:
                value = float(raw_val)
            elif raw_val.isdigit():
                value = int(raw_val)
            elif raw_val.lower() in ["true", "false"]:
                value = 1 if raw_val.lower() == "true" else 0
            else:
                value = raw_val
        except ValueError:
            value = raw_val

        try:
            await db.update_user_value(table, key, value, user_id)
            scope_str = "Globally" if not user_id else f"for user `{user_id}`"
            await interaction.response.send_message(f"✅ Updated `{key}` to `{value}` {scope_str}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

class UserDeleteModal(discord.ui.Modal, title="Delete User Data"):
    user_id_input = discord.ui.TextInput(label="User ID", placeholder="Enter Discord ID...", min_length=17, max_length=20, required=True)
    
    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction: discord.Interaction):
        user_id = self.user_id_input.value
        view = UserDeleteConfirmView(user_id, self.panel)
        embed = discord.Embed(
            title="⚠️ Confirm Deletion",
            description=f"Are you sure you want to delete **ALL** data for user `{user_id}`?\nThis cannot be undone.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class UserDeleteConfirmView(discord.ui.View):
    def __init__(self, user_id, panel):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.panel = panel
    
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await db.delete_user_data(self.user_id)
            await interaction.response.edit_message(content=f"✅ User `{self.user_id}` data wiped.", embed=None, view=None)
        except Exception as e:
            await interaction.response.edit_message(content=f"❌ Error: {e}", embed=None, view=None)

class GlobalResetConfirmView(discord.ui.View):
    def __init__(self, bot, panel):
        super().__init__(timeout=30)
        self.bot = bot
        self.panel = panel
    
    @discord.ui.button(label="Yes, RESET EVERYTHING", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await db.reset_all_user_data()
            embed = await self.panel.build_embed()
            embed.set_footer(text="✅ All user data has been factory reset.")
            await interaction.response.edit_message(embed=embed, view=self.panel)
        except Exception as e:
            await interaction.response.edit_message(content=f"❌ Error: {e}", embed=None, view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.panel.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.panel)

async def setup(bot):
    await bot.add_cog(SafetyCommand(bot))
