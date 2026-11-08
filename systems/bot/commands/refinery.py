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


class RefineryView(discord.ui.View):
    def __init__(
        self,
        user_id: str,
        inventory: dict[str, int],
        bot=None,
    ):
        super().__init__(timeout=180)
        self.user_id = str(user_id)
        self.inventory = dict(inventory)
        self.bot = bot

        self.tab = 0  # each item recipe is grouped into a category
        self.page = 0

        self.rebuild_components()

    def rebuild_components(self):
        # self.clear_items()

        # row 0: category tabs
        ref_fuel_btn = discord.ui.Button(
            label="🛢️",
            style=discord.ButtonStyle.primary,
            disabled=False,
            row=0,
        )

        autoroll_fuel_btn = discord.ui.Button(
            label="🍀🛢️",
            style=discord.ButtonStyle.primary,
            disabled=False,
            row=0,
        )
        
        async def _check_owner(self, interaction: discord.Interaction) -> bool:
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("This isn't your menu.", ephemeral=True)
                return False
            return True


class RefineryCommand(
    commands.GroupCog, group_name="refinery", group_description="Refine Items and Compounds"
):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="view", description="View recipes")
    async def view(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)


async def setup(bot):
    await bot.add_cog(RefineryCommand(bot))
