# Urch/commands/safety.py
import time
import discord
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
                await db.conn.execute("DELETE FROM conversation_history")
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


async def setup(bot):
    await bot.add_cog(SafetyCommand(bot))
