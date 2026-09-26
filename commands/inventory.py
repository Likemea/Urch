# Urch/commands/inventory.py
import discord
from discord import app_commands
from discord.ext import commands

from utils import get_user_data, inventory_all_items_sorted
from raritylist import RARITIES
from buffs import get_user_potion_summary


class InventoryView(discord.ui.View):
    def __init__(self, user_id: str, items: list[tuple[str, int]], potion_summary: list[str] = None):
        super().__init__(timeout=120)
        self.user_id = str(user_id)
        self.items = items
        self.potion_summary = potion_summary or []
        self.page = 0
        self.items_per_page = 10
        self.update_buttons()

    def format_page(self):
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.items[start:end]

        embed = discord.Embed(
            title=f"🎒 Inventory (Page {self.page+1}/{self.total_pages})",
            color=discord.Color.blurple()
        )
        if page_items:
            lines = [
                f"{rarity} (x{count})" if count > 1 else rarity
                for rarity, count in page_items
            ]
            embed.description = "\n".join(lines)
        else:
            embed.description = "Empty"

        total_items = sum(count for _, count in self.items)
        footer_parts = [f"Total items: {total_items}"]
        if self.potion_summary:
            footer_parts.append(f"Potions: {', '.join(self.potion_summary)}")
        embed.set_footer(text=" • ".join(footer_parts))
        return embed

    @property
    def total_pages(self):
        return (len(self.items) + self.items_per_page - 1) // self.items_per_page or 1

    def update_buttons(self):
        labels = {getattr(c, "label", ""): c for c in self.children}
        prev_btn = labels.get("⬅️ Prev")
        next_btn = labels.get("➡️ Next")
        if prev_btn:
            prev_btn.disabled = self.total_pages <= 1
        if next_btn:
            next_btn.disabled = self.total_pages <= 1

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This inventory isn’t yours.", ephemeral=True)
        self.page = (self.page - 1) % self.total_pages
        self.update_buttons()
        await interaction.response.edit_message(embed=self.format_page(), view=self)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This inventory isn’t yours.", ephemeral=True)
        self.page = (self.page + 1) % self.total_pages
        self.update_buttons()
        await interaction.response.edit_message(embed=self.format_page(), view=self)


class InventoryCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user = await get_user_data(user_id)
        items = await inventory_all_items_sorted(user_id, RARITIES)
        potion_summary = await get_user_potion_summary(user_id, user_obj=user)
        if not items and not potion_summary:
            await interaction.response.send_message("🎒 Your inventory is empty.", ephemeral=True)
            return

        view = InventoryView(user_id, items, potion_summary=potion_summary)
        embed = view.format_page()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)


async def setup(bot):
    await bot.add_cog(InventoryCommand(bot))