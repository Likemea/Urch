# Urch/commands/settings.py
import json
import os
import discord
from discord import app_commands
from discord.ext import commands

# Import wrappers from utils (which are now async)
from utils import (
    get_user_ai_params, set_user_ai_param, MODEL_LIST,
    get_user_personas, add_new_persona, delete_user_persona, 
    equip_user_persona, edit_existing_persona
)
from functions.memory import memory_manager

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
        # Await the async function
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
        # Fetch data asynchronously BEFORE initializing the view
        personas, active_name = await get_user_personas(self.user_id)
        view = PersonasView(self.user_id, self.bot, self, personas, active_name)
        await view.refresh_embed(interaction)

    @discord.ui.button(label="Advanced", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def advanced_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_params = await get_user_ai_params(self.user_id)
        view = AdvancedSettingsView(self.user_id, user_params, self.bot, self)
        await view.refresh_embed(interaction)
        
    @discord.ui.button(label="Memories", style=discord.ButtonStyle.success, emoji="💭", row=1)
    async def memories_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MemoryBrowserView(self.user_id, self.bot)
        await view.refresh_embed(interaction)
        
# ───────────────────────────────
# MEMORY SYSTEM UI
# ───────────────────────────────

class MemorySelect(discord.ui.Select):
    def __init__(self, memories_page, page_index):
        options = []
        for idx, (real_idx, mem_text) in enumerate(memories_page):
            prefix = f"#{real_idx+1}: "
            prefix_len = len(prefix)
            max_content_len = 100 - prefix_len
            
            if len(mem_text) > max_content_len:
                trunc_len = max(0, max_content_len - 3)
                label = f"{prefix}{mem_text[:trunc_len]}..."
            else:
                label = f"{prefix}{mem_text}"

            options.append(discord.SelectOption(label=label, value=str(real_idx)))

        if not options:
            options.append(discord.SelectOption(label="No memories on this page", value="-1"))

        super().__init__(placeholder="Select a memory", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        selected_idx = int(self.values[0])
        if selected_idx == -1:
            await interaction.response.defer()
            return
        
        view = MemoryActionView(interaction.user.id, selected_idx, self.view)
        embed = discord.Embed(title="Memory Actions", description=f"What do you want to do with Memory #{selected_idx+1}?", color=discord.Color.teal())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class MemoryBrowserView(discord.ui.View):
    def __init__(self, user_id, bot):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bot = bot
        self.page = 0
        self.memories = []
        
        # Initial load might be synchronous if memory_manager is sync. 
        # If memory_manager uses SQL now, we need to refactor. 
        # Assuming memory_manager is still sync or handles its own async loop for now based on provided files.
        self.load_data()
        self.rebuild_components()

    def load_data(self):
        all_mems = memory_manager.get_all_memories(self.user_id)
        self.memories = [(i, m["text"]) for i, m in enumerate(all_mems)]

    def rebuild_components(self):
        self.clear_items()
        # Ensure data is loaded (if pagination changes)
        
        ITEMS_PER_PAGE = 10
        total_pages = (len(self.memories) - 1) // ITEMS_PER_PAGE + 1
        if total_pages < 1: total_pages = 1
        if self.page >= total_pages: self.page = total_pages - 1
        
        start = self.page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = self.memories[start:end]
        
        if page_items:
            self.add_item(MemorySelect(page_items, self.page))
        else:
            sel = discord.ui.Select(placeholder="No memories found", options=[discord.SelectOption(label="Empty", value="-1")], disabled=True, row=0)
            self.add_item(sel)

        add_btn = discord.ui.Button(label="New", style=discord.ButtonStyle.success, emoji="➕", row=1)
        add_btn.callback = self.add_callback
        self.add_item(add_btn)
        
        conf_btn = discord.ui.Button(label="Config", style=discord.ButtonStyle.secondary, emoji="⚙️", row=1)
        conf_btn.callback = self.config_callback
        self.add_item(conf_btn)

        prev_btn = discord.ui.Button(label="◀", style=discord.ButtonStyle.primary, disabled=(self.page == 0), row=2)
        prev_btn.callback = self.prev_callback
        self.add_item(prev_btn)
        
        count_btn = discord.ui.Button(label=f"{self.page+1}/{total_pages}", style=discord.ButtonStyle.gray, disabled=True, row=2)
        self.add_item(count_btn)
        
        next_btn = discord.ui.Button(label="▶", style=discord.ButtonStyle.primary, disabled=(self.page >= total_pages - 1), row=2)
        next_btn.callback = self.next_callback
        self.add_item(next_btn)
        
        back_btn = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, emoji="↩", row=3)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def refresh_embed(self, interaction: discord.Interaction):
        # Reload data in case of changes
        self.load_data()
        self.rebuild_components()
        
        ITEMS_PER_PAGE = 10
        start = self.page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = self.memories[start:end]
        
        if not page_items:
            list_str = "*No memories stored yet.*"
        else:
            lines = []
            for real_idx, text in page_items:
                preview = text[:60].replace("\n", " ") + "..." if len(text) > 60 else text
                lines.append(f"`#{real_idx+1}` {preview}")
            list_str = "\n".join(lines)

        params = await get_user_ai_params(self.user_id)
        status = "🟢 Enabled" if params.get("memory_enabled", True) else "🔴 Disabled"
        
        desc = f"**Status:** {status}\n**Total Memories:** {len(self.memories)}\n\n{list_str}"
        
        embed = discord.Embed(title="🧠 Memory Bank", description=desc, color=discord.Color.dark_magenta())
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def add_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MemoryEditModal(self.user_id, self, mode="add"))

    async def config_callback(self, interaction: discord.Interaction):
        view = MemoryConfigView(self.user_id, self.bot, self)
        await view.refresh_embed(interaction)

    async def prev_callback(self, interaction: discord.Interaction):
        self.page -= 1
        await self.refresh_embed(interaction)

    async def next_callback(self, interaction: discord.Interaction):
        self.page += 1
        await self.refresh_embed(interaction)

    async def back_callback(self, interaction: discord.Interaction):
        view = MainSettingsView(self.user_id, self.bot)
        embed = discord.Embed(title="⚙️ Settings Menu", description="Choose a category", color=discord.Color.blurple())
        await interaction.response.edit_message(embed=embed, view=view)

