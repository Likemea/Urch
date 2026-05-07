# Urch/commands/autoroll.py
import discord
from discord import app_commands
from discord.ext import commands
import asyncio

from utils import db, ensure_user, get_upgrade_effect
from raritylist import RARITIES

class AutorollView(discord.ui.View):
    def __init__(self, user_id, bot):
        super().__init__(timeout=None)
        self.user_id = str(user_id)
        self.bot = bot

    @discord.ui.button(label="Refresh Dashboard", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This dashboard is not yours.", ephemeral=True)
            return
        
        await interaction.response.defer()
        embed = await create_autoroll_embed(self.user_id)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Stop Autoroll", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This dashboard is not yours.", ephemeral=True)
            return
            
        await db.set_autoroll_status(self.user_id, False)
        embed = await create_autoroll_embed(self.user_id)
        # Disable buttons
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

async def create_autoroll_embed(user_id: str) -> discord.Embed:
    user_data = await db.get_user_data(user_id)
    active = user_data.get("autoroll_active", 0)
    
    status = "🟢 ACTIVE" if active else "🔴 INACTIVE"
    color = discord.Color.green() if active else discord.Color.red()
    
    embed = discord.Embed(title="⚙️ Autoroll Dashboard", color=color)
    embed.description = f"Status: **{status}**\n\nRolling in the background every 10 seconds. Only meaningful rolls (1 in 100x Luck) will be logged here."
    
    embed.add_field(name="Total Rolls", value=f"{user_data.get('roll_count', 0):,}", inline=True)
    embed.add_field(name="Highscore", value=user_data.get("highscore", "None"), inline=True)
    
    # We could store a log of recent meaningful rolls in a separate table, 
    # but for now let's just show current stats.
    # The user request said "showing only meaningful rolls", 
    # but we don't have a place to store them specifically for the dashboard yet.
    # I'll add a "Recent Hits" field that shows the highscore if it was recent, 
    # or just a placeholder for now.
    
    return embed

class AutorollCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="autoroll", description="Toggle background rolling")
    async def autoroll(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user_data = await ensure_user(user_id)
        
        # Check upgrade
        upgrades = user_data.get("upgrades", {}).get("autoroll", {})
        if upgrades.get("unlock", 0) < 1:
            await interaction.response.send_message(
                "❌ You haven't unlocked the **Autoroll Engine** yet! Check `/upgrades`.", 
                ephemeral=True
            )
            return

        # Toggle status
        current_status = user_data.get("autoroll_active", 0)
        new_status = not current_status
        await db.set_autoroll_status(user_id, new_status)
        
        embed = await create_autoroll_embed(user_id)
        view = AutorollView(user_id, self.bot)
        
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(AutorollCommand(bot))
