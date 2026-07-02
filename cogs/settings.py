import discord
from discord.ext import commands
from discord import app_commands
from emojis import TICK, CROSS, LEFT, RIGHT
from cogs.utils import settings_manager

ITEMS_LIST = [
    "daily box", "cowboy boots", "pizza slice", "crunchy taco", "zombie hand", 
    "energy drink", "inflated", "Prismatic Delight", "rusty machine", "adventure compass",
    "ammo", "Stolen Amulet", "apple", "beggars bowl", "d20", 
    "jokebook", "Peps's bath water", "Tentacled Temptation", "tip jar", "Lucky Horseshoe", 
    "Grub Pail"
]

ITEM_DURATIONS = {
    "daily_box": 600,                 # 10m
    "cowboy_boots": 3600,             # 1h
    "pizza_slice": 1800,              # 30m
    "crunchy_taco": 1800,             # 30m
    "zombie_hand": 43200,             # 12h
    "energy_drink": 21600,            # 6h
    "inflated": 900,                  # 15m
    "prismatic_delight": 600,         # 10m
    "rusty_machine": 3600,            # 1h
    "adventure_compass": 3600,        # 1h
    "ammo": 3600,                     # 1h
    "stolen_amulet": 3600,            # 1h
    "apple": 86400,                   # 1d
    "beggars_bowl": 86400,            # 1d
    "d20": 86400,                     # 1d
    "jokebook": 10800,                # 3h
    "pepss_bath_water": 259200,       # 3d
    "tentacled_temptation": 10800,    # 3h
    "tip_jar": 3600,                  # 1h
    "lucky_horseshoe": 900,           # 15m
    "grub_pail": 3600                 # 1h
}

def _chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# Generate item pages dynamically
ITEM_PAGES = []
for chunk in _chunk(ITEMS_LIST, 5):
    page_dict = {}
    for item in chunk:
        key = item.replace(" ", "_").replace("'", "").lower()
        page_dict[key] = {
            "label": item.title(),
            "short_label": item.title(),
            "description": f"Get reminded when your {item.title()} expires or is ready to use."
        }
    ITEM_PAGES.append(page_dict)

toggle_all_dict = {
    "toggle_all_items": {
        "label": "Toggle All Item Reminders",
        "short_label": "Toggle All",
        "description": "Turn all item reminders on or off at once."
    }
}
ITEM_PAGES[0] = {**toggle_all_dict, **ITEM_PAGES[0]}

SETTINGS_DATA = {
    "general": [
        # Page 0    
        {
            "work_reminder": {
                "label": "Work Shift Reminders",
                "short_label": "Work Shift",
                "description": "Get reminded when your work shift cooldown is over so you can use the </work shift:1011560371267579942> command again."
            },
            "adv_reminder": {
                "label": "Adventure Reminders",
                "short_label": "Adventure",
                "description": "Get reminded when your adventure is completed so you can use the </adventure:1011560371041095695> command again."
            },
            "travel_reminder": {
                "label": "Travel Reminders",
                "short_label": "Travel",
                "description": "Get reminded when your travel duration is completed for fishing locations."
            },
            "prestige_reminder": {
                "label": "Prestige Reminders",
                "short_label": "Prestige Rem.",
                "description": "Get reminded when your prestige cooldown is over and you are can prestige again."
            },
            "prestige_assistant": {
                "label": "Prestige Assistant",
                "short_label": "Prestige Asst.",
                "description": "Get calculations showing how many more coins and levels you need to prestige."
            }
        },
        # Page 1
        {
            "farm_reminder": {
                "label": "Farm Reminders",
                "short_label": "Farm Rem.",
                "description": "Get reminded when your crops are fully grown and ready to be harvested."
            },
            "pet_reminder": {
                "label": "Pet Care Reminders",
                "short_label": "Pet Care",
                "description": "Get reminded to feed, play and take care of your pets."
            },
            "giveaway_reminder": {
                "label": "Giveaway Creation Reminders",
                "short_label": "Giveaway Rem.",
                "description": "Get reminded when your global giveaway creation cooldown is over."
            },
            "npc_summon_reminder": {
                "label": "NPC Summon Reminders",
                "short_label": "NPC Summon",
                "description": "Get reminded when your npc summon cooldown is over."
            },
            "daily_reminder": {
                "label": "Daily Reminders",
                "short_label": "Daily Rem.",
                "description": "Get a reminder to run the </daily:1011560370864930856> command."
            }
        },
        # Page 2
        {
            "stream_reminder": {
                "label": "Stream Reminders",
                "short_label": "Stream Rem.",
                "description": "Get reminders for the </stream:1011560371267579938> command."
            },
            "scratch_reminder": {
                "label": "Scratch Reminders",
                "short_label": "Scratch",
                "description": "Get a reminder to run the </scratch:1011560371267579934> command (in DMs)."
            },
            "happy_hour_reminder": {
                "label": "Happy Hour Reminders",
                "short_label": "Happy Hour",
                "description": "Get a reminder for Happy Hour (in DMs)."
            },
            "fish_boost_reminder": {
                "label": "Fih Boosts Reminder",
                "short_label": "Fih Boosts",
                "description": "Get reminders to check new Fih boosts (in DMs)."
            },
            "omega_shop_reminder": {
                "label": "Omega Shop Reminder",
                "short_label": "Omega Shop",
                "description": "Get reminded when your omega shop cooldown is over (omega bait, instant craft and farm boosts)."
            }
        }
    ],
    "items": ITEM_PAGES
}

