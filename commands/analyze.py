# Urch/commands/analyze.py
import os
import asyncio
import discord
import requests
from discord import app_commands, Interaction
from discord.ext import commands
from utils import get_user_ai_params
import config


GROQ_API_KEY = config.GROQ_API_KEY
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
headers_groq = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

def generate_vision_response(image_url, prompt, user_id):
    
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }
    ]

    payload = {
        "model": "qwen/qwen3.8-27b", 
        "messages": messages,
        "temperature": 1,
        "max_completion_tokens": 1024
    }
   
    try:
        response_json = requests.post(GROQ_API_URL, headers=headers_groq, json=payload, timeout=30)
        response_json.raise_for_status()
        response_data = response_json.json()
        return response_data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Error analyzing image: {str(e)}"

async def generate_analysis(image_url, prompt, user_id):
    loop = asyncio.get_event_loop()
    msg = await loop.run_in_executor(None, generate_vision_response, image_url, prompt, user_id)
    return msg

async def dispatch_analysis(interaction: Interaction, image_url: str, prompt: str):
    user_id = str(interaction.user.id)
    response = await generate_analysis(image_url, prompt, user_id)
    
    if len(response) > 1900:
        chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
        await interaction.followup.send(chunks[0])
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk) 
    else:
        await interaction.followup.send(response)


class AnalyzeCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.ctx_menu = app_commands.ContextMenu(
            name="Analyze Image",
            callback=self.analyze_context
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @app_commands.command(name="analyze", description="Analyze an image")
    @app_commands.describe(file="The image to analyze", prompt="Specific question about the image (Optional)")
    async def analyze_slash(self, interaction: discord.Interaction, file: discord.Attachment, prompt: str = "Describe this image in detail."):
        if not file.content_type or not file.content_type.startswith('image'):
            await interaction.response.send_message("❌ Please upload a valid image file.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        try:
            await dispatch_analysis(interaction, file.url, prompt)
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}")

    async def analyze_context(self, interaction: discord.Interaction, message: discord.Message):
        if not message.attachments:
            await interaction.response.send_message("❌ No image attachment found", ephemeral=True)
            return
            
        attachment = message.attachments[0]
        if not attachment.content_type or not attachment.content_type.startswith('image'):
            await interaction.response.send_message("❌ attachment is not an image", ephemeral=True)
            return
            
        default_prompt = "Describe this image in detail."

        await interaction.response.defer(thinking=True)
        try:
            await dispatch_analysis(interaction, attachment.url, default_prompt)
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}")


async def setup(bot):
    await bot.add_cog(AnalyzeCommand(bot))