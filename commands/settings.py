# Urch/commands/settings.py
import json
import os
import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    get_user_ai_params, set_user_ai_param, MODEL_LIST,
    get_user_personas, add_new_persona, delete_user_persona, 
    equip_user_persona, edit_existing_persona
)

class SettingsCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="settings", description="Manage Urch configurations")
    @app_commands.choices(action=[
        app_commands.Choice(name="View", value="view"),
        app_commands.Choice(name="Edit", value="edit")
    ])
    async def settings(self, interaction: discord.Interaction, action: str):
        if action == "view":
            await self.view_settings(interaction)
        elif action == "edit":
            await self.edit_settings(interaction)

    async def view_settings(self, interaction: discord.Interaction):
        user_params = await get_user_ai_params(str(interaction.user.id))
        
        params_display = []
        for k, v in user_params.items():
            if k in ["user_persona", "ai_persona"] and len(str(v)) > 50:
                val_str = str(v)[:50] + "..."
            elif k == "model":
                if v == "Auto":
                    val_str = "Auto"
                else:
                    val_str = MODEL_LIST.get(v, {}).get("disp", v)
            else:
                val_str = str(v)
            
            params_display.append(f"**{k.replace('_', ' ').title()}:** {val_str}")

        params_str = "\n".join(params_display)
        embed = discord.Embed(title="⚙️ Your AI Parameters", description=params_str, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def edit_settings(self, interaction: discord.Interaction):
        view = MainSettingsView(str(interaction.user.id), self.bot)
        embed = discord.Embed(title="⚙️ Settings", description="Choose a category", color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ───────────────────────────────
# MAIN SETTINGS VIEW
# ───────────────────────────────

class MainSettingsView(discord.ui.View):
    def __init__(self, user_id, bot):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bot = bot

    @discord.ui.button(label="Personas", style=discord.ButtonStyle.primary, emoji="🎭")
    async def personas_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        personas, active_name = await get_user_personas(self.user_id)
        view = PersonasView(self.user_id, self.bot, self, personas, active_name)
        await view.refresh_embed(interaction)

    @discord.ui.button(label="Advanced", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def advanced_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_params = await get_user_ai_params(self.user_id)
        view = AdvancedSettingsView(self.user_id, user_params, self.bot, self)
        await view.refresh_embed(interaction)

# ───────────────────────────────
# PERSONA SYSTEM
# ───────────────────────────────

class PersonaSelect(discord.ui.Select):
    def __init__(self, user_id, personas, active_name):
        options = []
        for name in personas.keys():
            is_default = (name == active_name)
            options.append(discord.SelectOption(label=name, value=name, default=is_default))

        super().__init__(placeholder="Select active Persona", min_values=1, max_values=1, options=options)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        selected_name = self.values[0]
        if await equip_user_persona(self.user_id, selected_name):
             personas, active_name = await get_user_personas(self.user_id)
             view = PersonasView(self.user_id, interaction.client, None, personas, active_name)
             await view.refresh_embed(interaction, msg=f"✅ Equipped **{selected_name}**")
        else:
             await interaction.response.send_message("❌ Failed to equip persona.", ephemeral=True)

class PersonasView(discord.ui.View):
    def __init__(self, user_id, bot, parent_view, personas, active_name):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bot = bot
        self.parent_view = parent_view
        
        self.rebuild_components(personas, active_name)

    def rebuild_components(self, personas, active_name):
        self.clear_items()
        
        self.add_item(PersonaSelect(self.user_id, personas, active_name))
        
        create_btn = discord.ui.Button(label="Create", style=discord.ButtonStyle.success, emoji="➕", custom_id="create_p")
        create_btn.callback = self.create_callback
        self.add_item(create_btn)
        
        edit_btn = discord.ui.Button(label="Edit", style=discord.ButtonStyle.primary, emoji="📝", custom_id="edit_p")
        edit_btn.callback = self.edit_callback
        self.add_item(edit_btn)
        
        del_btn = discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑", custom_id="del_p")
        del_btn.callback = self.delete_callback
        self.add_item(del_btn)
        
        back_btn = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀", custom_id="back_p", row=2)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def refresh_embed(self, interaction: discord.Interaction, msg=""):
        # Fetch fresh data async
        personas, active_name = await get_user_personas(self.user_id)
        
        desc = f"**Current Persona:** `{active_name}`\n\n"
        
        active_p = personas.get(active_name, {})
        u_p = active_p.get("user_persona", "None")
        a_p = active_p.get("ai_persona", "None")
        
        if len(u_p) > 100: u_p = u_p[:100] + "..."
        if len(a_p) > 100: a_p = a_p[:100] + "..."
        
        desc += f"**About You:** {u_p}\n"
        desc += f"**Instructions:** {a_p}\n\n"
        desc += "------------------\n"
        desc += "**Personas:**\n"
        
        for name in personas:
            icon = "✅" if name == active_name else "▪️"
            desc += f"{icon} {name}\n"
            
        embed = discord.Embed(title="🎭 Persona Manager", description=desc, color=discord.Color.gold())
        if msg: embed.set_footer(text=msg)
        
        self.rebuild_components(personas, active_name)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def create_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PersonaModal(self.user_id, mode="create", view=self))

    async def edit_callback(self, interaction: discord.Interaction):
        personas, active_name = await get_user_personas(self.user_id)
        current_persona = personas.get(active_name, {})
        
        u_p = current_persona.get("user_persona", "")
        a_p = current_persona.get("ai_persona", "")
        await interaction.response.send_modal(PersonaModal(self.user_id, mode="edit", view=self, persona_name=active_name, current_user_persona=u_p, current_ai_persona=a_p))

    async def delete_callback(self, interaction: discord.Interaction):
        _, active_name = await get_user_personas(self.user_id)
        if active_name == "Default":
             await interaction.response.send_message("❌ Cannot delete Default persona.", ephemeral=True)
             return

        success = await delete_user_persona(self.user_id, active_name)
        if success:
            await self.refresh_embed(interaction, msg=f"🗑 Deleted {active_name}")
        else:
            await interaction.response.send_message("❌ Could not delete (must have at least 1 persona).", ephemeral=True)

    async def back_callback(self, interaction: discord.Interaction):
        view = MainSettingsView(self.user_id, self.bot)
        embed = discord.Embed(title="⚙️ Settings Menu", description="Choose a category", color=discord.Color.blurple())
        await interaction.response.edit_message(embed=embed, view=view)

class PersonaModal(discord.ui.Modal):
    def __init__(self, user_id, mode, view, persona_name=None, current_user_persona="", current_ai_persona=""):
        self.user_id = user_id
        self.mode = mode
        self.view_obj = view
        self.target_name = persona_name
        
        title = "Create New Persona" if mode == "create" else f"Edit: {persona_name}"
        super().__init__(title=title)
        
        default_u = ""
        default_a = ""

        if mode == "create":
            self.p_name = discord.ui.TextInput(label="Persona Name", placeholder="My Persona", max_length=30, required=True)
            self.add_item(self.p_name)

        self.user_p = discord.ui.TextInput(label="About You", placeholder="I am a Python developer...", style=discord.TextStyle.paragraph, required=False, default=current_user_persona, max_length=500)
        self.ai_p = discord.ui.TextInput(label="Custom Instructions", placeholder="Always reply in code blocks...", style=discord.TextStyle.paragraph, required=False, default=current_ai_persona, max_length=500)
        
        self.add_item(self.user_p)
        self.add_item(self.ai_p)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.p_name.value if self.mode == "create" else self.target_name
        
        if self.mode == "create":
            success, msg = await add_new_persona(self.user_id, name, self.user_p.value, self.ai_p.value)
            if success:
                await equip_user_persona(self.user_id, name)
                await self.view_obj.refresh_embed(interaction, msg=f"✅ Created & Equipped **{name}**")
            else:
                await interaction.response.send_message(f"❌ Error: {msg}", ephemeral=True)
        else:
            await edit_existing_persona(self.user_id, name, self.user_p.value, self.ai_p.value)
            await self.view_obj.refresh_embed(interaction, msg=f"✅ Updated **{name}**")

# ───────────────────────────────
# ADVANCED SETTINGS
# ───────────────────────────────

class ModelSelect(discord.ui.Select):
    def __init__(self, user_id, current_model):
        options = [discord.SelectOption(label="🔄 Auto", value="Auto", description="Let Urch choose")]
        for key, info in MODEL_LIST.items():
            options.append(discord.SelectOption(label=info["disp"], value=key, description=info["id"]))

        for opt in options:
            if opt.value == str(current_model):
                opt.default = True

        super().__init__(placeholder="Choose your model", min_values=1, max_values=1, options=options, row=0)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await set_user_ai_param(self.user_id, "model", self.values[0])
        await interaction.response.defer()

class ReasoningSelect(discord.ui.Select):
    def __init__(self, user_id, current_val):
        options = [
            discord.SelectOption(label="Auto", value="Auto", description="Urch decides when to use tools"),
            discord.SelectOption(label="True", value="True", description="Urch always uses tools"),
            discord.SelectOption(label="False", value="False", description="Urch never uses tools")
        ]
        
        for opt in options:
            if opt.value == str(current_val):
                opt.default = True

        super().__init__(placeholder="Reasoning", min_values=1, max_values=1, options=options, row=1)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await set_user_ai_param(self.user_id, "reasoning", self.values[0])
        await interaction.response.defer()

class AdvancedSettingsView(discord.ui.View):
    def __init__(self, user_id, params, bot, parent_view):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bot = bot
        
        self.add_item(ModelSelect(user_id, params.get("model", "Auto")))
        self.add_item(ReasoningSelect(user_id, params.get("reasoning", "Auto")))
        
        num_btn = discord.ui.Button(label="Parameters", style=discord.ButtonStyle.primary, emoji="🔢", row=2)
        num_btn.callback = self.numeric_callback
        self.add_item(num_btn)

        back_btn = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀", row=2)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def refresh_embed(self, interaction: discord.Interaction):
        user_params = await get_user_ai_params(self.user_id)
        
        desc = "## Current Configuration\n"
        model_key = user_params.get("model", "Auto")
        model_disp = MODEL_LIST.get(model_key, {}).get("disp", model_key) if model_key != "Auto" else "Auto"
        
        desc += f"**Model:** {model_disp}\n"
        desc += f"**Reasoning:** {user_params.get('reasoning', 'Auto')}\n"
        desc += f"**Temperature:** {user_params.get('temperature', 0.7)}\n"
        desc += f"**Max Tokens:** {user_params.get('max_completion_tokens', 512)}\n"
        
        embed = discord.Embed(title="🔧 Advanced Settings", description=desc, color=discord.Color.dark_grey())
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def numeric_callback(self, interaction: discord.Interaction):
        params = await get_user_ai_params(self.user_id)
        await interaction.response.send_modal(AdvancedParamsModal(self.user_id, self, params))

    async def back_callback(self, interaction: discord.Interaction):
        view = MainSettingsView(self.user_id, self.bot)
        embed = discord.Embed(title="⚙️ Settings Menu", description="Choose a category", color=discord.Color.blurple())
        await interaction.response.edit_message(embed=embed, view=view)

def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))

