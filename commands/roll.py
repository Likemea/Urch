# Urch/commands/roll.py
import discord
from discord import app_commands
from discord.ext import commands
from collections import Counter
import math

from utils import roll_rarity, update_user_data, ensure_user, get_upgrade_effect, log_rare_roll
from raritylist import RARITIES

class ButtonView(discord.ui.View):
    def __init__(self, user_id, rarity, bot):
        super().__init__()
        self.user_id = str(user_id)
        self.rarity = rarity
        self.bot = bot

    @discord.ui.button(label="Reroll", style=discord.ButtonStyle.primary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                f"This roll belongs to <@{self.user_id}>. To roll, say ``/roll``",
                ephemeral=True
            )
            return

        all_rolls = []
        
        user = await ensure_user(self.user_id)
        luck_override = user.get('luck_override')

        new_rarity = await roll_rarity(self.user_id)
        await update_user_data(self.user_id, new_rarity, action="keep")
        all_rolls.append(new_rarity)
        
        await check_and_log_rarity(self.bot, interaction.user, new_rarity)

        bonuses = await get_upgrade_effect(self.user_id, user_obj=user)
        extra_rolls = bonuses.get("multi_roll", 0)

        if extra_rolls > 0:
            for _ in range(extra_rolls):
                extra_rarity = await roll_rarity(self.user_id)
                await update_user_data(self.user_id, extra_rarity, action="keep")
                all_rolls.append(extra_rarity)
                await check_and_log_rarity(self.bot, interaction.user, extra_rarity)

        rarity_order = [r[0] for r in RARITIES]
        
        counts = Counter(all_rolls)
        sorted_results = sorted(counts.items(), key=lambda x: rarity_order.index(x[0]), reverse=True)

        summary = ", ".join(
            f"x{count} {rarity}" if count > 1 else rarity
            for rarity, count in sorted_results
        )
        
        new_roll_count = user['roll_count']
        new_highscore = user['highscore']

        if luck_override is not None:
            luck = luck_override
        else:
            base_luck = user.get('luck_multi', 1.0)
            luck = (base_luck + bonuses.get("luck_bonus", 0.0)) * bonuses.get("exp_bonus", 1.0)
        
        luck = float(luck or 0.0)

        new_embed = discord.Embed(title="🎲 Roll Result 🎲", color=discord.Color.blurple())
        new_embed.description = f"You rolled: **{summary}**"
        new_embed.add_field(name="Rolls", value=new_roll_count, inline=True)
        new_embed.add_field(name="Best Roll", value=new_highscore, inline=True)
        new_embed.add_field(name="Luck", value=f"{luck:.2f}", inline=True)

        self.rarity = new_rarity
        
        await interaction.response.edit_message(embed=new_embed, view=self)

async def check_and_log_rarity(bot, user, rarity_name):
    try:
        user_id = str(user.id)
        user_data = await ensure_user(user_id)
        
        if user_data.get('luck_override') is not None:
             total_luck = float(user_data['luck_override'])
        else:
             base = user_data.get('luck_multi', 1.0)
             bonuses = await get_upgrade_effect(user_id, user_obj=user_data)
             total_luck = (base + bonuses.get("luck_bonus", 0.0)) * bonuses.get("exp_bonus", 1.0)

        total_luck = max(1.0, total_luck)

        total_weight = sum(r[1] for r in RARITIES)
        
        rarity_data = next((r for r in RARITIES if r[0] == rarity_name), None)
        
        if not rarity_data: return
            
        weight = rarity_data[1]
        one_in = total_weight / weight
        
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
        all_rolls = []        
        user = await ensure_user(user_id)
        
        rarity = await roll_rarity(user_id)
        await update_user_data(user_id, rarity, action="keep")
        all_rolls.append(rarity)
        
        await check_and_log_rarity(self.bot, interaction.user, rarity)

        bonuses = await get_upgrade_effect(user_id, user_obj=user)
        extra_rolls = bonuses.get("multi_roll", 0)

        if extra_rolls > 0:
            for _ in range(extra_rolls):
                extra_rarity = await roll_rarity(user_id)
                await update_user_data(user_id, extra_rarity, action="keep")
                all_rolls.append(extra_rarity)
                await check_and_log_rarity(self.bot, interaction.user, extra_rarity)

        rarity_order = [r[0] for r in RARITIES]
        counts = Counter(all_rolls)
        sorted_results = sorted(counts.items(), key=lambda x: rarity_order.index(x[0]), reverse=True)

        summary = ", ".join(f"x{count} {rarity}" if count > 1 else rarity for rarity, count in sorted_results)
        
        roll_count = user['roll_count'] + len(all_rolls)
        
        luck_override = user.get('luck_override')
        if luck_override is not None:
            luck = float(luck_override)
        else:
            base_luck = user.get('luck_multi', 1.0)
            luck = (base_luck + bonuses.get("luck_bonus", 0.0)) * bonuses.get("exp_bonus", 1.0)
        
        highscore = user.get("highscore", rarity)

        embed = discord.Embed(title="🎲 Roll Result 🎲", color=discord.Color.blurple())
        embed.description = f"You rolled: **{summary}**"
        embed.add_field(name="Rolls", value=roll_count, inline=True)
        embed.add_field(name="Best Roll", value=highscore, inline=True)
        embed.add_field(name="Luck", value=f"{luck:.2f}", inline=True)

        view = ButtonView(user_id, rarity, self.bot)
        await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(RollCommand(bot))