# Urch/commands/ask.py
import os
import asyncio
import json

import discord
import aiohttp
from discord import app_commands
from discord.ext import commands

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
HEADERS_GROQ = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

async def generate_response(prompt, user_id):
    
    messages = [
        {"role": "system", "content": "You are Urch, an AI assistant developed by urghan2, Likemea, and Urch AI."},
        {"role": "user", "content": prompt}
    ]

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "temperature": 1,
        "max_completion_tokens": 512
    }
   
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_API_URL, headers=HEADERS_GROQ, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                response = data["choices"][0]["message"]["content"].strip()
                print(response)
                return response
    except Exception as e:
        return f"⚠️ Unexpected error: {str(e)}"

class AskCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ask", description="Ask Urch something")
    @app_commands.describe(prompt="Your prompt")
    async def prompt(self, interaction: discord.Interaction, prompt: str):
        user_id = str(interaction.user.id)
        await interaction.response.defer(thinking=True)
        response = await generate_response(prompt, user_id)
        
        if len(response) > 1900:
            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
            await interaction.followup.send(chunks[0])
            for chunk in chunks[1:]:
                await interaction.channel.send(chunk)
        else:
            await interaction.followup.send(response)

async def setup(bot):
    await bot.add_cog(AskCommand(bot))