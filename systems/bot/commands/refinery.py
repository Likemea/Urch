import discord
from discord import app_commands
from discord.ext import commands


async def setup(bot):
    await bot.add_cog(RefineryCommand(bot))
