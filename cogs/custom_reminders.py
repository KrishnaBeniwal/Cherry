import discord
from discord.ext import commands
from discord import app_commands
import time as time_module
import json
import datetime
import uuid
from core.database import db
import emojis
from core.time_utils import parse_duration, parse_time, parse_date, get_timezone, calculate_next_occurrence
from cogs.reminder_views import UnifiedReminderView
from emojis import REPLY, REPLY_CONT
import zoneinfo
from core.fuzzy import get_fuzzy_matches

class PaginatedReminderListView(discord.ui.LayoutView):
    def __init__(self, reminders, user_id):
        super().__init__(timeout=None)
        self.reminders = reminders
        self.user_id = user_id
        self.current_page = 0
        self.per_page = 5
        self.max_pages = max(1, (len(reminders) + self.per_page - 1) // self.per_page)
        
        self.btn_left = discord.ui.Button(emoji=discord.PartialEmoji.from_str(emojis.LEFT), style=discord.ButtonStyle.secondary, custom_id=f"remlist_prev_{user_id}")
        self.btn_left.callback = self.prev_page
        
        self.btn_refresh = discord.ui.Button(emoji=discord.PartialEmoji.from_str(emojis.REFRESH), style=discord.ButtonStyle.secondary, custom_id=f"remlist_refresh_{user_id}")
        self.btn_refresh.callback = self.refresh_page
        
        self.btn_right = discord.ui.Button(emoji=discord.PartialEmoji.from_str(emojis.RIGHT), style=discord.ButtonStyle.secondary, custom_id=f"remlist_next_{user_id}")
        self.btn_right.callback = self.next_page
        
        self.update_view()

    def update_view(self):
        self.clear_items()
        
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("### **Active Reminders**"))
        c.add_item(discord.ui.Separator())
        
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_rems = self.reminders[start_idx:end_idx]
        
        for rem in page_rems:
            try:
                extra = json.loads(rem['extra_data']) if rem['extra_data'] else {}
            except:
                extra = {}
                
            rem_type = rem['reminder_type']
            
            if rem_type == "custom":
                msg = extra.get('message') or "*No message*"
                rep_type = extra.get('repeat_type', 'none')
                series_id = extra.get('series_id', str(rem['id']))
                is_snoozed = extra.get('is_snoozed', False)
                snooze_url = extra.get('snooze_url')
                
                
                if is_snoozed and series_id == "SYSTEM_SNOOZE":
                    msg_lower = msg.lower()
                    sys_type = "System"
                    if "adventure" in msg_lower: sys_type = "Adventure"
                    elif "prestige" in msg_lower: sys_type = "Prestige"
                    elif "farm" in msg_lower: sys_type = "Farm"
                    elif "work" in msg_lower: sys_type = "Work"
                    elif "scratch" in msg_lower: sys_type = "Scratch"
                    elif "fish boost" in msg_lower: sys_type = "Fish Boosts"
                    elif "happy hour" in msg_lower: sys_type = "Happy Hour"
                    elif "arrived at" in msg_lower: sys_type = "Travel"
                    elif "giveaway" in msg_lower: sys_type = "Giveaway"
                    elif "expired" in msg_lower or "box" in msg_lower: sys_type = "Item"
                    elif "feed" in msg_lower or "hungry" in msg_lower: sys_type = "Pet"
                    
                    if snooze_url:
                        desc = f"{emojis.CHERRY_BOT} [{sys_type} Reminder Snooze]({snooze_url})\n"
                    else:
                        desc = f"{emojis.CHERRY_BOT} **{sys_type} Reminder Snooze**\n"
                else:
                    desc = f"{emojis.CHERRY_BOT} **ID: `{series_id}`** "
                    if is_snoozed and snooze_url:
                        desc += f"([Snoozed]({snooze_url})) "
                    desc += f"- {msg}\n"
                if rep_type != "none":
                    desc += f"{REPLY_CONT} Next: <t:{rem['target_time']}:R>\n"
                    rep_rem = extra.get('repeat_remaining', -1)
                    rem_txt = "forever" if rep_rem == -1 else f"{rep_rem} more times"
                    
                    if rep_type == "every":
                        interval = extra.get('repeat_interval', 0)
                        parts = []
                        if interval >= 86400: parts.append(f"{interval // 86400}d"); interval %= 86400
                        if interval >= 3600: parts.append(f"{interval // 3600}h"); interval %= 3600
                        if interval >= 60: parts.append(f"{interval // 60}m"); interval %= 60
                        if interval > 0 or not parts: parts.append(f"{interval}s")
                        dur_str = "".join(parts)
                        desc += f"{REPLY} Repeat every {dur_str} ({rem_txt})"
                    else:
                        desc += f"{REPLY} Repeat {rep_type} ({rem_txt})"
                else:
                    desc += f"{REPLY} Next: <t:{rem['target_time']}:R>\n"
                    desc = desc.strip()
            else:
                emoji = emojis.TIMER
                if rem_type == "scratch":
                    emoji = emojis.CAT_SCRATCH
                elif rem_type == "fish_boosts":
                    emoji = emojis.TRAUMA
                elif rem_type == "travel":
                    emoji = emojis.TRAUMA_JORM
                elif rem_type == "prestige":
                    emoji = emojis.RAT_DANCE
                
                pretty_type = rem_type.replace('_', ' ').title()
                if pretty_type.lower().startswith('item '):
                    pretty_type = pretty_type[5:]
                    
                desc = f"{emoji} **`{pretty_type}` reminder**\n"
                
                context_parts = []
                for k, v in extra.items():
                    if k not in ('is_snoozed', 'snooze_url', 'snooze_msg_id', 'snooze_channel_id', 'status_message_id'):
                        context_parts.append(f"{v}")
                        
                if context_parts:
                    desc += f"> {', '.join(context_parts)}\n"
                    
                desc += f"{REPLY} Next: <t:{rem['target_time']}:R>"
                
            c.add_item(discord.ui.TextDisplay(desc))
            c.add_item(discord.ui.Separator())
            
        c.add_item(discord.ui.TextDisplay(f"Page {self.current_page + 1} of {self.max_pages}"))
        self.add_item(c)
        
        row = discord.ui.ActionRow()
        self.btn_left.disabled = self.current_page == 0
        self.btn_right.disabled = self.current_page >= self.max_pages - 1
        
        row.add_item(self.btn_left)
        row.add_item(self.btn_refresh)
        row.add_item(self.btn_right)
        self.add_item(row)

    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not yours!", ephemeral=True)
            return
        self.current_page -= 1
        self.update_view()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not yours!", ephemeral=True)
            return
        self.current_page += 1
        self.update_view()
        await interaction.response.edit_message(view=self)

    async def refresh_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not yours!", ephemeral=True)
            return
            
        from core.database import db
        import time
        cursor = await db.pool.execute("SELECT * FROM reminders WHERE user_id = ? ORDER BY target_time ASC", (self.user_id,))
        rems = await cursor.fetchall()
        
        # Filter expired reminders.
        self.reminders = [r for r in rems if r['target_time'] >= int(time.time())]
        
        self.max_pages = max(1, (len(self.reminders) + self.per_page - 1) // self.per_page)
        if self.current_page >= self.max_pages:
            self.current_page = self.max_pages - 1
            
        self.update_view()
        await interaction.response.edit_message(view=self)


class CustomReminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    reminder_group = app_commands.Group(name="reminder", description="Manage custom reminders")
    
    @reminder_group.command(name="every", description="Set a reminder that triggers every X duration")
    @app_commands.describe(time="E.g. 10m, 1h30m, 2d", message="What to remind you about", repeat="Number of times to repeat (empty for infinite)")
    async def reminder_every(self, interaction: discord.Interaction, time: str, message: str, repeat: int = -1):
        try:
            interval = parse_duration(time)
        except ValueError as e:
            await interaction.response.send_message(f"{emojis.CROSS} {e}", ephemeral=True)
            return
            
        if repeat != -1 and repeat <= 0:
            await interaction.response.send_message(f"{emojis.CROSS} Repeat must be greater than 0.", ephemeral=True)
            return
            
        now = int(time_module.time())
        target_time = now + interval
        
        series_id = uuid.uuid4().hex[:6].upper()
        extra_data = {
            "series_id": series_id,
            "message": message,
            "repeat_type": "every",
            "repeat_interval": interval,
            "repeat_remaining": repeat - 1 if repeat > 0 else repeat,
            "base_target_time": target_time
        }
        
        await db.add_reminder(interaction.user.id, interaction.channel_id, "custom", target_time, extra_data)
        
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"### **Reminder Set**\nReminder ID : `{series_id}`"))
        c.add_item(discord.ui.Separator())
        
        body = ""
        if message:
            body += f"> {message}\n\n"
            
        body += f"Reminder set for <t:{target_time}:F> (<t:{target_time}:R>)"
            
        c.add_item(discord.ui.TextDisplay(body))
        
        view = discord.ui.LayoutView()
        view.add_item(c)
        await interaction.response.send_message(view=view)

    @reminder_group.command(name="at", description="Set a reminder that triggers at a specific time")
    @app_commands.describe(time="E.g. 6am, 18:00", message="What to remind you about", repeat="Repeat frequency", date_str="E.g. tomorrow, 25 June", timezone="Your timezone")
    @app_commands.choices(repeat=[
        app_commands.Choice(name="Daily", value="daily"),
        app_commands.Choice(name="Weekly", value="weekly"),
        app_commands.Choice(name="Monthly", value="monthly"),
    ])
    async def reminder_at(self, interaction: discord.Interaction, time: str, message: str, repeat: str = "none", date_str: str = "today", timezone: str = None):
        try:
            tz = get_timezone(timezone)
            parsed_time = parse_time(time)
            parsed_date = parse_date(date_str, tz)
        except ValueError as e:
            await interaction.response.send_message(f"{emojis.CROSS} {e}", ephemeral=True)
            return
            
        # Combine date and time.
        dt = datetime.datetime.combine(parsed_date, parsed_time, tzinfo=tz)
        target_time = int(dt.timestamp())
        now = int(time_module.time())
        
        if target_time <= now:
            if date_str == "today":
                # Push past times to tomorrow.
                dt += datetime.timedelta(days=1)
                target_time = int(dt.timestamp())
            else:
                await interaction.response.send_message(f"{emojis.CROSS} That time is in the past!", ephemeral=True)
                return
                
        series_id = uuid.uuid4().hex[:6].upper()
        extra_data = {
            "series_id": series_id,
            "message": message,
            "repeat_type": repeat,
            "repeat_interval": 0,
            "repeat_remaining": -1 if repeat != "none" else 0,
            "base_target_time": target_time
        }
        
        await db.add_reminder(interaction.user.id, interaction.channel_id, "custom", target_time, extra_data)
        
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"### **Reminder Set**\nReminder ID : `{series_id}`"))
        c.add_item(discord.ui.Separator())
        
        body = ""
        if message:
            body += f"> {message}\n\n"
            
        body += f"Reminder set for <t:{target_time}:F> (<t:{target_time}:R>)"
            
        c.add_item(discord.ui.TextDisplay(body))
        
        view = discord.ui.LayoutView()
        view.add_item(c)
        await interaction.response.send_message(view=view)
        
    @reminder_at.autocomplete("timezone")
    async def timezone_autocomplete(self, interaction: discord.Interaction, current: str):
        zones = list(zoneinfo.available_timezones())
        matches = get_fuzzy_matches(current, zones)
        return [app_commands.Choice(name=m, value=m) for m in matches[:25]]
        
    @reminder_group.command(name="list", description="List your active reminders")
    async def reminder_list(self, interaction: discord.Interaction):
        cursor = await db.pool.execute("SELECT * FROM reminders WHERE user_id = ? ORDER BY target_time ASC", (interaction.user.id,))
        reminders = await cursor.fetchall()
        
        import time
        reminders = [r for r in reminders if r['target_time'] >= int(time.time())]
        
        if not reminders:
            await interaction.response.send_message("You don't have any active reminders.", ephemeral=True)
            return
            
        view = PaginatedReminderListView(reminders, interaction.user.id)
        await interaction.response.send_message(view=view)
        
    @reminder_group.command(name="remove", description="Remove a specific reminder")
    @app_commands.describe(series_id="The ID of the reminder to remove (see /reminder list)")
    async def reminder_remove(self, interaction: discord.Interaction, series_id: str):
        cursor = await db.pool.execute("SELECT id, extra_data FROM reminders WHERE user_id = ? AND reminder_type = ?", (interaction.user.id, "custom"))
        reminders = await cursor.fetchall()
        
        deleted_count = 0
        for rem in reminders:
            try:
                extra = json.loads(rem['extra_data'])
                if extra.get('series_id') == series_id.upper() or str(rem['id']) == series_id:
                    await db.remove_reminder_by_id(rem['id'])
                    deleted_count += 1
            except:
                pass
                
        if deleted_count == 0:
            await interaction.response.send_message(f"{emojis.CROSS} Reminder not found or it doesn't belong to you.", ephemeral=True)
            return
            
        await interaction.response.send_message(f"{emojis.TICK} Removed reminder `{series_id.upper()}`.")

    @commands.Cog.listener("on_reminder_due")
    async def on_reminder_due(self, reminder_data: dict):
        if reminder_data.get("reminder_type") != "custom":
            return
            
        extra = reminder_data.get("extra_data", {})
        if not isinstance(extra, dict):
            extra = json.loads(extra) if extra else {}
            
        msg = extra.get("message")
        rep_type = extra.get("repeat_type", "none")
        user_id = reminder_data.get("user_id")
        channel_id = reminder_data.get("channel_id")
        rem_id = reminder_data.get("id")
        is_snoozed = extra.get("is_snoozed", False)
        series_id = extra.get("series_id", str(rem_id))
        
        user = self.bot.get_user(user_id)
        if not user:
            try:
                user = await self.bot.fetch_user(user_id)
            except:
                pass
                
        # Calculate next occurrence.
        next_id = None
        next_target = 0
        now = int(time_module.time())
        
        if rep_type != "none" and not is_snoozed:
            rep_rem = extra.get("repeat_remaining", -1)
            if rep_rem == -1 or rep_rem > 0:
                base_target = extra.get("base_target_time", reminder_data.get("target_time"))
                interval = extra.get("repeat_interval", 0)
                
                try:
                    next_target = calculate_next_occurrence(base_target, rep_type, interval)
                    
                    # Fast forward past missed triggers.
                    while next_target <= now:
                        next_target = calculate_next_occurrence(next_target, rep_type, interval)
                        
                    # Update reminder state.
                    next_extra = extra.copy()
                    if rep_rem > 0:
                        next_extra["repeat_remaining"] = rep_rem - 1
                    next_extra["base_target_time"] = next_target
                    
                    next_id = await db.add_reminder(user_id, channel_id, "custom", next_target, next_extra)
                except Exception as e:
                    print(f"Failed to calculate next occurrence for custom reminder: {e}")
                    
        # Send reminder.
        if user:
            title = extra.get("original_title", "Reminder")
            show_id = True
            if series_id == "SYSTEM_SNOOZE":
                show_id = False
                
            
            buttons = []
            buttons.append(discord.ui.Button(label="Snooze 5 Minutes", style=discord.ButtonStyle.secondary, emoji=discord.PartialEmoji.from_str(emojis.TIMER), custom_id=f"cus_snooze_{user_id}_{series_id}"))
            
            if next_target:
                buttons.append(discord.ui.Button(label="Cancel Reminder", style=discord.ButtonStyle.secondary, emoji=discord.PartialEmoji.from_str(emojis.CROSS), custom_id=f"cus_cancel_{user_id}_{series_id}"))
                
            final_msg = msg
            if series_id != "SYSTEM_SNOOZE":
                final_msg = "\n".join(f"> {line}" for line in msg.split("\n"))
                
            view = UnifiedReminderView(
                title=title, 
                text=final_msg,
                reminder_id=series_id if show_id else None,
                next_target=next_target, 
                buttons=buttons,
                snooze_url=extra.get('snooze_url')
            )
            
            snooze_channel = None
            if is_snoozed and "snooze_channel_id" in extra:
                snooze_channel = self.bot.get_channel(extra["snooze_channel_id"])
                
            kwargs = {"view": view}
            
            if snooze_channel:
                if "snooze_msg_id" in extra:
                    kwargs["reference"] = discord.MessageReference(
                        message_id=extra["snooze_msg_id"],
                        channel_id=extra["snooze_channel_id"],
                        fail_if_not_exists=False
                    )
                try:
                    await snooze_channel.send(**kwargs)
                except discord.Forbidden:
                    kwargs.pop("reference", None)
                    try:
                        await user.send(**kwargs)
                    except:
                        pass
            else:
                try:
                    await user.send(**kwargs)
                except discord.Forbidden:
                    if channel_id:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            try:
                                view.children[0].add_item(discord.ui.TextDisplay(content=f"<@{user_id}>, your reminder is due! (I couldn't DM you)"))
                                await channel.send(**kwargs)
                            except discord.Forbidden:
                                pass

async def setup(bot):
    await bot.add_cog(CustomReminders(bot))