class SettingsToggle(discord.ui.Button):
    def __init__(self, key: str, is_on: bool):
        style = discord.ButtonStyle.green if is_on else discord.ButtonStyle.red
        status_text = "On" if is_on else "Off"
        super().__init__(style=style, label=status_text, custom_id=f"toggle_{key}")
        self.key = key

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Settings")
        if not cog:
            return

        owner_id = str(interaction.user.id)
        current = cog.get_user_settings(owner_id)
        
        if self.key == "toggle_all_items":
            new_state = not current.get("toggle_all_items", False)
            current["toggle_all_items"] = new_state
            for item in ITEMS_LIST:
                item_key = item.replace(" ", "_").replace("'", "").lower()
                current[item_key] = new_state
        elif self.key in ["npc_summon_reminder"]:
            current[self.key] = False
        else:
            current[self.key] = not current.get(self.key, False)
            
        cog.save_user_settings(owner_id, current)

        # Determine target page.
        target_cat = "general"
        target_page = 0
        for cat, pages in SETTINGS_DATA.items():
            for idx, page_dict in enumerate(pages):
                if self.key in page_dict:
                    target_cat = cat
                    target_page = idx
                    break

        new_view = cog.build_settings_view(owner_id, target_cat, target_page)
        await interaction.response.edit_message(view=new_view)
        
        if self.key == "pet_reminder" and current.get(self.key, False):
            note_view = discord.ui.LayoutView()
            note_c = discord.ui.Container()
            note_text = "### Note:\nYou must react with 💀 on a pet's care page to set it as your active pet.\n\nOnly your active pet will receive feeding reminders."
            note_c.add_item(discord.ui.TextDisplay(content=note_text))
            note_view.add_item(note_c)
            await interaction.followup.send(view=note_view, ephemeral=True)
            
        if self.key in ["npc_summon_reminder"]:
            note_view = discord.ui.LayoutView()
            note_c = discord.ui.Container()
            note_text = "### Coming Soon\nThis feature is currently under development."
            note_c.add_item(discord.ui.TextDisplay(content=note_text))
            note_view.add_item(note_c)
            await interaction.followup.send(view=note_view, ephemeral=True)

class SettingsCategorySelect(discord.ui.Select):
    def __init__(self, current_cat: str):
        options = [
            discord.SelectOption(label="General Settings", value="general", default=(current_cat == "general")),
            discord.SelectOption(label="Item Settings", value="items", default=(current_cat == "items"))
        ]
        super().__init__(custom_id="settings_category_select", options=options, placeholder="Select Settings Category")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Settings")
        if not cog:
            return

        owner_id = str(interaction.user.id)
        new_cat = self.values[0]
        
        # Reset to first page.
        new_view = cog.build_settings_view(owner_id, new_cat, 0)
        await interaction.response.edit_message(view=new_view)

class SettingsPageButton(discord.ui.Button):
    def __init__(self, direction: str, category: str, page: int, disabled: bool):
        emoji = LEFT if direction == "prev" else RIGHT
        # Use custom_id for stateless routing.
        super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji, custom_id=f"settings_nav_{category}_{page}", disabled=disabled)
        self.target_cat = category
        self.target_page = page

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Settings")
        if not cog:
            return
            
        owner_id = str(interaction.user.id)
        new_view = cog.build_settings_view(owner_id, self.target_cat, self.target_page)
        await interaction.response.edit_message(view=new_view)

