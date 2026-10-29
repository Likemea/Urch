# Urch/commands/txt2img.py
import discord
from discord import app_commands
from discord.ext import commands

from functions.image_gen import generate_image
from providers import IMAGE_MODELS
from safeguard import check_safeguard


class Txt2ImgCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="txt2img", description="Generate an image via Pollinations")
    @app_commands.describe(
        prompt="Description of the image",
        model="AI model to use",
        width="Width of the image",
        height="Height of the image",
        seed="Seed for reproducible results (-1 for random)",
        enhance="Urch prompt enhancement",
        quality="Image quality (low/medium/high) - gpt-image only",
    )
    @app_commands.choices(
        model=[
            app_commands.Choice(name=info["disp"], value=mid) for mid, info in IMAGE_MODELS.items()
        ]
    )
    @app_commands.choices(
        quality=[
            app_commands.Choice(name="Low", value="low"),
            app_commands.Choice(name="Medium", value="medium"),
            app_commands.Choice(name="High", value="high"),
        ]
    )
    async def txt2img(
        self,
        interaction: discord.Interaction,
        prompt: str,
        model: str = "dreamshaper",
        width: app_commands.Range[int, 128, 1024] = 512,
        height: app_commands.Range[int, 128, 1024] = 512,
        seed: int = -1,
        enhance: bool = False,
        quality: str = "low",
    ):
        rl = getattr(self.bot, "rate_limiter", None)
        if rl:
            allowed, wait_time, reason = rl.check(str(interaction.user.id), tier="medium")
            if not allowed:
                msg = (
                    reason
                    if wait_time <= 0
                    else f"⏳ Slow down! {reason} Try again in {wait_time:.1f}s."
                )
                await interaction.response.send_message(msg, ephemeral=True)
                return

        await interaction.response.defer(thinking=True)

        safeguard_func = getattr(self.bot, "check_safeguard", check_safeguard)
        try:
            safeguard_result = await safeguard_func([], prompt, "")
            verdict = safeguard_result.get("verdict", "safe").lower()
            if verdict in ["unsafe_input", "unsafe_output", "unsafe_both"]:
                reason = safeguard_result.get("reasoning", "No specific reason provided.")
                policy = safeguard_result.get("violated_policy", "General Safety Policy")
                msg = (
                    f"🛡️ **Safeguard Block ({verdict})**\n"
                    f"- **Reason**: {reason}\n"
                    f"- **Violated Policy**: {policy}"
                )
                await interaction.followup.send(msg)
                return
        except Exception as e:
            print(f"[txt2img] Safeguard check error: {e}")

        try:
            gen_kwargs = {"seed": seed, "enhance": enhance}
            if model == "gpt-image-2":
                gen_kwargs["quality"] = quality

            file = await generate_image(
                prompt=prompt, model=model, width=width, height=height, **gen_kwargs
            )

            if file:
                embed = discord.Embed(title="🎨 Image Result", color=discord.Color.purple())
                embed.add_field(name="Prompt", value=f"**{prompt}**", inline=False)
                embed.add_field(name="Model", value=f"**{model}**", inline=False)

                footer_parts = [f"{width}x{height}", f"seed: {seed}"]
                if enhance:
                    footer_parts.append("enhanced")
                if model == "gpt-image-2":
                    footer_parts.append(f"quality: {quality}")

                embed.set_footer(text=" | ".join(footer_parts))
                embed.set_image(url=f"attachment://{file.filename}")
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(
                    "❌ Failed to generate image. Please try again later.", ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Txt2ImgCommand(bot))
