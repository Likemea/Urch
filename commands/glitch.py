# Urch/commands/glitch.py
import io
import random
import discord
import numpy as np
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageEnhance


class GlitchCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="glitch", description="Glitch an image or GIF")
    @app_commands.describe(
        image="The image or GIF to glitch", intensity="How glitchy it should be (1-10)"
    )
    async def glitch(
        self, interaction: discord.Interaction, image: discord.Attachment, intensity: int = 5
    ):
        await interaction.response.defer(thinking=True)

        if not (1 <= intensity <= 10):
            await interaction.followup.send("Intensity must be between 1 and 10", ephemeral=True)
            return

        if not (
            image.content_type.startswith("image")
            or image.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))
        ):
            await interaction.followup.send(
                "Only PNG, JPG, and GIF files supported", ephemeral=True
            )
            return

        try:
            img_data = await image.read()
            input_image = Image.open(io.BytesIO(img_data)).convert("RGB")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to load image: {e}", ephemeral=True)
            return

        is_gif = image.filename.lower().endswith(".gif")
        if is_gif:
            frames = []
            try:
                input_image.seek(0)
                while True:
                    frames.append(input_image.copy().convert("RGB"))
                    input_image.seek(input_image.tell() + 1)
            except EOFError:
                pass
            if len(frames) == 0:
                frames = [input_image]
        else:
            frames = [input_image]

        glitched_frames = []
        glitch_intensity = intensity / 10.0
        for i, frame in enumerate(frames):
            local_intensity = glitch_intensity * (0.8 + 0.4 * (i % 3) / 2)
            glitched = self.apply_glitch(frame, local_intensity)
            glitched_frames.append(glitched)

        with io.BytesIO() as output:
            glitched_frames[0].save(
                output,
                format="GIF",
                save_all=True,
                append_images=glitched_frames[1:],
                duration=150 if is_gif else 250,
                loop=0,
                disposal=2,
            )
            output.seek(0)
            filename = f"glitched_{'gif' if is_gif else 'img'}_lvl{intensity}.gif"
            await interaction.followup.send(f"", file=discord.File(output, filename=filename))

    def apply_glitch(self, img: Image.Image, intensity: float) -> Image.Image:
        w, h = img.size
        np_img = np.array(img)
        if random.random() < 0.8:
            shift_x = int((random.randint(-5, 5) * intensity))
            shift_y = int((random.randint(-3, 3) * intensity))
            r = np.roll(np_img[:, :, 0], shift=(shift_y, shift_x), axis=(0, 1))
            g = np_img[:, :, 1]
            b = np.roll(np_img[:, :, 2], shift=(-shift_y, -shift_x), axis=(0, 1))
            np_img = np.stack([r, g, b], axis=2)
        if random.random() < 0.6:
            scanline = np.zeros_like(np_img)
            scanline[::2] = np_img[::2]
            np_img = (np_img * 0.7 + scanline * 0.3).astype(np.uint8)
        if random.random() < 0.5 * intensity:
            try:
                axis = random.choice([0, 1])
                idx = random.randint(0, h - 1 if axis == 1 else w - 1)
                region_size = max(1, int(20 * intensity))
                if axis == 1:
                    start = max(0, idx - region_size // 2)
                    end = min(h, idx + region_size // 2)
                    strip = np_img[start:end, :, :]
                    brightness = np.mean(strip, axis=2)
                    for y in range(strip.shape[0]):
                        order = np.argsort(brightness[y])
                        if random.random() < 0.5:
                            order = order[::-1]
                        strip[y] = strip[y][order]
                    np_img[start:end, :, :] = strip
            except Exception:
                pass
        pil_img = Image.fromarray(np_img)
        if random.random() < 0.4:
            enhancer = ImageEnhance.Contrast(pil_img)
            pil_img = enhancer.enhance(1 + 0.5 * intensity * random.choice([-1, 1]))
        if random.random() < 0.3:
            enhancer = ImageEnhance.Brightness(pil_img)
            pil_img = enhancer.enhance(1 + 0.4 * intensity * random.choice([-1, 1]))
        if intensity > 0.7 and random.random() < 0.3:
            noise = np.random.randint(0, 256, np_img.shape, dtype=np.uint8)
            mask = np.random.rand(*np_img.shape[:2]) < (0.02 * intensity)
            noisy = np.where(mask[..., None], noise, np.array(pil_img))
            pil_img = Image.fromarray(noisy.astype(np.uint8))
        return pil_img


async def setup(bot):
    await bot.add_cog(GlitchCommand(bot))
