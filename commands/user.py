# Urch/commands/user.py
import discord
from discord import app_commands
from discord.ext import commands

class UserInfoCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="user", description="Get information about a user")
    @app_commands.describe(user="The user to view")
    async def user_info(self, interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user
        
        if interaction.guild:
            member = interaction.guild.get_member(target.id)
            if member:
                target = member

        embed = discord.Embed(color=target.color if hasattr(target, 'color') else discord.Color.blue())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_author(name=f"{target.display_name} ({target.name})", icon_url=target.display_avatar.url)
        
        embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
        
        created_at = discord.utils.format_dt(target.created_at, style="D")
        embed.add_field(name="Created", value=created_at, inline=True)
        
        if isinstance(target, discord.Member):
            if target.joined_at:
                joined_at = discord.utils.format_dt(target.joined_at, style="D")
                embed.add_field(name="Joined Server", value=joined_at, inline=True)
            
            roles = [role.mention for role in target.roles if role.name != "@everyone"]
            if len(roles) > 10:
                role_str = ", ".join(roles[:10]) + f" and {len(roles)-10} more..."
            elif roles:
                role_str = ", ".join(roles)
            else:
                role_str = "None"
                
            embed.add_field(name=f"Roles ({len(roles)})", value=role_str, inline=False)
            
            embed.color = target.top_role.color

        is_bot = "Bot" if target.bot else "Human"
        embed.set_footer(text=f"Type: {is_bot}")

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(UserInfoCommand(bot))