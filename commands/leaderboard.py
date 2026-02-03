# Urch/commands/leaderboard.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import List

from utils import get_upgrade_effect # We still need this for the math
from database import db
from raritylist import RARITIES

class LeaderboardView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=180)
        self.bot = bot
        self.category = "luck"  # default category
        self.page = 0  # current page (0-indexed)
        self.entries_per_page = 10
        self.update_buttons_sync()

    def update_buttons_sync(self):
        """Updates just the visual style of category buttons."""
        for child in self.children:
            if hasattr(child, 'label') and child.label:
                if "Most Luck" in child.label:
                    child.style = discord.ButtonStyle.success if self.category == "luck" else discord.ButtonStyle.primary
                elif "Most Rolls" in child.label:
                    child.style = discord.ButtonStyle.success if self.category == "rolls" else discord.ButtonStyle.primary
                elif "Best Rarity" in child.label:
                    child.style = discord.ButtonStyle.success if self.category == "rarity" else discord.ButtonStyle.primary

    async def update_buttons_async(self):
        """Updates enabled/disabled state of pagination buttons."""
        max_pages = await self.get_max_pages()
        for child in self.children:
            if getattr(child, "label", "") == "◀":
                child.disabled = (self.page == 0)
            elif getattr(child, "label", "") == "▶":
                child.disabled = (self.page >= max_pages - 1)
        self.update_buttons_sync()

    # Category switchers
    @discord.ui.button(label="🍀 Most Luck", style=discord.ButtonStyle.primary, row=0)
    async def show_luck(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.category = "luck"
        self.page = 0
        await self.update_buttons_async()
        await interaction.response.edit_message(embed=await self.format_page(), view=self)

    @discord.ui.button(label="🎰 Most Rolls", style=discord.ButtonStyle.primary, row=0)
    async def show_rolls(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.category = "rolls"
        self.page = 0
        await self.update_buttons_async()
        await interaction.response.edit_message(embed=await self.format_page(), view=self)

    @discord.ui.button(label="💎 Best Rarity", style=discord.ButtonStyle.primary, row=0)
    async def show_rarity(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.category = "rarity"
        self.page = 0
        await self.update_buttons_async()
        await interaction.response.edit_message(embed=await self.format_page(), view=self)

    # Pagination buttons
    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, row=1)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await self.update_buttons_async()
            await interaction.response.edit_message(embed=await self.format_page(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        max_pages = await self.get_max_pages()
        if self.page < max_pages - 1:
            self.page += 1
            await self.update_buttons_async()
            await interaction.response.edit_message(embed=await self.format_page(), view=self)

    async def get_leaderboard_data(self) -> List[tuple]:
        """
        OPTIMIZED: Fetches all data in 3 bulk queries instead of N+1 queries.
        Returns sorted list of (user_id, value).
        """
        leaderboard_data = []
        rarity_map = {name: i for i, (name, _, _) in enumerate(RARITIES)}
        
        # 1. Bulk Fetch: User Stats (Rolls, Luck, Highscore)
        await db._check_conn()
        async with db.conn.execute("SELECT user_id, roll_count, highscore, luck_multi, max_luck FROM users") as cursor:
            users_rows = await cursor.fetchall()
            # Map: user_id -> {roll_count, highscore, luck_multi, max_luck}
            users_map = {r[0]: {'roll_count': r[1], 'highscore': r[2], 'luck_multi': r[3], 'max_luck': r[4]} for r in users_rows}
            
        # 2. Bulk Fetch: Upgrades
        async with db.conn.execute("SELECT user_id, category, upgrade_key, tier FROM user_upgrades") as cursor:
            upgrades_rows = await cursor.fetchall()
            # Map: user_id -> {category: {key: tier}}
            upgrades_map = {}
            for uid, cat, key, tier in upgrades_rows:
                if uid not in upgrades_map:
                    upgrades_map[uid] = {'luck': {}, 'roll': {}, 'clover': {}}
                upgrades_map[uid][cat][key] = tier
        
        # 3. Bulk Fetch: Discovered Items (Inventory)
        # We only fetch discovered items to calculate the checklist bonus efficiently
        async with db.conn.execute("SELECT user_id, item_name FROM user_inventory WHERE discovered = 1") as cursor:
            inv_rows = await cursor.fetchall()
            # Map: user_id -> {item_name: True} (Mimicking the 'discovered' dict structure)
            discovered_map = {}
            for uid, item in inv_rows:
                if uid not in discovered_map:
                    discovered_map[uid] = {}
                discovered_map[uid][item] = True

        # Process data in memory (Very fast)
        for user_id, data in users_map.items():
            val = 0
            
            if self.category == "luck":
                # Construct a lightweight user_obj for the helper function
                user_obj = {
                    "upgrades": upgrades_map.get(user_id, {}),
                    "discovered": discovered_map.get(user_id, {}),
                    "luck_multi": data['luck_multi'],
                    "max_luck": data['max_luck']
                }
                
                # Calculate total luck using the existing utility
                bonuses = await get_upgrade_effect(user_id, user_obj=user_obj)
                base = data['luck_multi']
                total_luck = (base + bonuses["luck_bonus"]) * bonuses["exp_bonus"]
                val = total_luck
                
            elif self.category == "rolls":
                val = data['roll_count']
                
            elif self.category == "rarity":
                highscore = data['highscore']
                val = rarity_map.get(highscore, -1)
            
            leaderboard_data.append((user_id, val))
        
        leaderboard_data.sort(key=lambda x: x[1], reverse=True)
        return leaderboard_data

    async def get_max_pages(self) -> int:
        data = await self.get_leaderboard_data()
        return max(1, (len(data) + self.entries_per_page - 1) // self.entries_per_page)

    async def format_page(self) -> discord.Embed:
        data = await self.get_leaderboard_data()
        max_pages = await self.get_max_pages()
        
        start_idx = self.page * self.entries_per_page
        end_idx = min(start_idx + self.entries_per_page, len(data))
        
        if self.category == "luck":
            color, title, value_name = discord.Color.green(), "🏆 Luck Leaderboard", "🍀"
        elif self.category == "rolls":
            color, title, value_name = discord.Color.blue(), "🏆 Rolls Leaderboard", "🎰"
        else:
            color, title, value_name = discord.Color.purple(), "🏆 Rarity Leaderboard", "💎"
        
        embed = discord.Embed(title=title, color=color)
        
        if not data:
            embed.description = "No data available yet. Start rolling with `/roll`!"
        else:
            leaderboard_text = ""
            for i in range(start_idx, end_idx):
                user_id, value = data[i]
                rank = i + 1
                
                try:
                    user = self.bot.get_user(int(user_id))
                    display_name = user.display_name if user else f"<@{user_id}>"
                except:
                    display_name = f"<@{user_id}>"
                
                if self.category == "luck":
                    formatted_value = f"{value:.2f}"
                elif self.category == "rolls":
                    formatted_value = f"{int(value):,}"
                else:
                    formatted_value = RARITIES[int(value)][0] if value != -1 else "None"
                
                medal = "🥇 " if rank == 1 else "🥈 " if rank == 2 else "🥉 " if rank == 3 else f"#{rank} "
                leaderboard_text += f"\n**{medal}{display_name}** - {value_name} **{formatted_value}**\n"
            
            embed.description = leaderboard_text
        
        embed.set_footer(text=f"Page {self.page + 1}/{max_pages} • {len(data)} total players")
        return embed

class LeaderboardCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="View the top players")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer() # Good practice for DB heavy commands
        view = LeaderboardView(self.bot)
        await view.update_buttons_async() 
        embed = await view.format_page()
        await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(LeaderboardCommand(bot))