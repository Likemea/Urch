# Urch/commands/help.py
import discord
from discord import app_commands
from discord.ext import commands


class HelpView(discord.ui.View):
    def __init__(self, embeds):
        super().__init__(timeout=180)
        self.embeds = embeds
        self.current_page = 0
        self.total_pages = len(embeds)
        self.update_buttons()

    def update_buttons(self):
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == self.total_pages - 1
        self.children[2].label = f"Page {self.current_page + 1}/{self.total_pages}"

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass


class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Get a list of available commands")
    async def help(self, interaction: discord.Interaction):
        commands_list = []
        for cmd in self.bot.tree.get_commands():
            if hasattr(cmd, "type") and cmd.type.value != 1:
                continue

            desc = cmd.description or "No description provided."
            commands_list.append(f"``/{cmd.name}`` - {desc}")

        commands_list.sort()

        per_page = 10
        chunks = [commands_list[i : i + per_page] for i in range(0, len(commands_list), per_page)]

        if not chunks:
            await interaction.response.send_message("⚠️ No commands found.", ephemeral=True)
            return

        embeds = []
        for i, chunk in enumerate(chunks):
            embed = discord.Embed(
                title="📚 Urch Command List",
                description="Here are all available commands:",
                color=discord.Color.blurple(),
            )
            embed.description += "\n\n" + "\n".join(chunk)
            embed.set_footer(
                text=f"Page {i + 1}/{len(chunks)} • Total Commands: {len(commands_list)}"
            )
            embeds.append(embed)

        try:
            view = HelpView(embeds) if len(embeds) > 1 else None
            await interaction.user.send(embed=embeds[0], view=view)
            await interaction.response.send_message(
                "📬 Sent you a DM with the command list!", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I couldn't DM you. Please check your privacy settings.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(HelpCommand(bot))
