# Urch/commands/pit.py
import random

import discord
from discord import app_commands
from discord.ext import commands

from systems.core.database import db
from systems.game.raritylist import RARITIES
from systems.game.upgrades.luck_upgrades import (
    calculate_pit_luck_gain,
    get_pit_luck_multiplier,
)
from systems.game.utils import (
    RARITY_ID_TO_NAME,
    RARITY_INDEX_MAP,
    ensure_user,
    format_number,
    get_user_data,
    save_user_data,
)

RARITY_NAME_TO_ID: dict[str, str] = {r[0]: r[2] for r in RARITIES}
RARITY_NAME_TO_ONE_IN: dict[str, float] = {
    r[0]: (1.0 / r[1]) if r[1] > 0 else 0.0 for r in RARITIES
}
RARITY_ID_TO_ONE_IN: dict[str, float] = {r[2]: (1.0 / r[1]) if r[1] > 0 else 0.0 for r in RARITIES}

PIT_SACRIFICE_EFFICIENCY: float = 0.75

QUANTITY_MODES = [
    ("keep_one", "🛡️ Mode: Keep 1"),
    ("all", "💥 Mode: All"),
    ("half", "⚖️ Mode: Half"),
]


def calculate_sacrifice_qty(owned: int, mode: str) -> int:
    """Calculates how many copies of a rarity to sacrifice for the given mode."""
    if owned <= 0:
        return 0
    if mode == "keep_one":
        return max(0, owned - 1)
    if mode == "half":
        return max(1, owned // 2) if owned >= 1 else 0
    # "all"
    return owned


UNIQUE_TIER_VALUES: list[float] = sorted(
    list(set(round((1.0 / r[1]), 4) for r in RARITIES if r[1] > 0))
)


def get_fusion_tax_multiplier(target_one_in: float, max_sac_one_in: float | None = None) -> float:
    """Calculates fusion tax multiplier when aiming for a target rarity tier.

    - Target <= max_sac_one_in: 1.0x (consolidating duplicates / filling gaps)
    - +1 tier above max_sac: 2.0x
    - +2 tiers above max_sac: 3.5x
    - +3 or more tiers above max_sac: 5.0x
    """
    if max_sac_one_in is None or max_sac_one_in <= 0:
        return 1.0
    if target_one_in <= max_sac_one_in * (1.0 + 1e-6):
        return 1.0

    target_rounded = round(target_one_in, 4)
    max_sac_rounded = round(max_sac_one_in, 4)
    step = 0
    for v in UNIQUE_TIER_VALUES:
        if v > max_sac_rounded and v <= target_rounded:
            step += 1

    if step <= 1:
        return 2.0
    elif step == 2:
        return 3.5
    else:
        return 5.0


def find_closest_rarity_for_value(
    total_value: float,
    max_sac_one_in: float | str | None = None,
    exclude_single_same: str | None = None,
) -> tuple[str, float, list[str]] | None:
    """Finds the highest rarity tier that can be forged from total_value,

    taking into account the fusion tax if forging tiers strictly higher than max_sac_one_in.
    Returns (chosen_rarity_name, tier_one_in, all_tied_names_at_tier).
    """
    if isinstance(max_sac_one_in, str):
        exclude_single_same = max_sac_one_in
        max_sac_one_in = None

    if total_value < 2.0 - 1e-9:
        return None

    limit = total_value * (1.0 + 1e-9)
    best_idx = -1
    best_one_in = 0.0

    for idx, (_name, prob, _rid) in enumerate(RARITIES):
        one_in = (1.0 / prob) if prob > 0 else 0.0
        tax = get_fusion_tax_multiplier(one_in, max_sac_one_in)
        required_value = one_in * tax
        if required_value <= limit:
            if one_in >= best_one_in:
                best_idx = idx
                best_one_in = one_in

    if best_idx < 0:
        return None

    # Collect all rarities that share virtually the exact same 1-in-X value
    tied_names = [
        r[0]
        for r in RARITIES
        if r[1] > 0 and abs((1.0 / r[1]) - best_one_in) / max(1.0, best_one_in) < 1e-6
    ]
    if not tied_names:
        tied_names = [RARITIES[best_idx][0]]

    # If the user sacrificed only 1 type of rarity and hit a tied tier containing it,
    # prefer another rarity in that tied tier if available
    candidates = (
        [n for n in tied_names if n != exclude_single_same]
        if exclude_single_same and len(tied_names) > 1
        else tied_names
    )
    chosen = random.choice(candidates)
    return chosen, best_one_in, tied_names


def _clean_label(text: str, max_len: int = 100) -> str:
    clean = text.replace("**", "").replace("*", "").replace("~~", "").replace("``", "")
    if len(clean) > max_len:
        return clean[: max_len - 1] + "…"
    return clean


class PitRaritySelect(discord.ui.Select):
    def __init__(self, pit_view: "PitView", page_items: list[tuple[str, int]]):
        self.pit_view = pit_view
        options: list[discord.SelectOption] = []

        for rarity_name, count in page_items[:25]:
            rid = RARITY_NAME_TO_ID.get(rarity_name, rarity_name)
            sac_qty = calculate_sacrifice_qty(count, pit_view.qty_mode)
            one_in = RARITY_NAME_TO_ONE_IN.get(rarity_name, 2.0)
            val_Contribution = sac_qty * one_in * PIT_SACRIFICE_EFFICIENCY

            label = _clean_label(f"{rarity_name} (x{count:,})", 100)
            if sac_qty > 0:
                desc = f"Throw x{sac_qty:,} -> +{format_number(val_Contribution)} value"
            else:
                desc = "Protected by 'Keep 1' mode (only 1 owned)"

            options.append(
                discord.SelectOption(
                    label=label,
                    value=rid,
                    description=_clean_label(desc, 100),
                    default=(rid in pit_view.selected_ids),
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No eligible rarities on this page",
                    value="__none__",
                    description="Try switching pages or changing mode",
                )
            )
            super().__init__(
                placeholder="No rarities available to select...",
                min_values=1,
                max_values=1,
                options=options,
                disabled=True,
                row=0,
            )
        else:
            super().__init__(
                placeholder="Select rarities...",
                min_values=0,
                max_values=len(options),
                options=options,
                row=0,
            )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.pit_view.user_id:
            return await interaction.response.send_message("This isn't your menu.", ephemeral=True)

        # Update selected_ids for items on the current page while preserving other pages
        page_rids = {
            RARITY_NAME_TO_ID.get(r_name, r_name)
            for r_name, _ in self.pit_view.current_page_items()
        }
        self.pit_view.selected_ids -= page_rids
        for val in self.values:
            if val != "__none__":
                self.pit_view.selected_ids.add(val)

        self.pit_view.last_result_banner = None
        self.pit_view.rebuild_components()
        await interaction.response.edit_message(
            embed=self.pit_view.format_embed(), view=self.pit_view
        )


class PitView(discord.ui.View):
    def __init__(
        self,
        user_id: str,
        inventory: dict[str, int],
        bot=None,
        pit_tier: int = 0,
        pit_luck: float = 0.0,
    ):
        super().__init__(timeout=240)
        self.user_id = str(user_id)
        self.inventory: dict[str, int] = dict(inventory)
        self.bot = bot
        self.pit_tier = int(pit_tier)
        self.pit_luck = float(pit_luck)

        self.qty_mode_idx = 0  # Default: "keep_one"
        self.sort_ascending = True  # Default: Lowest rarity first (easiest to dump junk)
        self.page = 0
        self.items_per_page = 25
        self.selected_ids: set[str] = set()
        self.last_result_banner: str | None = None

        self.rebuild_components()

    @property
    def qty_mode(self) -> str:
        return QUANTITY_MODES[self.qty_mode_idx][0]

    @property
    def qty_mode_label(self) -> str:
        return QUANTITY_MODES[self.qty_mode_idx][1]

    def sorted_inventory_items(self) -> list[tuple[str, int]]:
        valid = [
            (r_name, count)
            for r_name, count in self.inventory.items()
            if count > 0 and r_name in RARITY_INDEX_MAP
        ]
        valid.sort(
            key=lambda kv: RARITY_INDEX_MAP.get(kv[0], -1),
            reverse=not self.sort_ascending,
        )
        return valid

    @property
    def total_pages(self) -> int:
        items = self.sorted_inventory_items()
        return max(1, (len(items) + self.items_per_page - 1) // self.items_per_page)

    def current_page_items(self) -> list[tuple[str, int]]:
        items = self.sorted_inventory_items()
        self.page = max(0, min(self.page, self.total_pages - 1))
        start = self.page * self.items_per_page
        return items[start : start + self.items_per_page]

    def compute_sacrifice_plan(self) -> tuple[list[tuple[str, int, float]], float]:
        """
        Returns (list of (rarity_name, sac_qty, subtotal_value), combined_total_value)
        for all currently selected rarities.
        """
        plan: list[tuple[str, int, float]] = []
        total_value = 0.0

        # Order selected items by rarity index
        selected_names = [
            RARITY_ID_TO_NAME[rid]
            for rid in self.selected_ids
            if rid in RARITY_ID_TO_NAME and self.inventory.get(RARITY_ID_TO_NAME[rid], 0) > 0
        ]
        selected_names.sort(key=lambda n: RARITY_INDEX_MAP.get(n, -1), reverse=True)

        for r_name in selected_names:
            owned = self.inventory.get(r_name, 0)
            sac_qty = calculate_sacrifice_qty(owned, self.qty_mode)
            if sac_qty <= 0:
                continue
            one_in = RARITY_NAME_TO_ONE_IN.get(r_name, 2.0)
            sub_val = sac_qty * one_in * PIT_SACRIFICE_EFFICIENCY
            plan.append((r_name, sac_qty, sub_val))
            total_value += sub_val

        return plan, total_value

    def rebuild_components(self):
        self.clear_items()
        page_items = self.current_page_items()

        # Row 0: Multi-select dropdown
        self.add_item(PitRaritySelect(self, page_items))

        # Row 1: Pagination & Sort
        prev_btn = discord.ui.Button(
            label="⬅️ Prev",
            style=discord.ButtonStyle.secondary,
            disabled=(self.total_pages <= 1),
            row=1,
        )
        prev_btn.callback = self.on_prev_page
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(
            label="➡️ Next",
            style=discord.ButtonStyle.secondary,
            disabled=(self.total_pages <= 1),
            row=1,
        )
        next_btn.callback = self.on_next_page
        self.add_item(next_btn)

        sort_label = "🔽 Sort: Lowest First" if self.sort_ascending else "🔼 Sort: Highest First"
        sort_btn = discord.ui.Button(label=sort_label, style=discord.ButtonStyle.secondary, row=1)
        sort_btn.callback = self.on_toggle_sort
        self.add_item(sort_btn)

        # Row 2: Mode, Select Page, Clear
        mode_btn = discord.ui.Button(
            label=self.qty_mode_label, style=discord.ButtonStyle.primary, row=2
        )
        mode_btn.callback = self.on_cycle_mode
        self.add_item(mode_btn)

        sel_page_btn = discord.ui.Button(
            label="☑️ Select Page",
            style=discord.ButtonStyle.secondary,
            disabled=(len(page_items) == 0),
            row=2,
        )
        sel_page_btn.callback = self.on_select_page
        self.add_item(sel_page_btn)

        clear_btn = discord.ui.Button(
            label="🧹 Clear",
            style=discord.ButtonStyle.secondary,
            disabled=(len(self.selected_ids) == 0),
            row=2,
        )
        clear_btn.callback = self.on_clear_selection
        self.add_item(clear_btn)

        # Row 3: Confirm Sacrifice
        plan, total_val = self.compute_sacrifice_plan()
        can_sacrifice = len(plan) > 0 and total_val >= 2.0
        sac_btn = discord.ui.Button(
            label="🔥 Throw into The Pit",
            style=discord.ButtonStyle.danger if can_sacrifice else discord.ButtonStyle.secondary,
            disabled=not can_sacrifice,
            row=3,
        )
        sac_btn.callback = self.on_confirm_sacrifice
        self.add_item(sac_btn)

    def format_embed(self) -> discord.Embed:
        plan, total_val = self.compute_sacrifice_plan()
        total_sac_items = sum(q for _, q, _ in plan)

        desc_parts = []
        if self.last_result_banner:
            desc_parts.append(self.last_result_banner)

        desc_parts.append("Combine excess rarities to fuse into the closest matching rarity.")

        embed = discord.Embed(
            title="🕳️ The Pit",
            description="\n\n".join(desc_parts),
            color=discord.Color.dark_red() if plan else discord.Color.dark_purple(),
        )

        if plan:
            preview_lines = []
            for r_name, qty, sub_val in plan[:12]:
                preview_lines.append(f"• **x{qty:,}** {r_name} (`{format_number(sub_val)}`)")
            if len(plan) > 12:
                preview_lines.append(f"*...and {len(plan) - 12} more rarities*")
            embed.add_field(
                name=f"🔥 Selected to Throw ({total_sac_items:,} items across {len(plan)} rarities)",
                value="\n".join(preview_lines),
                inline=False,
            )

            max_sac_one_in = (
                max(RARITY_NAME_TO_ONE_IN.get(r_name, 2.0) for r_name, _, _ in plan)
                if plan
                else 0.0
            )
            match = find_closest_rarity_for_value(total_val, max_sac_one_in=max_sac_one_in)
            if match:
                chosen_name, tier_one_in, tied_names = match
                if len(tied_names) > 1:
                    outcome_text = (
                        f"🎯 **1 of {len(tied_names)} tied rarities** at `1 in {format_number(tier_one_in)}`:\n"
                        + ", ".join(tied_names[:4])
                    )
                else:
                    outcome_text = f"✨ **{chosen_name}**"
            else:
                outcome_text = "⚠️ Value too low"

            embed.add_field(
                name="⚡ Combined Value",
                value=f"**1 in {format_number(total_val)}**",
                inline=True,
            )
            embed.add_field(
                name="🎁 Reward",
                value=outcome_text,
                inline=True,
            )
            if self.pit_tier >= 1:
                luck_gain = calculate_pit_luck_gain(total_val, self.pit_tier)
                embed.add_field(
                    name="🍀 Pit Luck",
                    value=f"**+{format_number(luck_gain)}**",
                    inline=True,
                )
        else:
            if self.selected_ids and self.qty_mode == "keep_one":
                embed.add_field(
                    name="ℹ️ No Excess Copies",
                    value="You only own **1 copy** of the selected rarity with **Keep 1** mode active.",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="🕳️",
                    value="No rarities selected to sacrifice.",
                    inline=False,
                )

        footer_text = f"Page {self.page + 1}/{self.total_pages} • {self.qty_mode_label} • Selected types: {len(self.selected_ids)}"
        if self.pit_tier >= 1:
            mult = get_pit_luck_multiplier(self.pit_tier)
            footer_text += f" • Pit Luck: T{self.pit_tier} ({format_number(mult)}x)"
        embed.set_footer(text=footer_text)
        return embed

    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True

    async def on_prev_page(self, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        self.page = (self.page - 1) % self.total_pages
        self.rebuild_components()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    async def on_next_page(self, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        self.page = (self.page + 1) % self.total_pages
        self.rebuild_components()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    async def on_toggle_sort(self, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        self.sort_ascending = not self.sort_ascending
        self.page = 0
        self.rebuild_components()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    async def on_cycle_mode(self, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        self.qty_mode_idx = (self.qty_mode_idx + 1) % len(QUANTITY_MODES)
        self.last_result_banner = None
        self.rebuild_components()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    async def on_select_page(self, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        for r_name, _ in self.current_page_items():
            rid = RARITY_NAME_TO_ID.get(r_name, r_name)
            self.selected_ids.add(rid)
        self.last_result_banner = None
        self.rebuild_components()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    async def on_clear_selection(self, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        self.selected_ids.clear()
        self.last_result_banner = None
        self.rebuild_components()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    async def on_confirm_sacrifice(self, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return

        async with db.lock_user(self.user_id):
            user = await ensure_user(self.user_id)
            live_inv = user.setdefault("inventory", {})
            discovered = user.setdefault("discovered", {})

            # Recompute against live DB inventory to prevent any race condition
            actual_deductions: dict[str, int] = {}
            total_value = 0.0

            for rid in list(self.selected_ids):
                r_name = RARITY_ID_TO_NAME.get(rid)
                if not r_name:
                    continue
                owned = int(live_inv.get(r_name, 0))
                sac_qty = calculate_sacrifice_qty(owned, self.qty_mode)
                if sac_qty <= 0:
                    continue
                actual_deductions[r_name] = sac_qty
                total_value += (
                    sac_qty * RARITY_NAME_TO_ONE_IN.get(r_name, 2.0) * PIT_SACRIFICE_EFFICIENCY
                )

            if not actual_deductions or total_value < 2.0 - 1e-9:
                self.inventory = dict(live_inv)
                self.selected_ids.clear()
                self.rebuild_components()
                return await interaction.response.send_message(
                    "❌ You no longer have enough eligible items to sacrifice.", ephemeral=True
                )

            max_sac_one_in = (
                max(RARITY_NAME_TO_ONE_IN.get(r_name, 2.0) for r_name in actual_deductions.keys())
                if actual_deductions
                else 0.0
            )
            single_sac_name = (
                next(iter(actual_deductions.keys())) if len(actual_deductions) == 1 else None
            )
            match = find_closest_rarity_for_value(
                total_value,
                max_sac_one_in=max_sac_one_in,
                exclude_single_same=single_sac_name,
            )
            if not match:
                return await interaction.response.send_message(
                    "❌ Combined rarity value is too low to fuse.", ephemeral=True
                )

            pit_tier = int(((user.get("upgrades") or {}).get("luck") or {}).get("pit_luck", 0))
            self.pit_tier = pit_tier

            luck_gained = 0.0
            if pit_tier >= 1:
                luck_gained = calculate_pit_luck_gain(total_value, pit_tier)

            forged_rarity, _tier_one_in, _tied = match
            total_sacrificed_count = sum(actual_deductions.values())

            async with db.transaction():
                for r_name, qty in actual_deductions.items():
                    live_inv[r_name] = live_inv.get(r_name, 0) - qty
                    if live_inv[r_name] <= 0:
                        live_inv.pop(r_name, None)

                live_inv[forged_rarity] = live_inv.get(forged_rarity, 0) + 1
                discovered[forged_rarity] = True

                # Update highscore if forged rarity beats current highscore
                current_high = user.get("highscore")
                cur_idx = RARITY_INDEX_MAP.get(current_high, -1) if current_high else -1
                new_idx = RARITY_INDEX_MAP.get(forged_rarity, -1)
                if new_idx > cur_idx:
                    user["highscore"] = forged_rarity

                if luck_gained > 0.0:
                    new_pit_luck = round(float(user.get("pit_luck", 0.0)) + luck_gained, 4)
                    user["pit_luck"] = new_pit_luck
                    self.pit_luck = new_pit_luck

                await save_user_data(self.user_id, user)

            self.inventory = dict(live_inv)
            self.selected_ids.clear()
            banner_lines = [
                "🌋 **PITTED**",
                f"You sacrificed **{total_sacrificed_count:,}x** rarities "
                f"(Combined Value: `1 in {format_number(total_value)}`) and forged:\n"
                f"✨ **{forged_rarity}** ✨",
            ]
            if luck_gained > 0.0:
                banner_lines.append(
                    f"🍀 **+{format_number(luck_gained)}** Pit Luck (Total: `{format_number(self.pit_luck)}`)"
                )
            self.last_result_banner = "\n".join(banner_lines)
            self.rebuild_components()

        await interaction.response.edit_message(embed=self.format_embed(), view=self)


class PitCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="pit",
        description="Fuse excess rarities in The Pit into higher tiers",
    )
    async def pit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user = await get_user_data(user_id)
        inventory = (user or {}).get("inventory") or {}
        luck_upgs = ((user or {}).get("upgrades") or {}).get("luck") or {}
        pit_tier = int(luck_upgs.get("pit_luck", 0))
        pit_luck = float((user or {}).get("pit_luck", 0.0))

        valid_items = {k: v for k, v in inventory.items() if v > 0 and k in RARITY_INDEX_MAP}
        if not valid_items:
            return await interaction.response.send_message(
                "🕳️ Your inventory is empty! Roll some rarities with `/roll` before visiting The Pit.",
                ephemeral=True,
            )

        view = PitView(
            user_id,
            valid_items,
            bot=self.bot,
            pit_tier=pit_tier,
            pit_luck=pit_luck,
        )
        embed = view.format_embed()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(PitCommand(bot))
