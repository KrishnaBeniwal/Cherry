import discord
from discord.ext import commands
import re
from core.database import db

DANK_MEMER_ID = 270904126974590976
GROUP_WINDOW = 300

FARM_MATCH_REGEX = re.compile(r"### Farm #([123])", re.IGNORECASE)
CROP_PATTERN_REGEX = re.compile(r":.+?:\s*(.*?)\s*ready\s*<t:(\d+):R>", re.IGNORECASE)

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

class ToggleFarmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Toggle Farm Reminder", style=discord.ButtonStyle.primary, custom_id="toggle_farm_reminder_btn")
        
    async def callback(self, interaction: discord.Interaction):
        settings_cog = interaction.client.get_cog("Settings")
        if not settings_cog:
            await interaction.response.send_message("Settings cog not found.", ephemeral=True)
            return
            
        user_id_str = str(interaction.user.id)
        current_settings = settings_cog.get_user_settings(user_id_str)
        is_enabled = current_settings.get("farm_reminder", False)
        
        new_val = not is_enabled
        current_settings["farm_reminder"] = new_val
        settings_cog.save_user_settings(user_id_str, current_settings)
        
        status = "enabled" if new_val else "disabled"
        await interaction.response.send_message(f"Your farm reminder has been **{status}**.", ephemeral=True)

from cogs.reminder_views import UnifiedReminderView

class FarmReminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_user_cache = {}

    def is_reminder_enabled(self, user_id: str, setting_key: str) -> bool:
        settings_cog = self.bot.get_cog("Settings")
        if not settings_cog:
            return False
        return settings_cog.get_user_settings(user_id).get(setting_key, False)

    @commands.Cog.listener("on_reminder_due")
    async def on_reminder_due(self, reminder_data: dict):
        reminder_type = reminder_data.get("reminder_type")
        if not reminder_type.startswith("farm_"):
            return
            
        farm_number = reminder_type.split("_")[1]
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
                text = f"<@{user_id}> Your crops are ready to harvest at **Farm #{farm_number}**\n### > </farm view:1044653042965954571>"
                from cogs.reminder_views import SnoozeReminderButton
                view = UnifiedReminderView(
                    title="Farm Reminder",
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
            
        full_text = extract_text_from_components(message.components)
        await self._process_dank_message(message, full_text=full_text)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.author.id != DANK_MEMER_ID:
            return
            
        full_text = extract_text_from_components(after.components)
        await self._process_dank_message(after, full_text=full_text)

    async def _process_dank_message(self, message: discord.Message, full_text: str = None):
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
            
        # Store user in cache.
        self.message_user_cache[message.id] = user_id

        if not message.components:
            return

        if full_text is None:
            full_text = extract_text_from_components(message.components)
        
        farm_match = FARM_MATCH_REGEX.search(full_text)
        
        if not farm_match:
            return

        if not self.is_reminder_enabled(user_id, "farm_reminder"):
            return

        farm_number = farm_match.group(1)
        farm_key = f"farm_{farm_number}"

        # Extract crops.
        raw_timestamps = []
        for line in full_text.splitlines():
            line = line.strip()
            if "ready <t:" not in line:
                continue
                
            crop_match = CROP_PATTERN_REGEX.search(line)
            if crop_match:
                timestamp = int(crop_match.group(2))
                raw_timestamps.append(timestamp)

        if not raw_timestamps:
            return

        # Group timestamps.
        sorted_ts = sorted(list(set(raw_timestamps)))
        grouped_reminders = []
        for ts in sorted_ts:
            if not grouped_reminders:
                grouped_reminders.append(ts)
            elif ts - grouped_reminders[-1] >= GROUP_WINDOW:
                grouped_reminders.append(ts)

        # Compare parsed and stored data.
        cursor = await db.pool.execute(
            "SELECT target_time FROM reminders WHERE user_id=? AND reminder_type=? ORDER BY target_time ASC",
            (int(user_id), farm_key)
        )
        existing_rows = await cursor.fetchall()
        existing_timestamps = [row['target_time'] for row in existing_rows]
        
        if existing_timestamps == grouped_reminders:
            return

        # Replace old reminders with grouped ones.
        await db.remove_reminders(int(user_id), farm_key)
        for ts in grouped_reminders:
            await db.add_reminder(int(user_id), message.channel.id, farm_key, ts)

        # Send response.
        text_lines = []
        if len(grouped_reminders) > 1:
            text_lines.append(f"Reminder(s) for **Farm #{farm_number}** at:\n")
        else:
            text_lines.append(f"Reminder for **Farm #{farm_number}** at:\n")
            
        for ts in grouped_reminders:
            text_lines.append(f"> <t:{ts}:F>")
            
        rem_view = UnifiedReminderView(
            title="Farm Reminder",
            text="\n".join(text_lines),
            buttons=[ToggleFarmButton()]
        )

        await message.reply(view=rem_view)

async def setup(bot):
    await bot.add_cog(FarmReminders(bot))
