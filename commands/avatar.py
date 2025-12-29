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
        # In Group Chats/DMs, input is discord.User. In servers, it might be Member.
        # We default to interaction.user if no argument is provided.
        target = user or interaction.user
        
        # Get the highest resolution avatar url
        avatar_url = target.display_avatar.url

        embed = discord.Embed(
            title=f"🖼️ {target.display_name}'s Avatar",
            color=discord.Color.teal()
        )
        embed.set_image(url=avatar_url)
        
        # Add a download link button
        view = discord.ui.View()
        button = discord.ui.Button(label="Download", url=target.display_avatar.url, style=discord.ButtonStyle.link)
        view.add_item(button)

        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(AvatarCommand(bot))