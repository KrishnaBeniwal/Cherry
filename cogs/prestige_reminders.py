import discord
from discord.ext import commands
import re
from cogs.reminder_views import UnifiedReminderView
import time
from emojis import DM_COINS, RAT_DANCE
from core.database import db

DANK_MEMER_ID = 270904126974590976

PRESTIGE_REQ_REGEX = re.compile(r"Prestige\s+(\d+)\s+Requirements", re.IGNORECASE)
TIMESTAMP_REGEX = re.compile(r"<t:(\d+):[a-zA-Z]>")
FALLBACK_REGEX = re.compile(r"You can prestige again in (.+?)(?:\n|$)", re.IGNORECASE)
BALANCE_REGEX = re.compile(r"Pocket Balance.*?([\d,]+)/([\d,]+)", re.IGNORECASE | re.DOTALL)
LEVEL_REGEX = re.compile(r"Level Required.*?(\d+)/(\d+)", re.IGNORECASE | re.DOTALL)
DUR_PART_REGEX = re.compile(r"(\d+)\s*(d|h|m|s|day|hour|minute|second)")
OMEGA_BUY_REGEX = re.compile(r"successfully purchased \*\*<a:omega\d+:\d+>\s*omega \d+\*\*", re.IGNORECASE)

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


class TogglePrestigeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Toggle Prestige Reminder", style=discord.ButtonStyle.primary, custom_id="toggle_prestige_reminder_btn")
        
    async def callback(self, interaction: discord.Interaction):
        settings_cog = interaction.client.get_cog("Settings")
        if not settings_cog:
            await interaction.response.send_message("Settings cog not found.", ephemeral=True)
            return
            
        user_id_str = str(interaction.user.id)
        current_settings = settings_cog.get_user_settings(user_id_str)
        is_enabled = current_settings.get("prestige_reminder", False)
        
        new_val = not is_enabled
        current_settings["prestige_reminder"] = new_val
        settings_cog.save_user_settings(user_id_str, current_settings)
        
        status = "enabled" if new_val else "disabled"
        await interaction.response.send_message(f"Your prestige reminder has been **{status}**.", ephemeral=True)



