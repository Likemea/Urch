# Urch/commands/checklist.py
import discord
from discord import app_commands
from discord.ext import commands
from math import ceil

from utils import ensure_user, get_checklist_bonus
from raritylist import RARITIES

ITEMS_PER_PAGE = 20

class ChecklistView(discord.ui.View):
    def __init__(self, user_id: str, discovered: dict):
        super().__init__(timeout=180)
        self.user_id = str(user_id)
        self.rarity_names = [r[0] for r in RARITIES]
        self.discovered = discovered
        self.page = 0
        self.total = len(self.rarity_names)

    def format_page_embed(self) -> discord.Embed:
        start = self.page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        names = self.rarity_names[start:end]

        embed = discord.Embed(title="📋 Checklist", color=discord.Color.blurple())
        lines = []
        for name in names:
            had = self.discovered.get(name, False)
            mark = "✅" if had else "❌"
            lines.append(f"{mark} {name}")
        embed.description = "\n".join(lines) if lines else "No rarities defined."
        
        # We can calculate checklist bonus roughly here or need to pass it in.
        # Ideally, calculate from self.discovered count to be sync
        count = sum(1 for v in self.discovered.values() if v)
        bonus_mult = 1.0 + (0.03 * count) # Hardcoded constant from utils to avoid async import
        
        embed.set_footer(text=f"Discovered: {count}/{self.total} • Bonus: x{bonus_mult:.3f} 🍀")
        return embed

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This checklist isn't yours.", ephemeral=True)
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.format_page_embed(), view=self)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This checklist isn't yours.", ephemeral=True)
        max_page = max(0, ceil(self.total / ITEMS_PER_PAGE) - 1)
        if self.page < max_page:
            self.page += 1
            await interaction.response.edit_message(embed=self.format_page_embed(), view=self)

class ChecklistCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="checklist", description="View how many rarities you've discovered so far")
    async def checklist(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        # Fetch data asynchronously HERE
        user = await ensure_user(uid)
        discovered = user.get("discovered", {})
        
        # Pass data synchronously to View
        view = ChecklistView(uid, discovered)
        embed = view.format_page_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ChecklistCommand(bot))