class MemoryActionView(discord.ui.View):
    def __init__(self, user_id, memory_index, browser_view):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.index = memory_index
        self.browser = browser_view

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, emoji="📝")
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        all_mems = memory_manager.get_all_memories(self.user_id)
        current_text = ""
        if 0 <= self.index < len(all_mems):
            current_text = all_mems[self.index]["text"]
            
        await interaction.response.send_modal(MemoryEditModal(self.user_id, self.browser, mode="edit", index=self.index, current_text=current_text))

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        success = memory_manager.delete_memory(self.user_id, self.index)
        if success:
            await interaction.response.send_message("🗑 Memory deleted", ephemeral=True)
            await self.browser.refresh_embed(interaction) 
        else:
            await interaction.response.send_message("❌ Failed to delete", ephemeral=True)

class MemoryEditModal(discord.ui.Modal):
    def __init__(self, user_id, browser_view, mode="add", index=None, current_text=""):
        self.user_id = user_id
        self.browser = browser_view
        self.mode = mode
        self.index = index
        
        title = "New Memory" if mode == "add" else "Edit Memory"
        super().__init__(title=title)
        
        self.text_input = discord.ui.TextInput(
            label="Memory Content", 
            style=discord.TextStyle.paragraph, 
            placeholder="User likes apples...", 
            default=current_text,
            max_length=1000,
            required=True
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction):
        text = self.text_input.value
        if self.mode == "add":
            memory_manager.add_memory_manual(self.user_id, text)
            msg = "✅ Memory added."
        else:
            memory_manager.edit_memory(self.user_id, self.index, text)
            msg = "✅ Memory updated."
            
        await interaction.response.send_message(msg, ephemeral=True)
        await self.browser.refresh_embed(interaction)

