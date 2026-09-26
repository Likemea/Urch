# Urch/commands/upgrades.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import List

from utils import save_user_data, ensure_user, has_requirements, consume_requirements, get_item_count, get_upgrade_effect, RARITY_ID_TO_NAME, format_number
from upgrades import UPGRADE_CATEGORIES

class UpgradeView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=180)
        self.user_id = str(user_id)
        self.category = "luck"   # default category
        self.page = 0            # index of current upgrade within category
        self.update_buttons()

    # category switchers
    @discord.ui.button(label="🍀", style=discord.ButtonStyle.primary, row=0)
    async def show_luck(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn’t your menu.", ephemeral=True)
        self.category = "luck"
        self.page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=await self.format_page(), view=self)

    @discord.ui.button(label="🎰", style=discord.ButtonStyle.primary, row=0)
    async def show_roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn’t your menu.", ephemeral=True)
        self.category = "roll"
        self.page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=await self.format_page(), view=self)
        
    @discord.ui.button(label="☘", style=discord.ButtonStyle.primary, row=0)
    async def show_clovers(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn’t your menu.", ephemeral=True)
    
        user = await ensure_user(self.user_id)
        base_luck = user.get('luck_multi', 1.0) # Safe get

        bonuses = await get_upgrade_effect(self.user_id, user_obj=user)
        luck = base_luck + bonuses["luck_bonus"]
        luck *= bonuses["exp_bonus"]
        if luck < 1000:
            return await interaction.response.send_message("☘ You need 1000 Luck to access this", ephemeral=True)
    
        self.category = "clover"
        self.page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=await self.format_page(), view=self)

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary, row=1)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn’t your menu.", ephemeral=True)
        
        category_dict = UPGRADE_CATEGORIES.get(self.category, {})
        num_upgrades = len(category_dict)
        if num_upgrades > 0:
            self.page = (self.page - 1) % num_upgrades
            self.update_buttons()
            await interaction.response.edit_message(embed=await self.format_page(), view=self)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary, row=1)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn’t your menu.", ephemeral=True)
        
        category_dict = UPGRADE_CATEGORIES.get(self.category, {})
        num_upgrades = len(category_dict)
        if num_upgrades > 0:
            self.page = (self.page + 1) % num_upgrades
            self.update_buttons()
            await interaction.response.edit_message(embed=await self.format_page(), view=self)

    # upgrade purchase button
    @discord.ui.button(label="⬆️ Upgrade", style=discord.ButtonStyle.success, row=2)
    async def upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn’t your menu.", ephemeral=True)

        category_dict = UPGRADE_CATEGORIES.get(self.category, {})
        keys = list(category_dict.keys())
        if not keys:
            return await interaction.response.send_message("No upgrades in this category.", ephemeral=True)

        key = keys[self.page]
        upgrade_def = category_dict[key]

        user = await ensure_user(self.user_id)
        user_upgrades = user.setdefault("upgrades", {})
        cat_upgs = user_upgrades.setdefault(self.category, {})
        current_tier = int(cat_upgs.get(key, 0))

        next_tier = current_tier + 1
        reqs = upgrade_def.get("requirements", {}).get(next_tier)
        if not reqs:
            return await interaction.response.send_message("✅ Upgrade is already maxed.", ephemeral=True)

        ok, missing = await has_requirements(self.user_id, reqs, user_obj=user)
        if not ok:
            lines = [f"{rar} ({need} more needed)" for rar, need in missing.items()]
            return await interaction.response.send_message(
                "❌ You don't have enough items:\n" + "\n".join(lines),
                ephemeral=True
            )

        success = await consume_requirements(self.user_id, reqs)
        if not success:
            return await interaction.response.send_message("Unexpected error consuming items.", ephemeral=True)

        cat_upgs[key] = next_tier
        await save_user_data(self.user_id, user)

        await interaction.response.edit_message(embed=await self.format_page(), view=self)
        
    @discord.ui.button(label="💰 Buy Max", style=discord.ButtonStyle.success, row=2)
    async def buy_max(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn't your menu.", ephemeral=True)
    
        category_dict = UPGRADE_CATEGORIES.get(self.category, {})
        keys = list(category_dict.keys())
        if not keys:
            return await interaction.response.send_message("No upgrades in this category.", ephemeral=True)
    
        key = keys[self.page]
        upgrade_def = category_dict[key]
    
        user = await ensure_user(self.user_id)
        user_upgrades = user.setdefault("upgrades", {})
        cat_upgs = user_upgrades.setdefault(self.category, {})
        current_tier = int(cat_upgs.get(key, 0))
        
        max_tier = upgrade_def.get("max_tier", current_tier + 100)
        tiers_bought = 0
        total_cost = {}
    
        max_tiers_to_check = 25
        tiers_checked = 0
        
        for next_tier in range(current_tier + 1, max_tier + 1):
            if tiers_checked >= max_tiers_to_check:
                break
            tiers_checked += 1
                
            reqs = upgrade_def.get("requirements", {}).get(next_tier)
            if not reqs:
                break
            
            # check if we can afford cumulative cost + this tier
            # we need a temp cost dict to check against
            temp_reqs = total_cost.copy()
            for item, amount in reqs.items():
                temp_reqs[item] = temp_reqs.get(item, 0) + amount
            
            ok, missing = await has_requirements(self.user_id, temp_reqs, user_obj=user)
            if not ok:
                break
                
            # if affordable, commit to total cost
            total_cost = temp_reqs
            tiers_bought += 1
    
        if tiers_bought == 0:
            return await interaction.response.send_message(
                "❌ Cannot afford any more", 
                ephemeral=True
            )
    
        success = await consume_requirements(self.user_id, total_cost)
        if not success:
            return await interaction.response.send_message(
                "unexpected error", 
                ephemeral=True
            )
    
        cat_upgs[key] = current_tier + tiers_bought
        await save_user_data(self.user_id, user)
    
        await interaction.response.edit_message(embed=await self.format_page(), view=self)

    async def format_page(self) -> discord.Embed:
        category_dict = UPGRADE_CATEGORIES.get(self.category, {})
        keys = list(category_dict.keys())
        if not keys:
            return discord.Embed(title="No upgrades", description="No upgrades defined for this category.")
        
        self.page = max(0, min(self.page, len(keys)-1))
        key = keys[self.page]
        upgrade_def = category_dict[key]
        
        user = await ensure_user(self.user_id)
        luck_override = user.get('luck_override')
        upgrades = user.get("upgrades", {}).get(self.category, {})
        current_tier = int(upgrades.get(key, 0))
        next_tier = current_tier + 1
        reqs = upgrade_def.get("requirements", {}).get(next_tier)
        
        if self.category == "luck":
            color = discord.Color.green()
        elif self.category == "roll":
            color = discord.Color.blurple()
        elif self.category == "clover":
            color = discord.Color.gold()
        else:
            color = discord.Color.blue()
        
        embed = discord.Embed(
            title=f"{upgrade_def.get('name', key)}",
            color=color
        )
        
        if self.category == "luck":
            if luck_override is not None:
                total_luck = luck_override
                luck_status = "🎯 OVERRIDE"
            else:
                base_luck = user.get("luck_multi", 1.0)
                bonuses = await get_upgrade_effect(self.user_id, user_obj=user)
                total_luck = (base_luck + bonuses.get("luck_bonus", 0.0)) * bonuses.get("exp_bonus", 1.0)
                luck_status = "🍀 Your Luck"
                
            total_luck = float(total_luck or 0.0)
            
            embed.add_field(name="🍀 You have", value=f"**{format_number(total_luck)}**\nLuck", inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            embed.add_field(name="Tier", value=str(current_tier), inline=True)
        elif self.category == "clover":
            user = await ensure_user(self.user_id)
            clover_count = user.get("currencies", {}).get("clovers", 0)
            embed.add_field(name="☘ You have", value=f"**{clover_count}**\nClovers", inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True) 
            embed.add_field(name="Tier", value=str(current_tier), inline=True)
        else:
            embed.add_field(name="Tier", value=str(current_tier), inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        embed.add_field(name="Description", value=upgrade_def.get("description", "No description."), inline=False)
        
        if reqs:
            lines = []
            for item, need in reqs.items():
                have = await get_item_count(self.user_id, item, user_obj=user)
                mark = "✅" if have >= need else "❌"
                display_name = RARITY_ID_TO_NAME.get(item, item.capitalize())
                lines.append(f"{mark} {display_name}: {have}/{need}")
            embed.add_field(name="Next Tier Cost", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Next Tier Cost", value="Maxed Out!", inline=False)
        
        embed.set_footer(text=f"Category: {self.category} • Upgrade {self.page+1}/{len(keys)}")
        return embed

    def update_buttons(self):
        labels = {getattr(c, "label", ""): c for c in self.children}
        prev_btn = labels.get("⬅️ Prev")
        next_btn = labels.get("➡️ Next")
        
        category_dict = UPGRADE_CATEGORIES.get(self.category, {})
        num_upgrades = len(category_dict)
        
        if prev_btn:
            prev_btn.disabled = num_upgrades <= 1
        if next_btn:
            next_btn.disabled = num_upgrades <= 1
        
        if num_upgrades > 0:
            self.page = self.page % num_upgrades
        else:
            self.page = 0

class UpgradesCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="upgrades", description="View and buy upgrades")
    async def upgrades(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        await ensure_user(user_id)
        view = UpgradeView(user_id)
        embed = await view.format_page()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(UpgradesCommand(bot))