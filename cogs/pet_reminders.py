import discord
from discord.ext import commands
import re
import json
from cogs.reminder_views import UnifiedReminderView
from core.database import db

DANK_MEMER_ID = 270904126974590976

PET_MATCH_REGEX = re.compile(r"###\s*([^\n]+)", re.IGNORECASE)
HUNGER_MATCH_REGEX = re.compile(r"\*\*Hunger\*\*\s*empty\s*<t:(\d+):R>", re.IGNORECASE)

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

class TogglePetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Toggle Pet Reminder", style=discord.ButtonStyle.primary, custom_id="toggle_pet_reminder_btn")
        
    async def callback(self, interaction: discord.Interaction):
        settings_cog = interaction.client.get_cog("Settings")
        if not settings_cog:
            await interaction.response.send_message("Settings cog not found.", ephemeral=True)
            return
            
        user_id_str = str(interaction.user.id)
        current_settings = settings_cog.get_user_settings(user_id_str)
        is_enabled = current_settings.get("pet_reminder", False)
        
        new_val = not is_enabled
        current_settings["pet_reminder"] = new_val
        settings_cog.save_user_settings(user_id_str, current_settings)
        
        status = "enabled" if new_val else "disabled"
        if new_val:
            text = "### Note:\nYou must react with 💀 on a pet's care page to set it as your active pet.\n\nOnly your active pet will receive feeding reminders."
        else:
            text = f"Your pet reminder has been **disabled**."
            
        await interaction.response.send_message(text, ephemeral=True)


class PetReminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_user_cache = {}

    def set_active_pet(self, user_id: str, pet_name: str):
        settings_cog = self.bot.get_cog("Settings")
        if settings_cog:
            settings = settings_cog.get_user_settings(user_id)
            settings["active_pet"] = pet_name
            settings_cog.save_user_settings(user_id, settings)
            
    def get_active_pet(self, user_id: str) -> str:
        settings_cog = self.bot.get_cog("Settings")
        if settings_cog:
            return settings_cog.get_user_settings(user_id).get("active_pet")
        return None

    def is_reminder_enabled(self, user_id: str, setting_key: str) -> bool:
        settings_cog = self.bot.get_cog("Settings")
        if not settings_cog:
            return False
        return settings_cog.get_user_settings(user_id).get(setting_key, False)

    @commands.Cog.listener("on_reminder_due")
    async def on_reminder_due(self, reminder_data: dict):
        if reminder_data.get("reminder_type") != "pet_feed":
            return
            
        user_id = reminder_data.get("user_id")
        channel_id = reminder_data.get("channel_id")
        extra_data = reminder_data.get("extra_data")
        
        pet_name = "your pet"
        if extra_data:
            try:
                extra = json.loads(extra_data)
                pet_name = extra.get("pet_name", "your pet")
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
                text = f"<@{user_id}> It's time to feed **{pet_name}**, he is hungry again.\n\n### > </pets care:1011560371171102768>"
                from cogs.reminder_views import SnoozeReminderButton
                view = UnifiedReminderView(
                    title="Pet Reminder",
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
                        except Exception as e:
                            pass
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "💀":
            return
            
        if payload.user_id == self.bot.user.id:
            return
            
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except Exception:
                return
                
        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            return
            
        if message.author.id != DANK_MEMER_ID:
            return
            
        user_id = None
        if getattr(message, 'interaction_metadata', None):
            user_id = str(message.interaction_metadata.user.id)
        elif message.reference and getattr(message.reference, 'resolved', None) and hasattr(message.reference.resolved, 'author'):
            user_id = str(message.reference.resolved.author.id)
            
        if not user_id and message.mentions:
            user_id = str(message.mentions[0].id)
            
        if not user_id:
            user_id = self.message_user_cache.get(message.id)
            
        if str(payload.user_id) != user_id:
            return
            
        content = message.content or ""
        if message.components:
            content += "\n" + extract_text_from_components(message.components)
            
        if "**Hunger**" not in content and "**Hygiene**" not in content:
            return
            
        pet_match = PET_MATCH_REGEX.search(content)
        if not pet_match:
            return
            
        pet_name = pet_match.group(1).strip()
        
        # Remove the reaction.
        try:
            await message.remove_reaction("💀", payload.member or await self.bot.fetch_user(payload.user_id))
        except Exception:
            pass
            
        self.set_active_pet(str(payload.user_id), pet_name)
        
        text = f"### Active Pet Updated\n**{pet_name}** is now your active pet."
        try:
            await message.reply(text)
        except Exception as e:
            pass
            
        hunger_match = HUNGER_MATCH_REGEX.search(content)
        if hunger_match and self.is_reminder_enabled(str(payload.user_id), "pet_reminder"):
            timestamp = int(hunger_match.group(1))
            
            rem_text = f"<@{payload.user_id}> Reminder set for feeding **{pet_name}**\nReminder at:\n\n> <t:{timestamp}:F>"
            rem_view = UnifiedReminderView(title="Pet Reminder", text=rem_text, buttons=[TogglePetButton()])
            
            await db.remove_reminders(int(payload.user_id), "pet_feed")
            try:
                rem_msg = await message.reply(view=rem_view)
                await db.add_reminder(int(payload.user_id), payload.channel_id, "pet_feed", timestamp, {"pet_name": pet_name, "status_message_id": rem_msg.id})
            except Exception as e:
                await db.add_reminder(int(payload.user_id), payload.channel_id, "pet_feed", timestamp, {"pet_name": pet_name})

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
            
        if not self.is_reminder_enabled(user_id, "pet_reminder"):
            return
            
        content = message.content or ""
        if message.components:
            content += "\n" + extract_text_from_components(message.components)
            
        if "**Hunger**" not in content and "**Hygiene**" not in content:
            return
            
        pet_match = PET_MATCH_REGEX.search(content)
        if not pet_match:
            return
            
        pet_name = pet_match.group(1).strip()
        active_pet = self.get_active_pet(user_id)
        
        if pet_name != active_pet:
            return
            
        hunger_match = HUNGER_MATCH_REGEX.search(content)
        if not hunger_match:
            return
            
        timestamp = int(hunger_match.group(1))
        
        # Check if reminder is unchanged.
        cursor = await db.pool.execute("SELECT target_time, extra_data FROM reminders WHERE user_id=? AND reminder_type='pet_feed'", (int(user_id),))
        row = await cursor.fetchone()
        
        status_message_id = None
        if row:
            if row['target_time'] == timestamp:
                return # Unchanged
            if row['extra_data']:
                try:
                    extra = json.loads(row['extra_data'])
                    status_message_id = extra.get("status_message_id")
                except:
                    pass

        text = f"Reminder set for feeding {pet_name}\n\nReminder at:\n\n> <t:{timestamp}:F>"
        view = UnifiedReminderView(title="Pet Reminder", text=text, buttons=[TogglePetButton()])
        
        await db.remove_reminders(int(user_id), "pet_feed")
        
        updated = False
        rem_data = {"pet_name": pet_name}
        if status_message_id:
            try:
                status_msg = await message.channel.fetch_message(status_message_id)
                await status_msg.edit(view=view)
                rem_data["status_message_id"] = status_message_id
                updated = True
            except Exception as e:
                pass
                
        if not updated:
            try:
                new_msg = await message.reply(view=view)
                rem_data["status_message_id"] = new_msg.id
            except Exception as e:
                pass
                
        await db.add_reminder(int(user_id), message.channel.id, "pet_feed", timestamp, rem_data)

async def setup(bot):
    await bot.add_cog(PetReminders(bot))
