import discord
from discord import app_commands
from discord.ext import commands

from systems.game.refineryrecipes import (
    ITEM_DATA,
    REFINERY_RECIPES,
    REFINERY_TABS,
)
from systems.game.utils import (
    get_user_data,
    save_user_data,
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
        self.curr_item = "defaultium"

        self.rebuild_components()

    def rebuild_components(self):
        self.clear_items()

        # row 0: category tabs
        ref_fuel_btn = discord.ui.Button(
            label="🛢️",
            style=discord.ButtonStyle.primary,
            disabled=False,
            row=0,
        )
        ref_fuel_btn.callback = self.ref_fuel_tab
        self.add_item(ref_fuel_btn)

        autoroll_fuel_btn = discord.ui.Button(
            label="🍀🛢️",
            style=discord.ButtonStyle.primary,
            disabled=False,
            row=0,
        )
        autoroll_fuel_btn.callback = self.autoroll_fuel_tab
        self.add_item(autoroll_fuel_btn)

        compound_btn = discord.ui.Button(
            label="C",
            style=discord.ButtonStyle.primary,
            disabled=False,
            row=0,
        )
        compound_btn.callback = self.compound_tab
        self.add_item(compound_btn)

    def format_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Refinery",
            description="Refine compounds using rarities.",
            color=discord.Color.red(),
        )
        for recipe_id in REFINERY_TABS[self.tab]["recipes"][self.curr_item]:
            recipe_data = REFINERY_RECIPES[recipe_id]
            recipe_inputs = []
            for item_id, amount in recipe_data["input"]:
                recipe_inputs.append(f"{amount}x {item_id}")
            recipe_outputs = []
            for item_id, amount in recipe_data["output"]:
                recipe_outputs.append(f"{amount}x {item_id}")
            recipe_time = f"{str(recipe_data['base_time'])}s"  # temporary
            recipe_full_text = [
                "**Inputs:**",
                "\n\n".join(recipe_inputs),
                "**Outputs:**",
                "\n\n".join(recipe_outputs),
                recipe_time,
                f"Tier {recipe_data['tier']}",
            ]
            embed.add_field(
                name=f"**{recipe_data['name']}**",
                value="\n\n".join(recipe_full_text),
                inline=False,
            )

    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True

    async def ref_fuel_tab(self, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        self.tab = 0
        self.page = 0
        self.curr_item = "diesel"
        self.rebuild_components()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    async def autoroll_fuel_tab(self, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        self.tab = 1
        self.page = 0
        self.curr_item = "cfuel_mk1"
        self.rebuild_components()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    async def compound_tab(self, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        self.tab = 2
        self.page = 0
        self.curr_item = "cast_iron"
        self.rebuild_components()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)


class RefineryCommand(
    commands.GroupCog, group_name="refinery", group_description="Refine Items and Compounds"
):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="view", description="View recipes")
    async def view(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user = await get_user_data(user_id)
        inventory = (user or {}).get("inventory") or {}

        view = RefineryView(
            user_id,
            inventory,
            bot=self.bot,
        )
        embed = view.format_embed()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(RefineryCommand(bot))
