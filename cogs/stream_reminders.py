import discord
from discord.ext import commands
import time
from core.database import db
from cogs.reminder_views import UnifiedReminderView

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

class ToggleStreamButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Toggle Stream Reminder", style=discord.ButtonStyle.primary, custom_id="toggle_stream_reminder_btn")
        
    async def callback(self, interaction: discord.Interaction):
        settings_cog = interaction.client.get_cog("Settings")
        if not settings_cog:
            await interaction.response.send_message("Settings cog not found.", ephemeral=True)
            return
            
        user_id_str = str(interaction.user.id)
        current_settings = settings_cog.get_user_settings(user_id_str)
        is_enabled = current_settings.get("stream_reminder", False)
        
        new_val = not is_enabled
        current_settings["stream_reminder"] = new_val
        settings_cog.save_user_settings(user_id_str, current_settings)
        
        status = "enabled" if new_val else "disabled"
        
        view = discord.ui.LayoutView()
        c = discord.ui.Container()
        text = f"Your stream reminder has been **{status}**."
        c.add_item(discord.ui.TextDisplay(content=text))
        view.add_item(c)
        
        await interaction.response.send_message(view=view, ephemeral=True)



class StreamReminders(commands.Cog):
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
        if reminder_data.get("reminder_type") not in ["stream_interaction", "stream_cooldown"]:
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
                if reminder_data.get("reminder_type") == "stream_interaction":
                    msg = f"<@{user_id}> you can now interact with your stream again.\n### > </stream:1011560371267579938>"
                else:
                    msg = f"<@{user_id}> you can now stream again.\n### > </stream:1011560371267579938>"
                    
                from cogs.reminder_views import SnoozeReminderButton
                view = UnifiedReminderView(
                    title="Stream Reminder",
                    text=msg,
                    buttons=[SnoozeReminderButton(user_id=user_id)]
                )
                
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    channel = await self.bot.fetch_channel(channel_id)
                    
                await channel.send(view=view)
            except Exception as e:
                try:
                    await user.send(view=view)
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id != DANK_MEMER_ID:
            return
            
        if message.interaction_metadata and message.interaction_metadata.user:
            self.message_user_cache[message.id] = message.interaction_metadata.user.id
            # Prevent cache from growing indefinitely.
            if len(self.message_user_cache) > 2000:
                self.message_user_cache.pop(next(iter(self.message_user_cache)))

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.author.id != DANK_MEMER_ID:
            return
            
        if not after.embeds:
            return
            
        embed = after.embeds[0]
        if not embed.author or not embed.author.name or not embed.author.name.endswith("'s Stream Manager"):
            return
            
        user_id = None
        if after.interaction_metadata and after.interaction_metadata.user:
            user_id = after.interaction_metadata.user.id
        else:
            user_id = self.message_user_cache.get(after.id)
            
        # Try extracting user ID from components.
        if not user_id:
            for row in after.components:
                for comp in row.children:
                    if hasattr(comp, 'custom_id') and comp.custom_id and ':' in comp.custom_id:
                        try:
                            user_id = int(comp.custom_id.split(':')[-1])
                            break
                        except ValueError:
                            pass
                if user_id:
                    break
                    
        if not user_id:
            return
            
        user_id_str = str(user_id)
        is_enabled = self.is_reminder_enabled(user_id_str, "stream_reminder")
        if not is_enabled:
            return
            
        # Check for state transitions.
        before_comps_text = extract_text_from_components(before.components).lower()
        after_comps_text = extract_text_from_components(after.components).lower()
        
        is_go_live_state_before = "go live" in before_comps_text and "view setup" in before_comps_text
        is_go_live_state_after = "go live" in after_comps_text and "view setup" in after_comps_text
        
        embeds_equal = (before.embeds == after.embeds)
        components_equal = (before.components == after.components)
        
        before_desc = before.embeds[0].description.lower() if before.embeds and before.embeds[0].description else ""
        after_desc = after.embeds[0].description.lower() if after.embeds and after.embeds[0].description else ""
        
        stream_just_ended = ("ended" in after_desc and "ended" not in before_desc) or ("stream ended" in after_desc and "stream ended" not in before_desc)
        
        # Check reminder type.
        reminder_type = None
        duration = 0
        
        # 30-minute stream cooldown.
        # Triggers on stream end.
        if (not is_go_live_state_before and is_go_live_state_after) or stream_just_ended:
            reminder_type = "stream_cooldown"
            duration = 1800 # 30 minutes
            
        # 10-minute interaction cooldown.
        # Triggers on normal interaction.
        elif not is_go_live_state_after and embeds_equal and not components_equal:
            reminder_type = "stream_interaction"
            duration = 600 # 10 minutes
            
        if not reminder_type:
            return
            
        # Calculate target time.
        target_time = int(time.time()) + duration
        
        res = await db.add_reminder_or_update(user_id, after.channel.id, reminder_type, target_time)
        if res <= 0:
            return
            
        # Confirm reminder creation.
        view = UnifiedReminderView(
            title="Stream Reminder",
            text=f"Added stream reminder <t:{target_time}:R>"
        )
        
        try:
            await after.channel.send(view=view, reference=after)
        except Exception as e:
            try:
                await after.channel.send(view=view)
            except Exception as e2:
                pass

async def setup(bot):
    await bot.add_cog(StreamReminders(bot))
