# Urch/commands/ask.py
import os
import asyncio
import re
import json

import discord
import requests
from discord import app_commands
from discord.ext import commands
from utils import get_user_ai_params

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
headers_groq = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

DEFAULT_AI_PARAMS = {
    "max_completion_tokens": 256,
    "temperature": 1,
}

def generate_response(prompt, user_id):
    user_params = DEFAULT_AI_PARAMS
    
    messages = [
        {"role": "system", "content": "."},
        {"role": "user", "content": prompt}
    ]

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "temperature": user_params.get("temperature", 1),
        "max_completion_tokens": user_params.get("max_completion_tokens", 256)
    }
   
    try:
        response_json = requests.post(GROQ_API_URL, headers=headers_groq, json=payload, timeout=20)
        response_json.raise_for_status()
        data = response_json.json()
        response = data["choices"][0]["message"]["content"].strip()
        print(response)
        return response
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

async def generate_text(prompt, user_id):
    loop = asyncio.get_event_loop()
    msg = await loop.run_in_executor(None, generate_response, prompt, user_id)
    return msg

class AskCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ask", description="Ask Urch something")
    @app_commands.describe(prompt="Your prompt")
    async def prompt(self, interaction: discord.Interaction, prompt: str):
        user_id = str(interaction.user.id)
        await interaction.response.defer(thinking=True)
        response = await generate_text(prompt, user_id)
        
        if len(response) > 1900:
            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
            await interaction.followup.send(chunks[0])
            for chunk in chunks[1:]:
                await interaction.channel.send(chunk)
        else:
            await interaction.followup.send(response)

async def setup(bot):
  await bot.add_cog(AskCommand(bot))