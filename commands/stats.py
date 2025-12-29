# Urch/commands/stats.py
import discord
from discord import app_commands
from discord.ext import commands
import datetime
import time

class StatsCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()

    @app_commands.command(name="stats", description="View bot statistics")
    async def stats(self, interaction: discord.Interaction):
        # Calculate Uptime
        current_time = time.time()
        difference = int(current_time - self.start_time)
        uptime_str = str(datetime.timedelta(seconds=difference))
        
        # Server Count (Guilds)
        guild_count = len(self.bot.guilds)
        
        # User Count (Approximate - sum of members in all guilds)
        # Note: This might be inaccurate in Sharded bots, but fine here.
        user_count = sum(g.member_count for g in self.bot.guilds)

        embed = discord.Embed(title="Bot Statistics", color=discord.Color.gold())
        
        embed.add_field(name="Uptime", value=f"`{uptime_str}`", inline=True)
        embed.add_field(name="Servers", value=f"`{guild_count}`", inline=True)
        embed.add_field(name="Total Users", value=f"`{user_count:,}`", inline=True)
        embed.add_field(name="Latency", value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(StatsCommand(bot))