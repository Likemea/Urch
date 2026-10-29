# Urch/commands/setluck.py
import math
import discord
from discord import app_commands
from discord.ext import commands

from utils import ensure_user, save_user_data, format_number


class SetLuckCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setluck", description="Set your effective luck")
    async def setluck(self, interaction: discord.Interaction, value: float = 0.0):
        try:
            f_val = float(value)
        except (ValueError, TypeError):
            await interaction.response.send_message(
                "❌ Luck value must be a valid finite number (>= -1).", ephemeral=True
            )
            return

        if math.isnan(f_val) or math.isinf(f_val) or f_val < -1.0 or (-1.0 < f_val < 0.0):
            await interaction.response.send_message(
                "❌ Invalid luck value. Use -1 to remove override, 0 for max base luck, or a positive number.",
                ephemeral=True,
            )
            return

        user_id = str(interaction.user.id)
        from database import db

        async with db.lock_user(user_id):
            user = await ensure_user(user_id)

            personal_max = user.get("max_luck", 1.0)

            if f_val == -1.0:
                if user.get("luck_override") is not None:
                    user["luck_override"] = None
                    await db.update_user_value("users", "luck_override", None, user_id)
                    description = "🎲 Luck override removed"
                    color = discord.Color.blue()
                else:
                    description = "❌ No luck override active"
                    color = discord.Color.red()

            elif f_val == 0.0:
                user["luck_multi"] = personal_max
                user["luck_override"] = None
                await save_user_data(user_id, user)
                await db.update_user_value("users", "luck_override", None, user_id)
                description = f"🍀 Base luck set to your max: **{format_number(personal_max)}**"
                color = discord.Color.green()

            else:
                override_value = f_val

                if override_value > personal_max:
                    override_value = personal_max
                    description = (
                        f"⚠️ Override capped to your max: **{format_number(personal_max)}**"
                    )
                else:
                    description = f"🍀 Effective luck set to **{format_number(override_value)}**"

                user["luck_override"] = override_value
                color = discord.Color.gold()
                await save_user_data(user_id, user)

        embed = discord.Embed(title="🍀 Luck Configuration", description=description, color=color)

        embed.add_field(name="Max Luck", value=f"**{format_number(personal_max)}**", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SetLuckCommand(bot))
