import discord
from discord.ext import commands
import re
import time
from core.database import db

DANK_MEMER_ID = 270904126974590976

NAME_STRATEGY2_REGEX = re.compile(r"(?:\*\*Name\*\*|Name:?)\s*\n+([^\n]+)", re.IGNORECASE)
INTER_STRATEGY2_REGEX = re.compile(r"(?:\*\*Interactions\*\*|Interactions:?)\s*\n+[^\d]*(\d+)", re.IGNORECASE)
BUTTON_MATCH_REGEX = re.compile(r"adventure again in (\d+)\s*(second|sec|minute|min|hour|hr)s?", re.IGNORECASE)

ADVENTURE_COOLDOWNS = {
    "Pepe goes to Space!": 60,
    "Pepe goes out West": 60,
    "Pepe goes to Brazil!": 30,
    "Pepe goes on Vacation!": 30,
    "Pepe goes to the Museum!": 30,
    "Pepe goes down under": 120
}

def extract_text_from_components(components) -> str:
    if not components:
        return ""
    text_parts = []
    for comp in components:
        if hasattr(comp, 'content') and comp.content:
            text_parts.append(str(comp.content))
        elif hasattr(comp, 'label') and comp.label:
            text_parts.append(str(comp.label))
        elif hasattr(comp, 'to_dict'):
            try:
                d = comp.to_dict()
                if 'content' in d and d['content']:
                    text_parts.append(str(d['content']))
                elif 'label' in d and d['label']:
                    text_parts.append(str(d['label']))
            except Exception:
                pass
                
        if hasattr(comp, 'children') and comp.children:
            text_parts.append(extract_text_from_components(comp.children))
    return " ".join(text_parts)

class ToggleAdventureButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Toggle Adventure Reminder", style=discord.ButtonStyle.primary, custom_id="toggle_adventure_reminder_btn")
        
    async def callback(self, interaction: discord.Interaction):
        settings_cog = interaction.client.get_cog("Settings")
        if not settings_cog:
            await interaction.response.send_message("Settings cog not found.", ephemeral=True)
            return
            
        user_id_str = str(interaction.user.id)
        current_settings = settings_cog.get_user_settings(user_id_str)
        is_enabled = current_settings.get("adv_reminder", False)
        
        new_val = not is_enabled
        current_settings["adv_reminder"] = new_val
        settings_cog.save_user_settings(user_id_str, current_settings)
        
        status = "enabled" if new_val else "disabled"
        await interaction.response.send_message(f"Your adventure reminder has been **{status}**.", ephemeral=True)

from cogs.reminder_views import UnifiedReminderView

class AdventureReminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.processed_messages = set()
        self.message_user_cache = {}

    def is_reminder_enabled(self, user_id: str, setting_key: str) -> bool:
        settings_cog = self.bot.get_cog("Settings")
        if not settings_cog:
            return False
        return settings_cog.get_user_settings(user_id).get(setting_key, False)

    def calculate_adventure_cooldown(self, adventure_name: str, interactions: int, user_id: str, button_cooldown_seconds: int = None) -> int:
        base_cooldown = ADVENTURE_COOLDOWNS.get(adventure_name, 30)
        calculated_cooldown = base_cooldown * interactions
        
        modifier = 1.0
        if time.gmtime().tm_wday == 5:
            modifier *= 0.5
            
        zombie_hand_active = False
        if zombie_hand_active:
            modifier *= 0.5
            
        final_calculated = int(calculated_cooldown * modifier)
        
        final_cooldown = final_calculated
        if button_cooldown_seconds is not None:
            if abs(button_cooldown_seconds - final_calculated) > 60:
                final_cooldown = max(1, calculated_cooldown)
                
        return final_cooldown

    @commands.Cog.listener("on_reminder_due")
    async def on_reminder_due(self, reminder_data: dict):
        if reminder_data.get("reminder_type") != "adventure":
            return
            
        user_id = reminder_data.get("user_id")
        channel_id = reminder_data.get("channel_id")
        
        user = self.bot.get_user(user_id)
        if not user:
            try:
                user = await self.bot.fetch_user(user_id)
            except (discord.NotFound, discord.HTTPException):
                pass
                
        if user:
            try:
                text = f"<@{user_id}> Your adventure cooldown is over! You can now use </adventure:1011560371041095695> again."
                from cogs.reminder_views import SnoozeReminderButton
                view = UnifiedReminderView(
                    title="Adventure Reminder",
                    text=text,
                    buttons=[SnoozeReminderButton(user_id=user_id)]
                )
                
                if channel_id:
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        try:
                            channel = await self.bot.fetch_channel(channel_id)
                        except Exception:
                            pass
                            
                    if channel:
                        try:
                            await channel.send(view=view)
                        except discord.Forbidden:
                            pass
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id != DANK_MEMER_ID:
            return
        await self._process_dank_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.author.id != DANK_MEMER_ID:
            return
        await self._process_dank_message(after)

    async def _process_dank_message(self, message: discord.Message):
        user_id = None
        if getattr(message, 'interaction_metadata', None):
            user_id = str(message.interaction_metadata.user.id)
            if getattr(message.interaction_metadata, 'name', '') == 'adventure' or getattr(message.interaction_metadata, 'id', 0) == 1011560371041095695:
                pass
        elif message.reference and getattr(message.reference, 'resolved', None) and hasattr(message.reference.resolved, 'author'):
            user_id = str(message.reference.resolved.author.id)
            
        if not user_id and message.mentions:
            user_id = str(message.mentions[0].id)

        if not user_id:
            user_id = self.message_user_cache.get(message.id)

        if not user_id:
            return
            
        self.message_user_cache[message.id] = user_id
            
        content = message.content or ""
        if message.embeds:
            content += " " + str(message.embeds[0].description or "")
            content += " " + str(message.embeds[0].title or "")
            if message.embeds[0].author:
                content += " " + str(message.embeds[0].author.name or "")
            if message.embeds[0].footer:
                content += " " + str(message.embeds[0].footer.text or "")
            
        if message.components:
            content += " " + extract_text_from_components(message.components)
            
        content_lower = content.lower()
        
        # Require "Adventure Summary".
        if "adventure summary" not in content_lower:
            return
            
        # Extract name and interactions.
        adv_name = "unknown adventure"
        interactions = 1
        
        if message.embeds:
            for embed in message.embeds:
                desc = embed.description or ""
                
                # Extract from standard fields.
                for field in embed.fields:
                    fname = field.name.lower().strip('* :')
                    if fname == "name":
                        adv_name = field.value.strip()
                    elif fname == "interactions":
                        match = re.search(r"(\d+)", field.value)
                        if match:
                            interactions = int(match.group(1))
                            
                # Extract from description text.
                if adv_name == "unknown adventure":
                    name_match = NAME_STRATEGY2_REGEX.search(desc)
                    if name_match:
                        adv_name = name_match.group(1).strip()
                        
                    inter_match = INTER_STRATEGY2_REGEX.search(desc)
                    if inter_match:
                        interactions = int(inter_match.group(1))
                        
                # Extract from table format.
                if adv_name == "unknown adventure":
                    if "Name" in desc and "Interactions" in desc:
                        lines = desc.split('\n')
                        for i, line in enumerate(lines):
                            if "Name" in line and "Interactions" in line:
                                if i + 1 < len(lines):
                                    values_line = lines[i+1]
                                    cols = re.split(r'\s{2,}', values_line.strip())
                                    if len(cols) >= 2:
                                        adv_name = cols[0].strip()
                                        match = re.search(r"(\d+)", cols[1])
                                        if match:
                                            interactions = int(match.group(1))
                                    break
                                    
        # Extract cooldown.
        button_cd = None
        button_match = BUTTON_MATCH_REGEX.search(content)
        if button_match:
            amt = int(button_match.group(1))
            unit = button_match.group(2).lower()
            if unit.startswith("hour") or unit.startswith("hr"): amt *= 3600
            elif unit.startswith("min"): amt *= 60
            button_cd = amt
            
        if self.is_reminder_enabled(user_id, "adv_reminder"):
            if message.id in self.processed_messages:
                return
            self.processed_messages.add(message.id)
            
            final_cooldown = self.calculate_adventure_cooldown(adv_name, interactions, user_id, button_cd)
            timestamp = int(time.time()) + final_cooldown
            
            res = await db.add_reminder_or_update(int(user_id), message.channel.id, "adventure", timestamp)
            if res > 0:
                view = UnifiedReminderView(title="Adventure Reminder", text=f"I will remind you to adventure again <t:{timestamp}:R>.", buttons=[ToggleAdventureButton()])
                await message.reply(view=view)
            return

async def setup(bot):
    await bot.add_cog(AdventureReminders(bot))
