# Urch/commands/setluck.py
import discord
from discord import app_commands
from discord.ext import commands

from utils import ensure_user, save_user_data, get_user_data, format_number

class SetLuckCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setluck", description="Set your effective luck")
    async def setluck(self, interaction: discord.Interaction, value: float = 0.0):
        user_id = str(interaction.user.id)
        user = await ensure_user(user_id)
        
        personal_max = user.get("max_luck", 1.0)
        
        if value == -1:
            if "luck_override" in user:
                del user["luck_override"]
                description = "🎲 Luck override removed"
                color = discord.Color.blue()
            else:
                description = "❌ No luck override active"
                color = discord.Color.red()
                
        elif value == 0:
            user["luck_multi"] = personal_max
            if "luck_override" in user:
                del user["luck_override"]
            description = f"🍀 Base luck set to your max: **{format_number(personal_max)}**"
            color = discord.Color.green()
            
        else:
            override_value = float(value)
            
            if override_value > personal_max:
                override_value = personal_max
                description = f"⚠️ Override capped to your max: **{format_number(personal_max)}**"
            else:
                description = f"🍀 Effective luck set to **{format_number(override_value)}**"
            
            user["luck_override"] = override_value
            color = discord.Color.gold()
        
        await save_user_data(user_id, user)
        
        embed = discord.Embed(
            title="🍀 Luck Configuration",
            description=description,
            color=color
        )
        
        embed.add_field(
            name="Max Luck", 
            value=f"**{format_number(personal_max)}**", 
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(SetLuckCommand(bot))