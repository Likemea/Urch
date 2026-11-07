import discord
from discord import app_commands
from discord.ext import commands

from systems.game.utils import (
    ensure_user,
    has_requirements,
    consume_requirements,
    currency_count,
    RARITY_ID_TO_NAME,
)


class RefineryCommand(
    commands.GroupCog, group_name="refinery", group_description="Refine Items and Compounds"
):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="view",description="View recipes")
    async def view(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except TypeError:
            pass
        user_id = str(interaction.user.id)
        user = await ensure_user(user_id)


async def setup(bot):
    await bot.add_cog(RefineryCommand(bot))
