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


async def _send_response(interaction: discord.Interaction, *args, **kwargs):
    try:
        return await interaction.followup.send(*args, **kwargs)
    except TypeError:
        return await interaction.response.send_message(*args, **kwargs)


class RecipesCommand(
    commands.GroupCog, group_name="recipes", group_description="Potion and alchemy commands"
):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="view", description="Displays all recipes")
    async def view(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except TypeError:
            pass
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
        try:
            await interaction.followup.send(embed=embed)
        except TypeError:
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
        try:
            await interaction.response.defer(ephemeral=True)
        except TypeError:
            pass

        recipe = POTION_RECIPES.get(recipe_id)
        if not recipe:
            await _send_response(
                interaction, f"❌ Recipe `{recipe_id}` does not exist.", ephemeral=True
            )
            return

        if amount < 1:
            await _send_response(interaction, "❌ Amount must be at least 1.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        from database import db
        import time

        buff = recipe["buff"]
        now = int(time.time())

        async with db.lock_user(user_id):
            if buff["type"] == "duration":
                key = f"potion_exp_{recipe_id}"
                stored_exp = await currency_count(user_id, key)
                current_active = max(0, stored_exp - now) if stored_exp > now else 0
                dur_per_potion = buff["duration_seconds"]
                max_craftable = max(0, (86400 - current_active) // dur_per_potion)
                if amount > max_craftable:
                    await _send_response(
                        interaction,
                        f"❌ Crafting {amount}x **{recipe['name']}** exceeds the 24-hour active duration cap.\n"
                        f"You currently have {current_active // 60}m active and can craft at most **{max_craftable}** more.",
                        ephemeral=True,
                    )
                    return
            elif buff["type"] == "charges":
                key = f"potion_charge_{recipe_id}"
                stored_charges = await currency_count(user_id, key)
                charges_per_potion = buff["charges"]
                max_craftable = max(0, (1000 - stored_charges) // charges_per_potion)
                if amount > max_craftable:
                    await _send_response(
                        interaction,
                        f"❌ Crafting {amount}x **{recipe['name']}** exceeds the 1,000 charge limit.\n"
                        f"You currently have {stored_charges:,} charges and can craft at most **{max_craftable}** more.",
                        ephemeral=True,
                    )
                    return

            scaled_reqs = {k: v * amount for k, v in recipe["reqs"].items()}

            ok, missing = await has_requirements(user_id, scaled_reqs)
            if not ok:
                missing_items = []
                for k, amt in missing.items():
                    name = RARITY_ID_TO_NAME.get(k, k.capitalize())
                    missing_items.append(f"{amt:,}x {name}")
                await _send_response(
                    interaction,
                    f"❌ You are missing ingredients for **{recipe['name']}** (x{amount:,}):\n"
                    + "\n".join(f"• {m}" for m in missing_items),
                    ephemeral=True,
                )
                return

            consumed = await consume_requirements(user_id, scaled_reqs)
            if not consumed:
                await _send_response(
                    interaction,
                    "❌ Failed to consume ingredients. Please try again.",
                    ephemeral=True,
                )
                return

            await apply_potion_craft(user_id, recipe_id, amount=amount)

        desc_prefix = f"You successfully brewed **{amount:,}x {recipe['name']}**!\n\n*{recipe['description']}*"
        embed = discord.Embed(
            title="✨ Potion Brewed!" if amount == 1 else "✨ Potions Brewed!",
            description=desc_prefix,
            color=discord.Color.green(),
        )
        await _send_response(interaction, embed=embed)

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
