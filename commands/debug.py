# Urch/commands/debug.py
import discord
from discord import app_commands
from discord.ext import commands
from utils import ensure_user, save_user_data, LUCK_GROWTH_PER_ROLL, get_checklist_bonus, get_upgrade_effect

class DebugCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="debug", description="Recalculate and fix your luck")
    async def debug(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user = await ensure_user(user_id)
        
        original_luck_multi = user.get("luck_multi", 1.0)
        original_max_luck = user.get("max_luck", 1.0)
        roll_count = user.get("roll_count", 0)
        luck_override = user.get('luck_override')
        
        expected_base_luck = 1.0 + (roll_count * LUCK_GROWTH_PER_ROLL)
        
        bonuses = await get_upgrade_effect(user_id, user_obj=user)
        
        expected_total_luck = (expected_base_luck + bonuses["luck_bonus"]) * bonuses["exp_bonus"]
        
        fixes_applied = []
        
        if abs(user["luck_multi"] - expected_base_luck) > 0.01:
            old_luck = user["luck_multi"]
            user["luck_multi"] = round(expected_base_luck, 3)
            fixes_applied.append(f"Base luck: {old_luck:.2f} → {user['luck_multi']:.2f}")
        
        if user["max_luck"] < user["luck_multi"]:
            old_max = user["max_luck"]
            user["max_luck"] = user["luck_multi"]
            fixes_applied.append(f"Max luck: {old_max:.2f} → {user['max_luck']:.2f}")
        
        if fixes_applied:
            await save_user_data(user_id, user)
        
        embed = discord.Embed(
            title="🔧 Debug Information",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Roll Stats",
            value=f"**Roll Count:** {roll_count}\n"
                  f"**Expected Base Luck:** {expected_base_luck:.2f}\n"
                  f"**Current Base Luck:** {user['luck_multi']:.2f}",
            inline=False
        )
        
        embed.add_field(
            name="Upgrade Effects",
            value=f"**Additive Bonus:** +{bonuses['luck_bonus']:.2f}\n"
                  f"**Multiplicative Bonus:** ×{bonuses['exp_bonus']:.2f}\n"
                  f"**Extra Rolls:** +{bonuses['multi_roll']}",
            inline=False
        )
        
        embed.add_field(
            name="Luck Calculation",
            value=f"**Base:** {user['luck_multi']:.2f}\n"
                  f"**+ Additive:** {user['luck_multi'] + bonuses['luck_bonus']:.2f}\n"
                  f"**× Multiplicative:** {expected_total_luck:.2f}",
            inline=False
        )
        
        if luck_override is not None:
            effective_luck = user['luck_override']
            embed.add_field(
                name="🎯 Override Active",
                value=f"**Effective Luck:** {effective_luck:.2f}\n"
                      f"(Base calculation ignored due to override)",
                inline=False
            )
        else:
            effective_luck = expected_total_luck
            embed.add_field(
                name="🎲 Effective Luck",
                value=f"**{effective_luck:.2f}**\n"
                      f"(Base + Additive) × Multiplicative",
                inline=False
            )
        
        if fixes_applied:
            embed.add_field(
                name="✅ Fixes Applied",
                value="\n".join(fixes_applied),
                inline=False
            )
            embed.color = discord.Color.green()
        else:
            embed.add_field(
                name="✅ No Issues Found",
                value="Your luck stats appear to be correct!",
                inline=False
            )
            embed.color = discord.Color.blue()
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(DebugCommand(bot))