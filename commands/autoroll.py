# Urch/commands/autoroll.py
import discord
from discord import app_commands
from discord.ext import commands

from utils import db, ensure_user


class AutorollView(discord.ui.View):
    def __init__(self, user_id, bot):
        super().__init__(timeout=None)
        self.user_id = str(user_id)
        self.bot = bot

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This dashboard is not yours.", ephemeral=True)
            return

        await interaction.response.defer()
        embed = await create_autoroll_embed(self.user_id)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This dashboard is not yours.", ephemeral=True)
            return

        await db.set_autoroll_status(self.user_id, False)
        embed = await create_autoroll_embed(self.user_id)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)


async def create_autoroll_embed(user_id: str) -> discord.Embed:
    user_data = await db.get_user_data(user_id)
    active = user_data.get("autoroll_active", 0)

    status = "🟢 ON" if active else "🔴 OFF"
    color = discord.Color.green() if active else discord.Color.red()

    embed = discord.Embed(title="⚙️ Autoroll Dashboard", color=color)
    embed.description = f"Status: **{status}**\n\nRolling in the background every 10 seconds. Only rare rolls ([your luck]*100) will be shown"

    embed.add_field(name="Total Rolls", value=f"{user_data.get('roll_count', 0):,}", inline=True)
    embed.add_field(name="Best Roll", value=user_data.get("highscore", "None"), inline=True)

    rare_hits = await db.get_recent_rare_hits(user_id, limit=5)
    if rare_hits:
        hits_text = ""
        for hit in rare_hits:
            rarity = hit["rarity_name"]
            try:
                dt = discord.utils.parse_time(hit["timestamp"])
                time_str = f"<t:{int(dt.timestamp())}:R>"
            except:
                time_str = hit["timestamp"]

            hits_text += f"• **{rarity}** - {time_str}\n"

        embed.add_field(name="🎰 Recent Rolls", value=hits_text, inline=False)
    else:
        embed.add_field(
            name="🎰 Recent Rolls", value="No rare rolls yet. Keep rolling!", inline=False
        )

    return embed


class AutorollCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="autoroll", description="Toggle auto rolling")
    async def autoroll(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user_data = await ensure_user(user_id)

        upgrades = user_data.get("upgrades", {}).get("roll", {})
        if upgrades.get("autoroll_unlock", 0) < 1:
            await interaction.response.send_message(
                "❌ You haven't unlocked **Autoroll** yet! Check `/upgrades`.", ephemeral=True
            )
            return

        current_status = user_data.get("autoroll_active", 0)
        new_status = not current_status
        await db.set_autoroll_status(user_id, new_status)

        embed = await create_autoroll_embed(user_id)
        view = AutorollView(user_id, self.bot)

        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(AutorollCommand(bot))
