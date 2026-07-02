import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import emojis
from core.database import db

SCRATCH_TIMES = [
    datetime.time(hour=h, minute=0, tzinfo=datetime.timezone.utc)
    for h in range(0, 24, 3)
]

HH_PM_TIMES = [
    datetime.time(hour=16, minute=0, tzinfo=datetime.timezone.utc),  # 9:30 PM IST
    datetime.time(hour=16, minute=30, tzinfo=datetime.timezone.utc), # 10:00 PM IST
    datetime.time(hour=16, minute=50, tzinfo=datetime.timezone.utc), # 10:20 PM IST
]

HH_AM_TIMES = [
    datetime.time(hour=4, minute=0, tzinfo=datetime.timezone.utc),  # 9:30 AM IST
    datetime.time(hour=4, minute=30, tzinfo=datetime.timezone.utc), # 10:00 AM IST
    datetime.time(hour=4, minute=50, tzinfo=datetime.timezone.utc), # 10:20 AM IST
]

FISH_BOOST_TIMES = [
    datetime.time(hour=0, minute=0, tzinfo=datetime.timezone.utc),
    datetime.time(hour=4, minute=0, tzinfo=datetime.timezone.utc),
    datetime.time(hour=8, minute=0, tzinfo=datetime.timezone.utc),
    datetime.time(hour=12, minute=0, tzinfo=datetime.timezone.utc),
    datetime.time(hour=16, minute=0, tzinfo=datetime.timezone.utc),
    datetime.time(hour=20, minute=0, tzinfo=datetime.timezone.utc),
]

def get_next_occurrence(times_list):
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()
    
    candidates = []
    for t in times_list:
        dt = datetime.datetime.combine(today, t, tzinfo=datetime.timezone.utc)
        if dt <= now:
            dt += datetime.timedelta(days=1)
        candidates.append(dt)
        
    next_time = min(candidates)
    return int(next_time.timestamp())

def get_next_scratch_occurrence():
    return get_next_occurrence(SCRATCH_TIMES)

def get_next_hh_occurrence(is_pm=True):
    return get_next_occurrence(HH_PM_TIMES if is_pm else HH_AM_TIMES)

def get_next_fish_boost_occurrence():
    return get_next_occurrence(FISH_BOOST_TIMES)

def get_hh_end(is_pm: bool) -> int:
    now = datetime.datetime.now(datetime.timezone.utc)
    hour = 17 if is_pm else 5
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target < now - datetime.timedelta(hours=1):
        target += datetime.timedelta(days=1)
    return int(target.timestamp())

class ServerReminderToggle(discord.ui.Button):
    def __init__(self, key: str, is_on: bool, page: int):
        self.key = key
        self.page = page
        
        title_map = {
            "scratch": "Scratch",
            "fish_boosts": "Fish Boosts",
            "happy_hour_pm": "Happy Hour PM",
            "happy_hour_am": "Happy Hour AM"
        }
        
        super().__init__(
            style=discord.ButtonStyle.primary if is_on else discord.ButtonStyle.secondary,
            label=f"{title_map.get(key, key)} On/Off",
            custom_id=f"sr_toggle_{key}"
        )

    async def callback(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        row = await db.get_server_setting(guild_id, self.key)
        enabled = not (row['enabled'] if row else False)
        role_id = row['role_id'] if row else None
        channel_id = row['channel_id'] if row else interaction.channel_id
        
        await db.set_server_setting(guild_id, self.key, enabled, role_id, channel_id)
        view = await build_server_reminders_view(interaction.guild_id, self.page)
        await interaction.response.edit_message(view=view)


class ServerReminderRoleSelect(discord.ui.RoleSelect):
    def __init__(self, key: str, page: int):
        self.key = key
        self.page = page
        title_map = {
            "scratch": "Scratch",
            "fish_boosts": "Fish Boosts",
            "happy_hour_pm": "Happy Hour PM",
            "happy_hour_am": "Happy Hour AM"
        }
        super().__init__(
            placeholder=f"Select {title_map.get(key, key)} Ping Role",
            min_values=1, max_values=1,
            custom_id=f"sr_role_{key}"
        )

    async def callback(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        row = await db.get_server_setting(guild_id, self.key)
        enabled = row['enabled'] if row else False
        role_id = self.values[0].id
        channel_id = row['channel_id'] if row else interaction.channel_id
        
        await db.set_server_setting(guild_id, self.key, enabled, role_id, channel_id)
        view = await build_server_reminders_view(interaction.guild_id, self.page)
        await interaction.response.edit_message(view=view)


class ServerReminderChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, key: str, page: int):
        self.key = key
        self.page = page
        title_map = {
            "scratch": "Scratch",
            "fish_boosts": "Fish Boosts",
            "happy_hour_pm": "Happy Hour PM",
            "happy_hour_am": "Happy Hour AM"
        }
        super().__init__(
            placeholder=f"Select {title_map.get(key, key)} Ping Channel",
            channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1,
            custom_id=f"sr_chan_{key}"
        )

    async def callback(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        row = await db.get_server_setting(guild_id, self.key)
        enabled = row['enabled'] if row else False
        role_id = row['role_id'] if row else None
        channel_id = self.values[0].id
        
        await db.set_server_setting(guild_id, self.key, enabled, role_id, channel_id)
        view = await build_server_reminders_view(interaction.guild_id, self.page)
        await interaction.response.edit_message(view=view)


class ServerReminderNavButton(discord.ui.Button):
    def __init__(self, direction: str, page: int, disabled: bool):
        self.direction = direction
        self.page = page
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=emojis.LEFT if direction == "prev" else emojis.RIGHT,
            disabled=disabled,
            custom_id=f"sr_nav_{direction}_{page}"
        )

    async def callback(self, interaction: discord.Interaction):
        new_page = self.page - 1 if self.direction == "prev" else self.page + 1
        view = await build_server_reminders_view(interaction.guild_id, new_page)
        await interaction.response.edit_message(view=view)


async def build_server_reminders_view(guild_id: int, page: int) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=None)
    c = discord.ui.Container()
    
    c.add_item(discord.ui.TextDisplay(
        f"## **Server Reminders (Page {page + 1}/2)**\nPing roles for server events"
    ))
    c.add_item(discord.ui.Separator())
    
    if page == 0:
        events = [
            ("scratch", "Scratch", get_next_scratch_occurrence()),
            ("fish_boosts", "Fish Boosts", get_next_fish_boost_occurrence())
        ]
    else:
        events = [
            ("happy_hour_pm", "Happy Hour (4 PM)", get_next_hh_occurrence(is_pm=True)),
            ("happy_hour_am", "Happy Hour (4 AM)", get_next_hh_occurrence(is_pm=False))
        ]
        
    for i, (key, title, next_ts) in enumerate(events):
        row = None
        if guild_id:
            row = await db.get_server_setting(guild_id, key)
            
        is_on = row['enabled'] if row else False
        role_id = row['role_id'] if row else None
        channel_id = row['channel_id'] if row else None
        
        status_text = f"On {emojis.TICK}" if is_on else f"Off {emojis.CROSS}"
        role_text = f"<@&{role_id}>" if role_id else "None"
        chan_text = f"<#{channel_id}>" if channel_id else "None"
        
        content = (
            f"**{title}**\n"
            f"Next occurrence: <t:{next_ts}:F>\n"
            f"Status: {status_text}\n"
            f"Role: {role_text}\n"
            f"Channel: {chan_text}"
        )
        c.add_item(discord.ui.TextDisplay(content))
        
        btn_row = discord.ui.ActionRow()
        btn_row.add_item(ServerReminderToggle(key, is_on, page))
        c.add_item(btn_row)
        
        role_row = discord.ui.ActionRow()
        role_row.add_item(ServerReminderRoleSelect(key, page))
        c.add_item(role_row)
        
        chan_row = discord.ui.ActionRow()
        chan_row.add_item(ServerReminderChannelSelect(key, page))
        c.add_item(chan_row)
        
        if i < len(events) - 1:
            c.add_item(discord.ui.Separator())
            
    # Add navigation buttons.
    nav_row = discord.ui.ActionRow()
    nav_row.add_item(ServerReminderNavButton("prev", page, page == 0))
    nav_row.add_item(ServerReminderNavButton("next", page, page == 1))
    c.add_item(nav_row)
    
    view.add_item(c)
    return view


