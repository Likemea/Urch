import discord
from discord import app_commands
from discord.ext import commands

BADGE_MAPPING = {
    "staff": "⚙️ Discord Staff",
    "partner": "🤝 Partnered Server Owner",
    "hypesquad": "🏠 HypeSquad Events",
    "hypesquad_bravery": "🛡️ HypeSquad Bravery",
    "hypesquad_brilliance": "💡 HypeSquad Brilliance",
    "hypesquad_balance": "⚖️ HypeSquad Balance",
    "early_supporter": "💎 Early Supporter",
    "verified_bot_developer": "👨‍💻 Early Verified Bot Developer",
    "active_developer": "🛠️ Active Developer",
    "bot_http_interactions": "🌐 HTTP Bot",
}

class UserInfoCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="user", description="Get information about a user")
    @app_commands.describe(user="The user to view")
    async def user_info(self, interaction: discord.Interaction, user: discord.User | None = None):
        target = user or interaction.user

        if not target.banner or not target.public_flags:
            try:
                target = await self.bot.fetch_user(target.id)
            except discord.HTTPException:
                pass

        if interaction.guild:
            guild_member = interaction.guild.get_member(target.id)
            if guild_member:
                target = guild_member

        embed_color = discord.Color.blue()
        if isinstance(target, discord.Member) and target.top_role.color != discord.Color.default():
            embed_color = target.top_role.color

        embed = discord.Embed(color=embed_color)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_author(name=f"{target.display_name} (@{target.name})", icon_url=target.display_avatar.url)

        embed.add_field(name="User ID", value=f"`{target.id}`", inline=True)
        embed.add_field(name="Account Type", value="Bot 🤖" if target.bot else "Human 👤", inline=True)

        user_flags = [flag_name for flag_name, value in target.public_flags if value]
        badges = [BADGE_MAPPING.get(flag, flag.replace("_", " ").title()) for flag in user_flags]
        if badges:
            embed.add_field(name="Badges", value=", ".join(badges), inline=False)

        created_dt = f"{discord.utils.format_dt(target.created_at, style='D')} ({discord.utils.format_dt(target.created_at, style='R')})"
        embed.add_field(name="Account Created", value=created_dt, inline=False)

        if isinstance(target, discord.Member):
            if target.joined_at:
                joined_dt = f"{discord.utils.format_dt(target.joined_at, style='D')} ({discord.utils.format_dt(target.joined_at, style='R')})"
                
                sorted_members = sorted(
                    [m for m in interaction.guild.members if m.joined_at],
                    key=lambda m: m.joined_at
                )
                if target in sorted_members:
                    join_pos = sorted_members.index(target) + 1
                    joined_dt += f"\n*Join Position: #{join_pos}*"

                embed.add_field(name="Joined Server", value=joined_dt, inline=False)

            if target.premium_since:
                boost_dt = discord.utils.format_dt(target.premium_since, style="R")
                embed.add_field(name="Server Booster", value=f"Boosting since {boost_dt} 🚀", inline=True)

            status_flags = []
            if target.id == interaction.guild.owner_id:
                status_flags.append("👑 Owner")
            elif target.guild_permissions.administrator:
                status_flags.append("🛡️ Admin")
            elif target.guild_permissions.manage_guild or target.guild_permissions.ban_members:
                status_flags.append("⚔️ Mod")

            if status_flags:
                embed.add_field(name="Key Status", value=", ".join(status_flags), inline=True)

            roles = [role.mention for role in target.roles if role.name != "@everyone"]
            if len(roles) > 10:
                role_str = ", ".join(roles[:10]) + f" and {len(roles) - 10} more..."
            elif roles:
                role_str = ", ".join(roles)
            else:
                role_str = "None"

            embed.add_field(name=f"Roles ({len(roles)})", value=role_str, inline=False)

        links = [f"[Avatar]({target.display_avatar.url})"]
        if hasattr(target, "guild_avatar") and target.guild_avatar:
            links.append(f"[Server Avatar]({target.guild_avatar.url})")
        if target.banner:
            links.append(f"[Banner]({target.banner.url})")
            embed.set_image(url=target.banner.url)

        embed.add_field(name="Profile Links", value=" • ".join(links), inline=False)
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(UserInfoCommand(bot))