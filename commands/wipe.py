# Urch/commands/wipe.py
import discord
from discord import app_commands
from discord.ext import commands
from database import db


class WipeCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="wipe", description="Clear short-term memory")
    async def wipe(self, interaction: discord.Interaction):
        is_private = interaction.guild_id is None
        user_id = str(interaction.user.id)

        if is_private:
            success = await db.clear_conversation_history(user_id=user_id)
            if success:
                await interaction.response.send_message(
                    "🧹 This DM history has been cleared.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "ℹ️ You have no history to clear here.", ephemeral=True
                )
        else:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "⚠️ Only admins can clear server history.", ephemeral=True
                )
                return
            guild_id = str(interaction.guild.id)
            success = await db.clear_conversation_history(guild_id=guild_id)
            if success:
                await interaction.response.send_message(
                    f"🧹 Server history for **{interaction.guild.name}** has been cleared."
                )
            else:
                await interaction.response.send_message(
                    "ℹ️ This server has no stored history.", ephemeral=True
                )


async def setup(bot):
    await bot.add_cog(WipeCommand(bot))
