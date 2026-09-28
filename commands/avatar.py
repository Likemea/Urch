# Urch/commands/avatar.py
import discord
from discord import app_commands
from discord.ext import commands


class AvatarCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="avatar", description="Get someone's avatar")
    @app_commands.describe(user="The user whose avatar you want")
    async def avatar(self, interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user

        avatar_url = target.display_avatar.url

        embed = discord.Embed(title=f"🖼️ {target.display_name}'s Avatar", color=discord.Color.teal())
        embed.set_image(url=avatar_url)

        view = discord.ui.View()
        button = discord.ui.Button(
            label="Download", url=target.display_avatar.url, style=discord.ButtonStyle.link
        )
        view.add_item(button)

        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(AvatarCommand(bot))
