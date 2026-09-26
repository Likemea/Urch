# Urch/commands/roll.py
import discord
from discord import app_commands
from discord.ext import commands
from collections import Counter
import math

from utils import roll_rarities, update_user_data, ensure_user, get_upgrade_effect, log_rare_roll, format_number
from raritylist import RARITIES
from buffs import evaluate_active_buffs

RARITY_ORDER = [r[0] for r in RARITIES]
RARITY_WEIGHT_MAP = {r[0]: r[1] for r in RARITIES}
TOTAL_RARITY_WEIGHT = sum(r[1] for r in RARITIES)

class ButtonView(discord.ui.View):
    def __init__(self, user_id, rarity, bot):
        super().__init__()
        self.user_id = str(user_id)
        self.rarity = rarity
        self.bot = bot

    @discord.ui.button(label="Reroll", style=discord.ButtonStyle.primary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if str(interaction.user.id) != self.user_id:
            await interaction.followup.send(
                f"This roll belongs to <@{self.user_id}>. To roll, say ``/roll``",
                ephemeral=True
            )
            return

        user = await ensure_user(self.user_id)
        bonuses = await get_upgrade_effect(self.user_id, user_obj=user)
        
        luck_override = user.get('luck_override')
        if luck_override is not None:
            luck = float(luck_override)
        else:
            base_luck = user.get('luck_multi', 1.0)
            luck = (base_luck + bonuses.get("luck_bonus", 0.0)) * bonuses.get("exp_bonus", 1.0)
        
        buff_data = await evaluate_active_buffs(self.user_id, context="manual")
        luck *= buff_data["luck_mult"]
        luck = max(1.0, float(luck or 0.0))

        extra_rolls = bonuses.get("multi_roll", 0) + buff_data["extra_rolls"]
        total_rolls = 1 + extra_rolls

        all_rolls = await roll_rarities(self.user_id, count=total_rolls, provided_luck=luck)
        updated_user = await update_user_data(self.user_id, all_rolls, action="keep")
        if not updated_user:
            updated_user = user

        for r in all_rolls:
            await check_and_log_rarity(self.bot, interaction.user, r, total_luck=luck)

        counts = Counter(all_rolls)
        sorted_results = sorted(counts.items(), key=lambda x: RARITY_ORDER.index(x[0]) if x[0] in RARITY_ORDER else -1, reverse=True)

        summary = "\n".join(
            f"x{count} {rarity}" if count > 1 else rarity
            for rarity, count in sorted_results
        )
        
        new_roll_count = updated_user.get('roll_count', user.get('roll_count', 0))
        new_highscore = updated_user.get('highscore', user.get('highscore', all_rolls[0] if all_rolls else ""))

        new_embed = discord.Embed(title="🎲 Roll Result 🎲", color=discord.Color.blurple())
        new_embed.description = f"**{summary}**"
        new_embed.add_field(name="Rolls", value=new_roll_count, inline=True)
        new_embed.add_field(name="Best Roll", value=new_highscore, inline=True)
        new_embed.add_field(name="Luck", value=format_number(luck), inline=True)

        if buff_data["active_names"]:
            new_embed.set_footer(text=f"Active Potions: {', '.join(buff_data['active_names'])}")

        self.rarity = all_rolls[0] if all_rolls else self.rarity
        
        await interaction.edit_original_response(embed=new_embed, view=self)

async def check_and_log_rarity(bot, user, rarity_name, total_luck=None):
    try:
        if total_luck is None:
            user_id = str(user.id)
            user_data = await ensure_user(user_id)
            
            if user_data.get('luck_override') is not None:
                 total_luck = float(user_data['luck_override'])
            else:
                 base = user_data.get('luck_multi', 1.0)
                 bonuses = await get_upgrade_effect(user_id, user_obj=user_data)
                 total_luck = (base + bonuses.get("luck_bonus", 0.0)) * bonuses.get("exp_bonus", 1.0)

        total_luck = max(1.0, float(total_luck or 0.0))

        weight = RARITY_WEIGHT_MAP.get(rarity_name)
        if weight is None:
            return
            
        one_in = TOTAL_RARITY_WEIGHT / weight
        
        if one_in >= (total_luck * 100):
            await log_rare_roll(bot, user, rarity_name, one_in, total_luck)
            
    except Exception as e:
        print(f"Error checking rarity log: {e}")

class RollCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="roll", description="Roll for a rarity")
    async def roll(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        user_id = str(interaction.user.id)
        user = await ensure_user(user_id)
        bonuses = await get_upgrade_effect(user_id, user_obj=user)

        luck_override = user.get('luck_override')
        if luck_override is not None:
            luck = float(luck_override)
        else:
            base_luck = user.get('luck_multi', 1.0)
            luck = (base_luck + bonuses.get("luck_bonus", 0.0)) * bonuses.get("exp_bonus", 1.0)
        
        buff_data = await evaluate_active_buffs(user_id, context="manual")
        luck *= buff_data["luck_mult"]
        luck = max(1.0, float(luck or 0.0))
        
        extra_rolls = bonuses.get("multi_roll", 0) + buff_data["extra_rolls"]
        total_rolls = 1 + extra_rolls

        all_rolls = await roll_rarities(user_id, count=total_rolls, provided_luck=luck)
        updated_user = await update_user_data(user_id, all_rolls, action="keep")
        if not updated_user:
            updated_user = user

        for r in all_rolls:
            await check_and_log_rarity(self.bot, interaction.user, r, total_luck=luck)

        counts = Counter(all_rolls)
        sorted_results = sorted(counts.items(), key=lambda x: RARITY_ORDER.index(x[0]) if x[0] in RARITY_ORDER else -1, reverse=True)

        summary = "\n".join(f"x{count} {rarity}" if count > 1 else rarity for rarity, count in sorted_results)
        
        roll_count = updated_user.get('roll_count', user.get('roll_count', 0))
        highscore = updated_user.get("highscore", all_rolls[0] if all_rolls else "")

        embed = discord.Embed(title="🎲 Roll Result 🎲", color=discord.Color.blurple())
        embed.description = f"**{summary}**"
        embed.add_field(name="Rolls", value=roll_count, inline=True)
        embed.add_field(name="Best Roll", value=highscore, inline=True)
        embed.add_field(name="Luck", value=format_number(luck), inline=True)

        if buff_data["active_names"]:
            embed.set_footer(text=f"Active Potions: {', '.join(buff_data['active_names'])}")

        first_rarity = all_rolls[0] if all_rolls else ""
        view = ButtonView(user_id, first_rarity, self.bot)
        await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(RollCommand(bot))