class PrestigeReminders(commands.Cog):
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
        if reminder_data.get("reminder_type") != "prestige":
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
                text = f"<@{user_id}> You can prestige now {RAT_DANCE} \n### > </advancements prestige:1011560371041095694>"
                from cogs.reminder_views import SnoozeReminderButton
                view = UnifiedReminderView(
                    title="Prestige Reminder",
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

        if not user_id:
            return
            
        self.message_user_cache[message.id] = user_id
            
        content = message.content or ""
        full_text = content
        
        if message.embeds:
            embed = message.embeds[0]
            if embed.title:
                full_text += "\n" + embed.title
            if embed.description:
                full_text += "\n" + embed.description
            for field in embed.fields:
                full_text += "\n" + field.name + "\n" + field.value
                
        if message.components:
            full_text += "\n" + extract_text_from_components(message.components)
            
        full_text_lower = full_text.lower()
        
        # Detect prestige success.
        is_prestige = "congratulations you absolute gamer." in full_text_lower
        is_omega = bool(OMEGA_BUY_REGEX.search(full_text_lower))
        
        if is_prestige or is_omega:
            if message.id in self.processed_messages:
                return
            self.processed_messages.add(message.id)
                
            # Clear item reminders.
            await db.clear_item_reminders(int(user_id))
            
            # Set next prestige reminder.
            if is_prestige:
                prestige_reminder_enabled = self.is_reminder_enabled(user_id, "prestige_reminder")
                if not prestige_reminder_enabled:
                    return
                
                timestamp = int(message.created_at.timestamp()) + (5 * 3600)
                
                res = await db.add_reminder_or_update(int(user_id), message.channel.id, "prestige", timestamp)
                
                if res > 0:
                    rem_view = UnifiedReminderView(title="Prestige Reminder", text=f"I will remind you to prestige <t:{timestamp}:R>.", buttons=[TogglePrestigeButton()])
                    
                    await message.reply(view=rem_view)
            return

        # Detect prestige requirements.
        title_match = PRESTIGE_REQ_REGEX.search(full_text)
        prestige_level = "?"
        if title_match:
            prestige_level = title_match.group(1)
        elif "are you sure you want to prestige?" not in full_text_lower:
            return
            
        if message.id in self.processed_messages:
            return
            
        prestige_reminder_enabled = self.is_reminder_enabled(user_id, "prestige_reminder")
        prestige_assistant_enabled = self.is_reminder_enabled(user_id, "prestige_assistant")
        
        if not prestige_reminder_enabled and not prestige_assistant_enabled:
            return

        self.processed_messages.add(message.id)

        # Extract timestamp.
        time_match = TIMESTAMP_REGEX.search(full_text)
        
        timestamp = None
        cd_match = None
        if time_match:
            timestamp = int(time_match.group(1))
        else:
            # Parse text durations.
            fallback_match = FALLBACK_REGEX.search(full_text)
            cd_match = fallback_match
            if fallback_match:
                duration_str = fallback_match.group(1).lower()
                total_seconds = 0
                for part in DUR_PART_REGEX.finditer(duration_str):
                    val = int(part.group(1))
                    unit = part.group(2)
                    if unit.startswith("d"): total_seconds += val * 86400
                    elif unit.startswith("h"): total_seconds += val * 3600
                    elif unit.startswith("m"): total_seconds += val * 60
                    elif unit.startswith("s"): total_seconds += val * 1
                
                if total_seconds > 0:
                    timestamp = int(time.time()) + total_seconds

        # Extract balance.
        balance_match = BALANCE_REGEX.search(full_text)
        coins_text = ""
        if balance_match:
            current_coins = int(balance_match.group(1).replace(',', ''))
            required_coins = int(balance_match.group(2).replace(',', ''))
            diff = abs(required_coins - current_coins)
            diff_fmt = f"{diff:,}"
            if current_coins < required_coins:
                coins_text = f"You need `{diff_fmt}` more coins {DM_COINS}"
            else:
                coins_text = f"You have `{diff_fmt}` extra coins {DM_COINS}"

        # Extract level.
        level_match = LEVEL_REGEX.search(full_text)
        levels_text = ""
        if level_match:
            current_level = int(level_match.group(1).replace(',', ''))
            required_level = int(level_match.group(2).replace(',', ''))
            diff = abs(required_level - current_level)
            diff_fmt = f"{diff:,}"
            if current_level < required_level:
                levels_text = f"You need `{diff_fmt}` more levels {RAT_DANCE}"
            else:
                levels_text = f"You have `{diff_fmt}` extra levels {RAT_DANCE}"

        # Check if already set.
        reminder_already_set = False
        cursor = await db.pool.execute("SELECT target_time FROM reminders WHERE user_id=? AND reminder_type='prestige'", (int(user_id),))
        row = await cursor.fetchone()
        if row:
            reminder_already_set = True

        # Send reminder.
        if prestige_reminder_enabled and timestamp and not reminder_already_set:
            res = await db.add_reminder_or_update(int(user_id), message.channel.id, "prestige", timestamp)
            if res > 0:
                rem_view = UnifiedReminderView(title="Prestige Reminder", text=f"I will remind you to prestige <t:{timestamp}:R>.", buttons=[TogglePrestigeButton()])
                
                await message.reply(view=rem_view)

        # Send assistant view.
        if prestige_assistant_enabled and (coins_text or levels_text):
            ast_view = discord.ui.LayoutView(timeout=None)
            
            # Build V2 UI.
            c = discord.ui.Container()
            
            title_text = f"### Prestige {prestige_level} Requirements" if prestige_level != "?" else "### Prestige Requirements"
            c.add_item(discord.ui.TextDisplay(content=title_text))
            
            c.add_item(discord.ui.Separator())
            
            ast_body = []
            if coins_text:
                ast_body.append(coins_text)
            if levels_text:
                ast_body.append(levels_text)
                
            c.add_item(discord.ui.TextDisplay(content="\n\n".join(ast_body)))
            ast_view.add_item(c)
            
            await message.reply(view=ast_view)

async def setup(bot):
    await bot.add_cog(PrestigeReminders(bot))