class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_json_data(self) -> dict:
        return settings_manager.get_data()

    def _save_json_data(self, data: dict):
        settings_manager.set_data(data)

    def get_user_settings(self, user_id: str) -> dict:
        data = self._get_json_data()
        return data.get(user_id, {})

    def save_user_settings(self, user_id: str, user_data: dict):
        data = self._get_json_data()
        data[user_id] = user_data
        self._save_json_data(data)

    def get_persistent_views(self):
        """Builds multiple dummy views containing all possible buttons/dropdowns to register with Discord on startup, staying under the 25 component limit."""
        items_to_register = []
        
        # Register all toggle buttons.
        for cat, pages in SETTINGS_DATA.items():
            for page_dict in pages:
                for key in page_dict.keys():
                    items_to_register.append(SettingsToggle(key, False))
                    
        # Register category select.
        items_to_register.append(SettingsCategorySelect("general"))
        
        # Register navigation buttons.
        for cat, pages in SETTINGS_DATA.items():
            for i in range(len(pages)):
                items_to_register.append(SettingsPageButton("prev", cat, i, False))
                items_to_register.append(SettingsPageButton("next", cat, i, False))
                
        views = []
        view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container()
        current_row = discord.ui.ActionRow()
        rows_in_container = 0

        for item in items_to_register:
            # Start new row if full.
            if len(current_row.children) >= 5:
                container.add_item(current_row)
                rows_in_container += 1
                current_row = discord.ui.ActionRow()

            # Start new view if full.
            if rows_in_container >= 5:
                view.add_item(container)
                views.append(view)
                view = discord.ui.LayoutView(timeout=None)
                container = discord.ui.Container()
                rows_in_container = 0

            if isinstance(item, discord.ui.Select):
                # Dropdowns require dedicated rows.
                if len(current_row.children) > 0:
                    container.add_item(current_row)
                    rows_in_container += 1
                    current_row = discord.ui.ActionRow()
                    
                # Check container capacity.
                if rows_in_container >= 5:
                    view.add_item(container)
                    views.append(view)
                    view = discord.ui.LayoutView(timeout=None)
                    container = discord.ui.Container()
                    rows_in_container = 0

                # Add dropdown to container.
                current_row.add_item(item)
                container.add_item(current_row)
                rows_in_container += 1
                current_row = discord.ui.ActionRow()
            else:
                # Add normal button.
                current_row.add_item(item)

        # Push any remaining items.
        if len(current_row.children) > 0:
            container.add_item(current_row)
            
        if len(container.children) > 0:
            view.add_item(container)
            views.append(view)
            
        return views

    def build_settings_view(self, user_id: str, category: str, page: int):
        """Builds the dynamic LayoutView for the given user, category, and page"""
        settings = self.get_user_settings(user_id)
        page_settings = SETTINGS_DATA[category][page]
        total_pages = len(SETTINGS_DATA[category])
        
        view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container()
        
        container.add_item(discord.ui.TextDisplay(
            "**⚙️ User Settings**\nToggle your personal settings below. By default, all helper features are **Off**."
        ))
        
        container.add_item(discord.ui.Separator())
        
        for key, info in page_settings.items():
            is_on = settings.get(key, False)
            status_emoji = TICK if is_on else CROSS
            
            button = SettingsToggle(key, is_on)
            
            section = discord.ui.Section(
                f"{status_emoji} **{info['label']}**\n{info['description']}",
                accessory=button
            )
            container.add_item(section)
            container.add_item(discord.ui.Separator())
            
        # Add category selector.
        dropdown_row = discord.ui.ActionRow()
        dropdown_row.add_item(SettingsCategorySelect(category))
        container.add_item(dropdown_row)
        
        # Add pagination navigation.
        nav_row = discord.ui.ActionRow()
        nav_row.add_item(SettingsPageButton("prev", category, page - 1, disabled=(page == 0)))
        nav_row.add_item(SettingsPageButton("next", category, page + 1, disabled=(page == total_pages - 1)))
        container.add_item(nav_row)
        
        view.add_item(container)
        return view

    @commands.command(name="settings")
    async def settings_prefix(self, ctx: commands.Context):
        """Configure your personal reminder and assistant settings."""
        view = self.build_settings_view(str(ctx.author.id), "general", 0)
        await ctx.reply(view=view, mention_author=False)

    @app_commands.command(name="settings", description="Configure your personal reminder and assistant settings")
    async def settings_slash(self, interaction: discord.Interaction):
        view = self.build_settings_view(str(interaction.user.id), "general", 0)
        await interaction.response.send_message(view=view, ephemeral=False)

async def setup(bot):
    await bot.add_cog(Settings(bot))
