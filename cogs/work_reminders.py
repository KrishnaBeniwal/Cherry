import discord
from discord.ext import commands
import re
import time
from core.database import db

DANK_MEMER_ID = 270904126974590976

WORK_ERROR_REGEX = re.compile(r"you can work again at.*?\b(\d+)\s*(second|minute|hour|day)s?\b", re.IGNORECASE)
T_ERROR_REGEX = re.compile(r"you can work again at.*?<t:(\d+):", re.IGNORECASE)

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

JOB_COOLDOWNS = {
    "babysitter": 2400,
    "discord mod": 2400,
    "fast food cook": 2580,
    "house wife": 2580,
    "twitch streamer": 2760,
    "youtuber": 2760,
    "grave digger": 2940,
    "professional fisherman": 2940,
    "professional hunter": 2940,
    "bartender": 2940,
    "robber": 2940,
    "police officer": 2940,
    "teacher": 2940,
    "musician": 2940,
    "pro gamer": 3120,
    "manager": 3120,
    "developer": 3120,
    "day trader": 3300,
    "santa claus": 3300,
    "politician": 3300,
    "veterinarian": 3300,
    "pharmacist": 3300,
    "dank memer shopkeeper": 3300,
    "lawyer": 3480,
    "doctor": 3480,
    "scientist": 3480,
    "adventurer": 3480,
    "ghost": 3480
}

JOB_MIN_SHIFTS = {
    "babysitter": 0,
    "discord mod": 0,
    "fast food cook": 1,
    "house wife": 1,
    "twitch streamer": 2,
    "youtuber": 2,
    "grave digger": 3,
    "professional fisherman": 3,
    "professional hunter": 3,
    "bartender": 3,
    "robber": 3,
    "police officer": 3,
    "teacher": 3,
    "musician": 4,
    "pro gamer": 4,
    "manager": 4,
    "developer": 4,
    "day trader": 5,
    "santa claus": 5,
    "politician": 5,
    "veterinarian": 5,
    "pharmacist": 5,
    "dank memer shopkeeper": 5,
    "lawyer": 6,
    "doctor": 6,
    "scientist": 6,
    "adventurer": 6,
}

class ToggleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Toggle Work Reminder", style=discord.ButtonStyle.primary, custom_id="toggle_work_reminder_btn")
        
    async def callback(self, interaction: discord.Interaction):
        settings_cog = interaction.client.get_cog("Settings")
        if not settings_cog:
            await interaction.response.send_message("Settings cog not found.", ephemeral=True)
            return
            
        user_id_str = str(interaction.user.id)
        current_settings = settings_cog.get_user_settings(user_id_str)
        is_enabled = current_settings.get("work_reminder", False)
        
        # Toggle setting.
        new_val = not is_enabled
        current_settings["work_reminder"] = new_val
        settings_cog.save_user_settings(user_id_str, current_settings)
        
        status = "enabled" if new_val else "disabled"
        await interaction.response.send_message(f"Your work reminder has been **{status}**.", ephemeral=True)

from cogs.reminder_views import UnifiedReminderView

class WorkReminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.processed_messages = set()
        self.message_user_cache = {}

    def increment_daily_shifts(self, user_id: str) -> int:
        settings_cog = self.bot.get_cog("Settings")
        if not settings_cog:
            return 1
            
        settings = settings_cog.get_user_settings(user_id)
        current_date = time.strftime("%Y-%m-%d", time.gmtime())
        saved_date = settings.get("work_shifts_date")
        
        if saved_date != current_date:
            settings["work_shifts_today"] = 1
            settings["work_shifts_date"] = current_date
        else:
            settings["work_shifts_today"] = settings.get("work_shifts_today", 0) + 1
            
        settings_cog.save_user_settings(user_id, settings)
        return settings["work_shifts_today"]

    def get_daily_shifts(self, user_id: str) -> int:
        settings_cog = self.bot.get_cog("Settings")
        if not settings_cog:
            return 0
            
        settings = settings_cog.get_user_settings(user_id)
        current_date = time.strftime("%Y-%m-%d", time.gmtime())
        saved_date = settings.get("work_shifts_date")
        
        if saved_date != current_date:
            return 0
        return settings.get("work_shifts_today", 0)

    @commands.Cog.listener("on_reminder_due")
    async def on_reminder_due(self, reminder_data: dict):
        if reminder_data.get("reminder_type") != "work_shift":
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
                text = f"<@{user_id}> You can now use </work shift:1011560371267579942> again."
                from cogs.reminder_views import SnoozeReminderButton
                view = UnifiedReminderView(
                    title="Work Reminder",
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

    def is_reminder_enabled(self, user_id: str, setting_key: str) -> bool:
        settings_cog = self.bot.get_cog("Settings")
        if not settings_cog:
            return False
        return settings_cog.get_user_settings(user_id).get(setting_key, False)

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
        elif message.reference and getattr(message.reference, 'resolved', None) and hasattr(message.reference.resolved, 'author'):
            user_id = str(message.reference.resolved.author.id)
            
        if not user_id and message.mentions:
            user_id = str(message.mentions[0].id)

        if not user_id:
            user_id = self.message_user_cache.get(message.id)

        if not user_id:
            return
            
        self.message_user_cache[message.id] = user_id
            
        is_enabled = self.is_reminder_enabled(user_id, "work_reminder")
            
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
        
        # Check for work cooldown error.
        work_error_match = WORK_ERROR_REGEX.search(content)
        t_error_match = T_ERROR_REGEX.search(content)
        
        timestamp = None
        match_str = ""
        
        if work_error_match:
            amt = int(work_error_match.group(1))
            unit = work_error_match.group(2).lower()
            mult = 1
            if unit.startswith("minute"): mult = 60
            elif unit.startswith("hour"): mult = 3600
            elif unit.startswith("day"): mult = 86400
            timestamp = int(time.time()) + (amt * mult)
            match_str = work_error_match.group(0)
        elif t_error_match:
            timestamp = int(t_error_match.group(1))
            match_str = t_error_match.group(0)

        if timestamp and self.is_reminder_enabled(user_id, "work_reminder"):
            if message.id in self.processed_messages:
                return
            self.processed_messages.add(message.id)
            
            res = await db.add_reminder_or_update(int(user_id), message.channel.id, "work_shift", timestamp)
            if res > 0:
                view = UnifiedReminderView(title="Work Reminder", text=f"I will remind you to work again <t:{timestamp}:R>.", buttons=[ToggleButton()])
                await message.reply(view=view)
            return

        # Check for work shift result.
        content_lower = content.lower()
        
        is_great_work = "great work" in content_lower
        is_terrible_work = "terrible work" in content_lower
        
        if is_great_work or is_terrible_work:
            if self.is_reminder_enabled(user_id, "work_reminder"):
                job_name_found = "unknown job"
                # Exact match.
                for job_name in JOB_COOLDOWNS.keys():
                    if f"working as a {job_name}" in content_lower or f"working as an {job_name}" in content_lower:
                        job_name_found = job_name
                        break
                
                # Fallback match.
                if job_name_found == "unknown job":
                    for job_name in JOB_COOLDOWNS.keys():
                        if job_name in content_lower:
                            job_name_found = job_name
                            break
                            
                # Process if job found.
                if job_name_found != "unknown job":
                    if message.id in self.processed_messages:
                        return
                    self.processed_messages.add(message.id)
                        
                    if is_great_work:
                        shifts_done = self.increment_daily_shifts(user_id)
                    else:
                        shifts_done = self.get_daily_shifts(user_id)
                        
                    shifts_required = JOB_MIN_SHIFTS.get(job_name_found, 0)
                    base_cooldown = JOB_COOLDOWNS.get(job_name_found, 3600)
                    
                    # Calculate modifiers.
                    modifier = 1.0
                    if time.gmtime().tm_wday == 4:
                        modifier *= 0.5
                        
                    final_cooldown = int(base_cooldown * modifier)
                    timestamp = int(time.time()) + final_cooldown
                        
                    await db.add_reminder(int(user_id), message.channel.id, "work_shift", timestamp)
                    view = UnifiedReminderView(title="Work Reminder", text=f"I will remind you to work again <t:{timestamp}:R>.\n\nYou've completed `{shifts_done}/{shifts_required}` shifts as a {job_name_found.title()} today.", buttons=[ToggleButton()])
                    await message.reply(view=view)
                    return

async def setup(bot):
    await bot.add_cog(WorkReminders(bot))
