import discord
from discord.ext import commands
import re
import json
from core.database import db

DANK_MEMER_ID = 270904126974590976

LOCATION_MATCH_REGEX = re.compile(r"\**Traveling to:\**\s*\n+([^\n]+)", re.IGNORECASE)
TIME_MATCH_REGEX = re.compile(r"\**You will arrive at:\**\s*\n+<t:(\d+):[a-zA-Z]>", re.IGNORECASE)

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
    return "\n".join(text_parts)

class ToggleTravelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Toggle Travel Reminder", style=discord.ButtonStyle.primary, custom_id="toggle_travel_reminder_btn")
        
    async def callback(self, interaction: discord.Interaction):
        settings_cog = interaction.client.get_cog("Settings")
        if not settings_cog:
            await interaction.response.send_message("Settings cog not found.", ephemeral=True)
            return
            
        user_id_str = str(interaction.user.id)
        current_settings = settings_cog.get_user_settings(user_id_str)
        is_enabled = current_settings.get("travel_reminder", False)
        
        new_val = not is_enabled
        current_settings["travel_reminder"] = new_val
        settings_cog.save_user_settings(user_id_str, current_settings)
        
        status = "enabled" if new_val else "disabled"
        await interaction.response.send_message(f"Your travel reminder has been **{status}**.", ephemeral=True)

from cogs.reminder_views import UnifiedReminderView

class TravelReminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.processed_messages = set()
        self.message_user_cache = {}

    def is_reminder_enabled(self, user_id: str, setting_key: str) -> bool:
        settings_cog = self.bot.get_cog("Settings")
        if not settings_cog:
            return False
        return settings_cog.get_user_settings(user_id).get(setting_key, False)

    @commands.Cog.listener("on_reminder_due")
    async def on_reminder_due(self, reminder_data: dict):
        if reminder_data.get("reminder_type") != "travel":
            return
            
        user_id = reminder_data.get("user_id")
        channel_id = reminder_data.get("channel_id")
        extra_data = reminder_data.get("extra_data")
        
        location = "your destination"
        if extra_data:
            try:
                extra = json.loads(extra_data)
                location = extra.get("location", "your destination")
            except:
                pass
                
        user = self.bot.get_user(user_id)
        if not user:
            try:
                user = await self.bot.fetch_user(user_id)
            except (discord.NotFound, discord.HTTPException):
                pass
                
        if user:
            try:
                text = f"<@{user_id}> You have arrived at **{location}** and can fish now.\n > </fish catch:1011560371078832206>"
                from cogs.reminder_views import SnoozeReminderButton
                view = UnifiedReminderView(
                    title="Travel Reminder",
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
        elif message.reference and getattr(message.reference, 'resolved', None) and hasattr(message.reference.resolved, 'author'):
            user_id = str(message.reference.resolved.author.id)
            
        if not user_id and message.mentions:
            user_id = str(message.mentions[0].id)
            
        # Fallback to cache for edited messages.
        if not user_id:
            user_id = self.message_user_cache.get(message.id)
            
        # Cache found user.
        if user_id:
            self.message_user_cache[message.id] = user_id

        if not user_id:
            return
            
        content = message.content or ""
        full_text = content
        embed_title = ""
        
        if message.embeds:
            embed = message.embeds[0]
            if embed.title:
                embed_title = embed.title
                full_text += "\n" + embed.title
            if embed.description:
                full_text += "\n" + embed.description
            for field in embed.fields:
                full_text += "\n" + field.name + "\n" + field.value
                
        comp_text = ""
        if message.components:
            comp_text = extract_text_from_components(message.components)
            full_text += "\n" + comp_text
            
        full_text_lower = full_text.lower()
        
        # Detect travel cancellation.
        is_fishing = "fishing" in full_text_lower and (
            "current equipment" in full_text_lower or 
            "current location" in full_text_lower or 
            "bucket space" in full_text_lower or 
            "go fishing" in full_text_lower
        )
        
        if is_fishing:
            cursor = await db.pool.execute("SELECT target_time, channel_id, extra_data FROM reminders WHERE user_id=? AND reminder_type='travel'", (int(user_id),))
            row = await cursor.fetchone()
            if row:
                location = "your destination"
                if row['extra_data']:
                    try:
                        extra = json.loads(row['extra_data'])
                        location = extra.get("location", "your destination")
                    except:
                        pass
                channel_id = row['channel_id']
                
                await db.remove_reminders(int(user_id), "travel")
                
                if channel_id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        try:
                            text = f"<@{user_id}> Travel to **{location}** was cancelled."
                            view = UnifiedReminderView(title="Travel Reminder", text=text, buttons=[ToggleTravelButton()])
                            await channel.send(view=view)
                        except Exception:
                            pass
            return
            
        # Detect travel start.
        is_traveling = "traveling..." in full_text_lower
        if not is_traveling:
            return
            
        if not self.is_reminder_enabled(user_id, "travel_reminder"):
            return

        # Extract location and timestamp.
        location_match = LOCATION_MATCH_REGEX.search(full_text)
        time_match = TIME_MATCH_REGEX.search(full_text)
        
        if location_match and time_match:
            location = location_match.group(1).strip()
            location = location.replace('*', '').strip()
            timestamp = int(time_match.group(1))
            
            proc_key = f"{message.id}_{timestamp}"
            if proc_key in self.processed_messages:
                return
            
            self.processed_messages.add(proc_key)
            
            await db.add_reminder(int(user_id), message.channel.id, "travel", timestamp, {"location": location})
            
            view = UnifiedReminderView(title="Travel Reminder", text=f"I'll remind you to fish at **{location}** <t:{timestamp}:R>.", buttons=[ToggleTravelButton()])
            await message.reply(view=view)

async def setup(bot):
    await bot.add_cog(TravelReminders(bot))