class ServerReminders(commands.Cog):
    server_group = app_commands.Group(name="server", description="Server configuration commands")

    def __init__(self, bot):
        self.bot = bot
        self.scratch_task.start()
        self.hh_pm_task.start()
        self.hh_am_task.start()
        self.fish_boost_task.start()

    def cog_unload(self):
        self.scratch_task.cancel()
        self.hh_pm_task.cancel()
        self.hh_am_task.cancel()
        self.fish_boost_task.cancel()

    @server_group.command(name="settings", description="Configure role pings for server-wide events.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def server_settings_slash(self, interaction: discord.Interaction):
        view = await build_server_reminders_view(interaction.guild_id, 0)
        await interaction.response.send_message(view=view, ephemeral=False)

    async def _trigger_event(self, event_key):
        rows = await db.get_all_server_settings()
        for row in rows:
            if row['event_key'] != event_key: continue
            if row['enabled'] and row['role_id'] and row['channel_id']:
                channel = self.bot.get_channel(row['channel_id'])
                if not channel:
                    continue
                    
                role_id = row['role_id']
                text = ""
                if event_key == "scratch":
                    text = f"it's time to </scratch:1011560371267579934>"
                elif event_key == "fish_boosts":
                    text = f"## Its time to check new Fish Boosts <:Trauma:1512747137614610574>\n### > </fish boosts:1011560371078832206>"
                elif event_key in ["happy_hour_pm", "happy_hour_am"]:
                    is_pm = (event_key == "happy_hour_pm")
                    end_ts = get_hh_end(is_pm=is_pm)
                    text = f"### **Happy Hour is live now**\n\n > Ending <t:{end_ts}:R>"
                    
                from cogs.reminder_views import UnifiedReminderView
                view = UnifiedReminderView(
                    title="Server Reminder",
                    text=f"<@&{role_id}>\n{text}"
                )
                    
                try:
                    await channel.send(view=view)
                except Exception as e:
                    print(f"[SERVER REMINDERS] Failed to send {event_key}: {e}")

    @tasks.loop(time=SCRATCH_TIMES)
    async def scratch_task(self):
        await self._trigger_event("scratch")

    @tasks.loop(time=HH_PM_TIMES)
    async def hh_pm_task(self):
        await self._trigger_event("happy_hour_pm")

    @tasks.loop(time=HH_AM_TIMES)
    async def hh_am_task(self):
        await self._trigger_event("happy_hour_am")

    @tasks.loop(time=FISH_BOOST_TIMES)
    async def fish_boost_task(self):
        await self._trigger_event("fish_boosts")

    @scratch_task.before_loop
    @hh_pm_task.before_loop
    @hh_am_task.before_loop
    @fish_boost_task.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    cog = ServerReminders(bot)
    await bot.add_cog(cog)
    # Register dummy views for persistent UI.
    view_page_0 = await build_server_reminders_view(None, 0)
    view_page_1 = await build_server_reminders_view(None, 1)
    bot.add_view(view_page_0)
    bot.add_view(view_page_1)