class AdvancedParamsModal(discord.ui.Modal, title="Parameters"):
    def __init__(self, user_id, view_obj, params):
        super().__init__()
        self.user_id = user_id
        self.view_obj = view_obj
        
        # Use passed params
        self.temperature = discord.ui.TextInput(
            label="Temperature (0.0 - 2.0)", 
            placeholder="0.7", 
            required=False,
            default=str(params.get("temperature", 0.7))
        )
        
        self.max_completion_tokens = discord.ui.TextInput(
            label="Max Tokens (5 - 4096)",
            placeholder="512", 
            required=False,
            default=str(params.get("max_completion_tokens", 512))
        )
        
        self.add_item(self.temperature)
        self.add_item(self.max_completion_tokens)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.max_completion_tokens.value:
                raw = int(self.max_completion_tokens.value)
                clamped = clamp(raw, 5, 4096)
                await set_user_ai_param(self.user_id, "max_completion_tokens", clamped)
                
            if self.temperature.value:
                raw = float(self.temperature.value)
                clamped = clamp(raw, 0.0, 2.0)
                await set_user_ai_param(self.user_id, "temperature", clamped)
                
            await self.view_obj.refresh_embed(interaction)
            
        except ValueError:
            await interaction.response.send_message("❌ Invalid number format.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(SettingsCommand(bot))