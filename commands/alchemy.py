# Urch/commands/alchemy.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import List

from utils import (
    ensure_user,
    has_requirements,
    consume_requirements,
    currency_count,
    RARITY_ID_TO_NAME,
)
from recipes import POTION_RECIPES
from buffs import apply_potion_craft


class RecipesCommand(
    commands.GroupCog, group_name="recipes", group_description="Potion and alchemy commands"
):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="view", description="Displays all recipes")
    async def view(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user = await ensure_user(user_id)

        embed = discord.Embed(
            title="🧪 Alchemy Recipes",
            description="Craft potions using rarities to boost your stats!",
            color=discord.Color.purple(),
        )

        for p_id, recipe in POTION_RECIPES.items():
            req_lines = []
            for item_key, amount in recipe.get("reqs", {}).items():
                user_has = await currency_count(user_id, item_key, user_obj=user)
                display_name = RARITY_ID_TO_NAME.get(item_key, item_key.capitalize())
                status = "✅" if user_has >= amount else "❌"
                req_lines.append(f"• {status} **{display_name}**: {user_has:,}/{amount:,}")

            req_text = "\n".join(req_lines) if req_lines else "None"
            desc_text = recipe.get("description", "No description provided.")

            field_value = (
                f"**Effect:** {desc_text}\n**Requirements:**\n{req_text}\n**ID:** `{p_id}`"
            )
            embed.add_field(name=recipe.get("name", p_id), value=field_value, inline=False)

        embed.set_footer(text="Use /recipes craft <recipe_id> to brew a potion.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="craft", description="Craft a potion from recipes")
    @app_commands.describe(
        recipe_id="The recipe ID of the potion to craft",
        amount="The amount of potions to craft (default: 1)",
    )
    async def craft(
        self,
        interaction: discord.Interaction,
        recipe_id: str,
        amount: app_commands.Range[int, 1, 1000] = 1,
    ):
        recipe = POTION_RECIPES.get(recipe_id)
        if not recipe:
            await interaction.response.send_message(
                f"❌ Recipe `{recipe_id}` does not exist.", ephemeral=True
            )
            return

        if amount < 1:
            await interaction.response.send_message("❌ Amount must be at least 1.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        scaled_reqs = {k: v * amount for k, v in recipe["reqs"].items()}

        ok, missing = await has_requirements(user_id, scaled_reqs)
        if not ok:
            missing_items = []
            for k, amt in missing.items():
                name = RARITY_ID_TO_NAME.get(k, k.capitalize())
                missing_items.append(f"{amt:,}x {name}")
            await interaction.response.send_message(
                f"❌ You are missing ingredients for **{recipe['name']}** (x{amount:,}):\n"
                + "\n".join(f"• {m}" for m in missing_items),
                ephemeral=True,
            )
            return

        consumed = await consume_requirements(user_id, scaled_reqs)
        if not consumed:
            await interaction.response.send_message(
                "❌ Failed to consume ingredients. Please try again.", ephemeral=True
            )
            return

        await apply_potion_craft(user_id, recipe_id, amount=amount)

        desc_prefix = f"You successfully brewed **{amount:,}x {recipe['name']}**!\n\n*{recipe['description']}*"
        embed = discord.Embed(
            title="✨ Potion Brewed!" if amount == 1 else "✨ Potions Brewed!",
            description=desc_prefix,
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    @craft.autocomplete("recipe_id")
    async def craft_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        choices = []
        for p_id, recipe in POTION_RECIPES.items():
            name = recipe.get("name", p_id)
            if current.lower() in p_id.lower() or current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=p_id))
        return choices[:25]


async def setup(bot):
    await bot.add_cog(RecipesCommand(bot))
