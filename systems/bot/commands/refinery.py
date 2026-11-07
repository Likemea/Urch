import discord
from discord import app_commands
from discord.ext import commands


class RefineryCommand(commands.Cog,group_name="refinery",group_description="Refine Items and Compounds"):
    def __init__(self, bot):
    self.bot = bot
    super().__init__()


async def setup(bot):
    await bot.add_cog(RefineryCommand(bot))
