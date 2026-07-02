import discord
from discord.ext import commands
import re
from cogs.reminder_views import UnifiedReminderView
import time
from core.database import db

DANK_MEMER_ID = 270904126974590976

TIME_MINS_REGEX = re.compile(r'for (?:the next )?(\d+)\s*minutes?', re.IGNORECASE)
TIME_HOURS_REGEX = re.compile(r'for (?:the next )?(\d+)\s*hours?', re.IGNORECASE)
TIME_DAYS_REGEX = re.compile(r'for (?:the next )?(\d+)\s*days?', re.IGNORECASE)
TIME_HOURS_WITHIN_REGEX = re.compile(r'within the next (\d+)\s*hours?', re.IGNORECASE)
TIME_MINS_WEAR_REGEX = re.compile(r'wear off in (\d+)\s*minutes?', re.IGNORECASE)
TIMESTAMP_REGEX = re.compile(r'<t:(\d+):[a-zA-Z]>', re.IGNORECASE)
DAILY_BOX_REGEX = re.compile(r'\d+\s+daily box opened', re.IGNORECASE)

class ItemReminders(commands.Cog):
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
        reminder_type = reminder_data.get("reminder_type")
        if not reminder_type.startswith("item_"):
            return
            
        item_key = reminder_type[5:] # Remove "item_"
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
                item_name = item_key.replace("_", " ").title()
                cooldown_items = ["tip_jar", "d20", "rusty_machine"]
                omega_items = ["omega_finish_crafts", "omega_grow_plants", "omega_bait"]
                
                if item_key in cooldown_items:
                    text = f"<@{user_id}> you can use **{item_name}** again!"
                elif item_key in omega_items:
                    if item_key == "omega_finish_crafts":
                        disp = "Instantly Finish Ongoing Crafts"
                    elif item_key == "omega_grow_plants":
                        disp = "Instantly Grow Plants"
                    else:
                        disp = "Omega bait"
                    text = f"<@{user_id}> you can buy {disp} from omega shop.\n\n### > </advancements omega:1011560371041095694>"
                else:
                    text = f"<@{user_id}> Your **{item_name}** has expired!"
                from cogs.reminder_views import SnoozeReminderButton
                view = UnifiedReminderView(
                    title="Item Reminder",
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
        has_embeds = bool(message.embeds)
        if message.author.id != DANK_MEMER_ID and not has_embeds:
            return
        await self._process_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        has_embeds = bool(after.embeds)
        if after.author.id != DANK_MEMER_ID and not has_embeds:
            return
        await self._process_message(after)

    async def _process_message(self, message: discord.Message):
        # 1. Resolve User ID
        user_id = None
        if getattr(message, 'interaction_metadata', None):
            user_id = str(message.interaction_metadata.user.id)
        elif message.reference:
            if getattr(message.reference, 'resolved', None) and hasattr(message.reference.resolved, 'author'):
                user_id = str(message.reference.resolved.author.id)
            elif message.reference.message_id:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    user_id = str(ref_msg.author.id)
                except Exception:
                    pass
            
        if not user_id and message.mentions:
            user_id = str(message.mentions[0].id)

        if not user_id:
            user_id = self.message_user_cache.get(message.id)

        if not user_id:
            return
            
        self.message_user_cache[message.id] = user_id
            
        embeds = message.embeds
        if not embeds:
            return
            
        embed = embeds[0]
        embed_desc = str(embed.description or "").lower()
        if embed.fields:
            for field in embed.fields:
                embed_desc += "\n" + str(field.name or "").lower() + "\n" + str(field.value or "").lower()
        embed_footer = str(embed.footer.text or "").lower() if embed.footer else ""
        
        # Extract component text.
        component_text = ""
        for row in message.components:
            for child in getattr(row, 'children', []):
                if hasattr(child, 'label') and child.label:
                    component_text += str(child.label).lower() + " "
        
        matched_item = None
        duration_seconds = 0
        extracted_timestamp = 0
        
        # Daily Box.
        if DAILY_BOX_REGEX.search(embed_footer):
            matched_item = "daily_box"
            time_match = TIME_MINS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 60
                
        # Cowboy Boots.
        elif "you put cowboy boots on" in embed_desc:
            matched_item = "cowboy_boots"
            time_match = TIME_HOURS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 3600
                
        # Pizza Slice.
        elif "you eat the perfect slice of pizza" in embed_desc:
            matched_item = "pizza_slice"
            time_match = TIME_MINS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 60
                
        # Crunchy Taco.
        elif "you eat a delicious hard shelled taco" in embed_desc:
            matched_item = "crunchy_taco"
            time_match = TIME_MINS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 60
                
        # Zombie Hand.
        elif "you put the hand up to your mouth and consume it" in embed_desc:
            matched_item = "zombie_hand"
            time_match = TIME_HOURS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 3600
                
        # Energy Drink.
        elif "you took a sip from the energy drink" in embed_desc:
            matched_item = "energy_drink"
            time_match = TIME_HOURS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 3600
                
        # Inflated Delicacy.
        elif "you consumed the inflated delicacy" in embed_desc:
            matched_item = "inflated"
            time_match = TIME_MINS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 60
                
        # Prismatic Delight.
        elif "you consumed the prismatic delight" in embed_desc:
            matched_item = "prismatic_delight"
            time_match = TIME_MINS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 60
                
        # Adventure Compass.
        elif "you equipped your handy dandy compass" in embed_desc:
            matched_item = "adventure_compass"
            duration_seconds = 3600
            
        # Rusty Machine.
        elif "set a reminder for when the rusty machine is ready again" in embed_desc:
            matched_item = "rusty_machine"
            duration_seconds = 3600
            
        # Jokebook.
        elif "you can not get a dead meme while posting memes" in embed_desc:
            matched_item = "jokebook"
            time_match = TIME_HOURS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 3600
                
        # Pepe's Bath Water.
        elif "you take a gulp of pepe's bath water" in embed_desc:
            matched_item = "pepss_bath_water"
            time_match = TIME_DAYS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 86400
                
        # Tentacled Temptation.
        elif "you consumed the tentacled temptation" in embed_desc:
            matched_item = "tentacled_temptation"
            time_match = TIME_HOURS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 3600
                
        # Tip Jar.
        elif "in your tip jar" in embed_desc or "dropped it. it broke, sorry" in embed_desc:
            matched_item = "tip_jar"
            duration_seconds = 3600
            
        # Lucky Horseshoe.
        elif "lucky horseshoe, giving you slightly better luck" in embed_desc:
            matched_item = "lucky_horseshoe"
            time_match = TIME_MINS_WEAR_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 60

        # Ammo.
        elif "you load ammo into your hunting rifle" in embed_desc:
            matched_item = "ammo"
            time_match = TIME_MINS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 60
                
        # Stolen Amulet.
        elif "you equipped your shiny (totally not stolen) amulet" in embed_desc:
            matched_item = "stolen_amulet"
            time_match = TIME_HOURS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 3600
                
        # Apple.
        elif "you've eaten an apple!" in embed_desc:
            matched_item = "apple"
            time_match = TIME_HOURS_WITHIN_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 3600
                
        # D20.
        elif ("rolled:" in embed_desc or "rolled:" in embed_footer) and "remind me" in component_text:
            matched_item = "d20"
            duration_seconds = 86400
            
        # Beggar's Bowl.
        elif "you ready your bowl, and for the next day" in embed_desc:
            matched_item = "beggars_bowl"
            duration_seconds = 86400
            
        # Grub Pail.
        elif "you consumed the grub pail" in embed_desc:
            matched_item = "grub_pail"
            time_match = TIME_HOURS_REGEX.search(embed_desc)
            if time_match:
                duration_seconds = int(time_match.group(1)) * 3600
                
        # Omega Shop Items.
        elif "instantly finish ongoing crafts" in embed_desc and "successfully purchased" in embed_desc:
            matched_item = "omega_finish_crafts"
            duration_seconds = 86400
            
        elif "instantly grow plants" in embed_desc and "successfully purchased" in embed_desc:
            matched_item = "omega_grow_plants"
            duration_seconds = 86400
            
        elif "omega bait" in embed_desc and "successfully purchased" in embed_desc:
            matched_item = "omega_bait"
            duration_seconds = 86400
                
        # Cooldowns with timestamps.
        elif "you already used" in embed_desc and "rusty machine" in embed_desc:
            matched_item = "rusty_machine"
            time_match = TIMESTAMP_REGEX.search(embed_desc)
            if time_match:
                extracted_timestamp = int(time_match.group(1))
                
        elif "you already used the tipjar this hour" in embed_desc:
            matched_item = "tip_jar"
            time_match = TIMESTAMP_REGEX.search(embed_desc)
            if time_match:
                extracted_timestamp = int(time_match.group(1))
                
        elif "you already used the d20" in embed_desc:
            matched_item = "d20"
            time_match = TIMESTAMP_REGEX.search(embed_desc)
            if time_match:
                extracted_timestamp = int(time_match.group(1))

        if not matched_item or (duration_seconds == 0 and extracted_timestamp == 0):
            return
            
        # Check if enabled.
        omega_items = ["omega_finish_crafts", "omega_grow_plants", "omega_bait"]
        if matched_item in omega_items:
            is_enabled = self.is_reminder_enabled(user_id, "omega_shop_reminder")
        else:
            is_enabled = self.is_reminder_enabled(user_id, matched_item)
        
        # Support legacy keys.
        if not is_enabled:
            if matched_item == "pizza_slice":
                is_enabled = self.is_reminder_enabled(user_id, "pizza")
                
        if not is_enabled:
            return
            
        if message.id in self.processed_messages:
            return
        self.processed_messages.add(message.id)
            
        # Set reminder.
        if extracted_timestamp > 0:
            timestamp = extracted_timestamp
        else:
            if matched_item == "daily_box":
                cursor = await db.pool.execute("SELECT target_time FROM reminders WHERE user_id = ? AND reminder_type = ? ORDER BY target_time DESC LIMIT 1", (int(user_id), f"item_{matched_item}"))
                row = await cursor.fetchone()
                if row and row['target_time'] > int(time.time()):
                    timestamp = row['target_time'] + duration_seconds
                    await db.remove_reminders(int(user_id), f"item_{matched_item}")
                else:
                    timestamp = int(time.time()) + duration_seconds
            else:
                timestamp = int(time.time()) + duration_seconds
            
        if matched_item == "daily_box":
            await db.add_reminder(int(user_id), message.channel.id, f"item_{matched_item}", timestamp)
            res = 1
        else:
            res = await db.add_reminder_or_update(int(user_id), message.channel.id, f"item_{matched_item}", timestamp)
            
        if res <= 0:
            return
        
        # Send confirmation.
        item_name = matched_item.replace("_", " ").title()
        
        cooldown_items = ["tip_jar", "d20", "rusty_machine"]
        omega_items = ["omega_finish_crafts", "omega_grow_plants", "omega_bait"]
        
        if matched_item in cooldown_items or matched_item in omega_items:
            if "omega" in matched_item:
                if matched_item == "omega_finish_crafts":
                    item_name = "Instantly Finish Ongoing Crafts"
                elif matched_item == "omega_grow_plants":
                    item_name = "Instantly Grow Plants"
                else:
                    item_name = "Omega Bait"
            content = f"I'll remind you when your **{item_name}** cooldown is over <t:{timestamp}:R>."
        else:
            content = f"I will remind you when your **{item_name}** expires <t:{timestamp}:R>."
            
        view = UnifiedReminderView(
            title="Item Reminder",
            text=content
        )
        await message.reply(view=view)

async def setup(bot):
    await bot.add_cog(ItemReminders(bot))