# ───────────────────────────────
# MEMORY CONFIGURATION
# ───────────────────────────────

class MemoryConfigView(discord.ui.View):
    def __init__(self, user_id, bot, browser_view):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bot = bot
        self.browser = browser_view

    async def refresh_embed(self, interaction: discord.Interaction):
        params = await get_user_ai_params(self.user_id)
        
        enabled = params.get("memory_enabled", True)
        freq = params.get("memory_frequency", 10)
        prob = params.get("memory_probability", 0.35)
        
        desc = "**Memory Settings**\n\n"
        desc += f"**Status:** {'🟢 Enabled' if enabled else '🔴 Disabled'}\n"
        desc += f"**Frequency:** Every {freq} minutes\n"
        desc += f"**Relevance (Probability):** {prob}\n\n"
        desc += "Use buttons below to change."
        
        embed = discord.Embed(title="⚙️ Memory Configuration", description=desc, color=discord.Color.teal())
        
        self.clear_items()
        
        tog_style = discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success
        tog_lbl = "Disable" if enabled else "Enable"
        
        toggle_btn = discord.ui.Button(label=tog_lbl, style=tog_style, row=0)
        toggle_btn.callback = self.toggle_callback
        self.add_item(toggle_btn)
        
        freq_btn = discord.ui.Button(label="Set Frequency", style=discord.ButtonStyle.primary, emoji="⏱", row=0)
        freq_btn.callback = self.freq_callback
        self.add_item(freq_btn)
        
        prob_btn = discord.ui.Button(label="Set Relevance", style=discord.ButtonStyle.primary, emoji="🎯", row=0)
        prob_btn.callback = self.prob_callback
        self.add_item(prob_btn)
        
        back_btn = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, emoji="↩", row=1)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def toggle_callback(self, interaction: discord.Interaction):
        params = await get_user_ai_params(self.user_id)
        curr = params.get("memory_enabled", True)
        await set_user_ai_param(self.user_id, "memory_enabled", not curr)
        await self.refresh_embed(interaction)

    async def freq_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MemoryParamModal(self.user_id, self, "frequency"))

    async def prob_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MemoryParamModal(self.user_id, self, "probability"))

    async def back_callback(self, interaction: discord.Interaction):
        await self.browser.refresh_embed(interaction)

class MemoryParamModal(discord.ui.Modal):
    def __init__(self, user_id, config_view, param_type):
        self.user_id = user_id
        self.view_obj = config_view
        self.param_type = param_type
        
        title = "Memory Frequency" if param_type == "frequency" else "Memory Relevance"
        super().__init__(title=title)
        
        if param_type == "frequency":
            self.inp = discord.ui.TextInput(label="Minutes (1-60)", placeholder="10", default="10", max_length=2)
        else:
            self.inp = discord.ui.TextInput(label="Threshold (0.1 - 0.95)", placeholder="0.35", default="0.35", max_length=4)
        
        self.add_item(self.inp)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = float(self.inp.value)
            if self.param_type == "frequency":
                val = int(val)
                if val < 1 or val > 60: raise ValueError
                await set_user_ai_param(self.user_id, "memory_frequency", val)
            else:
                if val < 0.1 or val > 0.95: raise ValueError
                await set_user_ai_param(self.user_id, "memory_probability", val)
            
            await self.view_obj.refresh_embed(interaction)
        except ValueError:
            await interaction.response.send_message("❌ Invalid value. Frequency: 1-60, Relevance: 0.1-0.95", ephemeral=True)

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
             # We can't access parent view easily to call update, so we create a new one
             # But we need data first
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
        
        # Build components immediately with provided data
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
        
        # Init with passed params to avoid async calls in __init__
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
        
        # We should also rebuild selects to reflect changes, but for simplicity here we just edit embed.
        # Ideally: self.clear_items(), re-add Selects with new defaults, then edit view.
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def numeric_callback(self, interaction: discord.Interaction):
        # Pass current values to Modal
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