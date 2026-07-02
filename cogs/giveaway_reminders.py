import discord
from discord.ext import commands
from cogs.reminder_views import UnifiedReminderView
import time
from core.database import db

DANK_MEMER_ID = 270904126974590976

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

class ToggleGiveawayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Toggle Giveaway Reminder", style=discord.ButtonStyle.primary, custom_id="toggle_giveaway_reminder_btn")
        
    async def callback(self, interaction: discord.Interaction):
        settings_cog = interaction.client.get_cog("Settings")
        if not settings_cog:
            await interaction.response.send_message("Settings cog not found.", ephemeral=True)
            return
            
        user_id_str = str(interaction.user.id)
        current_settings = settings_cog.get_user_settings(user_id_str)
        is_enabled = current_settings.get("giveaway_reminder", False)
        
        new_val = not is_enabled
        current_settings["giveaway_reminder"] = new_val
        settings_cog.save_user_settings(user_id_str, current_settings)
        
        status = "enabled" if new_val else "disabled"
        
        view = discord.ui.View()
        text = f"Your giveaway reminder has been **{status}**."
        
        await interaction.response.send_message(text, ephemeral=True)



class GiveawayReminders(commands.Cog):
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
        if reminder_data.get("reminder_type") != "giveaway":
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
                text = f"<@{user_id}> You can now create a giveaway.\n### > </giveaway create coins:1011560371078832208>\n> </giveaway create items:1011560371078832208>"
                
                from cogs.reminder_views import SnoozeReminderButton
                view = UnifiedReminderView(
                    title="Giveaway Reminder",
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
            
        if not user_id:
            user_id = self.message_user_cache.get(message.id)
            
        if user_id:
            self.message_user_cache[message.id] = user_id

        if not user_id:
            return
            
        content = message.content or ""
        if message.embeds:
            for em in message.embeds:
                if em.description: content += "\n" + str(em.description)
                if em.title: content += "\n" + str(em.title)
        if message.components:
            content += "\n" + extract_text_from_components(message.components)
            
        timestamp = None
        if "Created your giveaway!" in content:
            timestamp = int(time.time()) + 300
        elif "You can't create a new giveaway yet" in content and "You can create a new one" in content:
            import re
            match = re.search(r"<t:(\d+):[Rf]>", content)
            if match:
                timestamp = int(match.group(1))
                
        if not timestamp:
            return
            
        if not self.is_reminder_enabled(user_id, "giveaway_reminder"):
            return
            
        res = await db.add_reminder_or_update(int(user_id), message.channel.id, "giveaway", timestamp)
        if res > 0:
            text = f"I'll remind you to create a giveaway <t:{timestamp}:R>."
            view = UnifiedReminderView(title="Giveaway Reminder", text=text, buttons=[ToggleGiveawayButton()])
            try:
                await message.reply(view=view)
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(GiveawayReminders(bot))
