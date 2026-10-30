# Urch/commands/biome.py
import time
import discord
from discord import app_commands
from discord.ext import commands

from biomes import (
    BIOMES,
    RARITY_ID_TO_NAME,
    get_active_biome,
    get_next_biome_timestamp,
)


def _format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


class BiomeBrowserView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=180)
        self.user_id = str(user_id)
        self.mode = "status"  # "status" or "browse"
        self.biome_keys = list(BIOMES.keys())
        self.page = 0
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.mode == "status":
            browse_btn = discord.ui.Button(
                label="📖 Browse All Biomes", style=discord.ButtonStyle.secondary
            )
            browse_btn.callback = self.switch_to_browse
            self.add_item(browse_btn)
        else:
            prev_btn = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)

            next_btn = discord.ui.Button(label="➡️ Next", style=discord.ButtonStyle.secondary)
            next_btn.callback = self.next_page
            self.add_item(next_btn)

            status_btn = discord.ui.Button(
                label="📡 Live Status", style=discord.ButtonStyle.primary
            )
            status_btn.callback = self.switch_to_status
            self.add_item(status_btn)

    async def switch_to_browse(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn't your menu.", ephemeral=True)
        self.mode = "browse"
        self.update_buttons()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    async def switch_to_status(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn't your menu.", ephemeral=True)
        self.mode = "status"
        self.update_buttons()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    async def prev_page(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn't your menu.", ephemeral=True)
        self.page = (self.page - 1) % len(self.biome_keys)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn't your menu.", ephemeral=True)
        self.page = (self.page + 1) % len(self.biome_keys)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    def format_embed(self) -> discord.Embed:
        now = time.time()
        if self.mode == "status":
            active = get_active_biome(now=now)
            if active:
                mult_val = active["multiplier"]
                mult_str = (
                    f"x{int(mult_val)}" if float(mult_val).is_integer() else f"x{mult_val:.1f}"
                )
                rem_str = _format_duration(int(active["ends_at"] - now))
                defn = BIOMES.get(active["id"], {})
                rarity_lines = [
                    f"• {RARITY_ID_TO_NAME.get(rid, rid)}" for rid in defn.get("rarities", [])
                ]
                rarities_text = "\n".join(rarity_lines) if rarity_lines else "None"
                if len(rarities_text) > 1000:
                    rarities_text = rarities_text[:990] + "\n..."

                embed = discord.Embed(
                    title=f"{active['emoji']} Biome: {active['name']}",
                    description=f"*{active['description']}*",
                    color=discord.Color(active.get("color", 0x5865F2)),
                )
                embed.add_field(name="Chance Boost", value=f"**{mult_str}**", inline=True)
                embed.add_field(name="Time Remaining", value=f"**{rem_str}**", inline=True)
                embed.add_field(
                    name=f"Boosted Rarities ({len(rarity_lines)})",
                    value=rarities_text,
                    inline=False,
                )
                embed.set_footer(text="Applies to /roll and /autoroll")
                return embed
            else:
                next_ts = get_next_biome_timestamp()
                wait_secs = max(0, int(next_ts - now))
                wait_str = _format_duration(wait_secs)
                embed = discord.Embed(
                    title="🌤️ No Biome",
                    description=(
                        "Atmosphere is tranquil. Server-wide biomes trigger every few hours for **15–30 minutes**, "
                        "boosting themed rarities by **x3 to x10**."
                    ),
                    color=discord.Color.blurple(),
                )
                embed.add_field(
                    name="Next Biome",
                    value=f"⏳ In **{wait_str}**",
                    inline=False,
                )
                embed.set_footer(text="Biomes rotate automatically")
                return embed
        else:
            key = self.biome_keys[self.page]
            defn = BIOMES[key]
            rarity_lines = [
                f"• {RARITY_ID_TO_NAME.get(rid, rid)}" for rid in defn.get("rarities", [])
            ]
            rarities_text = "\n".join(rarity_lines) if rarity_lines else "None"
            if len(rarities_text) > 1000:
                rarities_text = rarities_text[:990] + "\n..."

            embed = discord.Embed(
                title=f"{defn['emoji']} {defn['name']} ({self.page + 1}/{len(self.biome_keys)})",
                description=f"*{defn['description']}*",
                color=discord.Color(defn.get("color", 0x5865F2)),
            )
            embed.add_field(name="Possible Boost", value="**x3 to x10**", inline=True)
            embed.add_field(name="Duration", value="**15–30 minutes**", inline=True)
            embed.add_field(
                name=f"Boosted Rarities ({len(rarity_lines)})",
                value=rarities_text,
                inline=False,
            )
            embed.set_footer(text=f"Biome ID: {key}")
            return embed


class BiomeCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="biome", description="View the current server-wide biome event or browse all biomes"
    )
    async def biome(self, interaction: discord.Interaction):
        view = BiomeBrowserView(str(interaction.user.id))
        embed = view.format_embed()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(BiomeCommand(bot))
