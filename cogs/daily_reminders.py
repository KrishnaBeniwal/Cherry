import discord
import re
from discord.ext import commands
import time
from cogs.reminder_views import UnifiedReminderView
import datetime
from emojis import VERIFIED_TICK

DAILY_COINS_REGEX = re.compile(r"'s Daily Coins", re.IGNORECASE)

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

class DailyClaimButton(discord.ui.Button):
    def __init__(self, user_id: str, cog: 'DailyReminders'):
        super().__init__(label="Claimed already", style=discord.ButtonStyle.success, custom_id=f"daily_claim_btn_{user_id}")
        self.user_id = user_id
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This isn't your reminder!", ephemeral=True)
            return
            
        self.cog.mark_claimed(self.user_id)
        
        view = UnifiedReminderView(
            title="Daily Reminder",
            text=f"{VERIFIED_TICK} Daily claimed for today!"
        )
        await interaction.response.edit_message(view=view)
        self.cog.active_reminders.pop(self.user_id, None)

class DailyReminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_reminders = {} # user_id -> Message
        self.message_user_cache = {}
        self.last_burst_time = {} # user_id -> timestamp

    def get_utc_date(self) -> str:
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    def is_claimed_today(self, user_id: str) -> bool:
        settings_cog = self.bot.get_cog("Settings")
        if settings_cog:
            settings = settings_cog.get_user_settings(user_id)
            return settings.get("last_daily") == self.get_utc_date()
        return False

    def mark_claimed(self, user_id: str):
        settings_cog = self.bot.get_cog("Settings")
        if settings_cog:
            settings = settings_cog.get_user_settings(user_id)
            settings["last_daily"] = self.get_utc_date()
            settings_cog.save_user_settings(user_id, settings)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id != 270904126974590976:
            return
            
        user_id_str = None
        if getattr(message, 'interaction_metadata', None) and message.interaction_metadata.user:
            user_id_str = str(message.interaction_metadata.user.id)
        elif message.reference and getattr(message.reference, 'resolved', None) and hasattr(message.reference.resolved, 'author'):
            user_id_str = str(message.reference.resolved.author.id)
            
        if not user_id_str and message.mentions:
            user_id_str = str(message.mentions[0].id)

        if not user_id_str:
            user_id_str = self.message_user_cache.get(message.id)

        if not user_id_str:
            return
            
        self.message_user_cache[message.id] = user_id_str
        
        # Check if enabled for user.
        settings_cog = self.bot.get_cog("Settings")
        if not settings_cog:
            return
            
        user_settings = settings_cog.get_user_settings(user_id_str)
        is_enabled = user_settings.get("daily_reminder", False)
        
        if not is_enabled:
            return
            
        is_daily = False
            
        full_text = getattr(message, "content", "") + " "
        if message.embeds:
            for embed in message.embeds:
                try:
                    full_text += str(embed.to_dict()) + " "
                except Exception:
                    pass
        
        full_text += "\n" + extract_text_from_components(message.components)
        
        if re.search(r"['’]s Daily Coins", full_text, re.IGNORECASE) or \
           "was placed in your wallet!" in full_text or \
           "You already got your daily today" in full_text:
            is_daily = True
            
        if is_daily:
            self.mark_claimed(user_id_str)
            
            old_msg = self.active_reminders.pop(user_id_str, None)
            
            if old_msg:
                try:
                    await old_msg.delete()
                except Exception:
                    pass
                    
            try:
                await message.add_reaction(VERIFIED_TICK)
            except Exception:
                pass
                
            return
            
        if not self.is_claimed_today(user_id_str):
            now = time.time()
            if now - self.last_burst_time.get(user_id_str, 0) < 1.5:
                return
                
            self.last_burst_time[user_id_str] = now
            
            old_msg = self.active_reminders.pop(user_id_str, None)
            if old_msg:
                try:
                    await old_msg.delete()
                except Exception:
                    pass
            
            view = UnifiedReminderView(
                title="Daily Reminder",
                text=f"<@{user_id_str}> Reminder to run </daily:1011560370864930856>",
                buttons=[DailyClaimButton(user_id_str, self)]
            )
            try:
                sent_msg = await message.reply(view=view)
                self.active_reminders[user_id_str] = sent_msg
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(DailyReminders(bot))
