import discord
from discord.ext import commands, tasks
import datetime
from emojis import CAT_SCRATCH, TRAUMA

SCRATCH_TIMES = [
    datetime.time(hour=h, minute=0, tzinfo=datetime.timezone.utc)
    for h in range(0, 24, 3)
]

FISH_BOOST_TIMES = [
    datetime.time(hour=0, minute=0, tzinfo=datetime.timezone.utc),
    datetime.time(hour=4, minute=0, tzinfo=datetime.timezone.utc),
    datetime.time(hour=8, minute=0, tzinfo=datetime.timezone.utc),
    datetime.time(hour=12, minute=0, tzinfo=datetime.timezone.utc),
    datetime.time(hour=16, minute=0, tzinfo=datetime.timezone.utc),
    datetime.time(hour=20, minute=0, tzinfo=datetime.timezone.utc),
    datetime.time(hour=20, minute=0, tzinfo=datetime.timezone.utc),
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

def get_next_scratch_occurrence() -> int:
    now = datetime.datetime.now(datetime.timezone.utc)
    # Get next scratch hour or next day.
    hours = [0, 3, 6, 9, 12, 15, 18, 21]
    
    for h in hours:
        target = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if target > now:
            return int(target.timestamp())
            
    target = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    return int(target.timestamp())

def get_hh_end(is_pm: bool) -> int:
    now = datetime.datetime.now(datetime.timezone.utc)
    hour = 17 if is_pm else 5
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target < now - datetime.timedelta(hours=1):
        target += datetime.timedelta(days=1)
    return int(target.timestamp())

class DMReminders(commands.Cog):
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

    async def _dispatch_dm(self, setting_key: str, text: str):
        settings_cog = self.bot.get_cog("Settings")
        if not settings_cog:
            return
            
        data = settings_cog._get_json_data()
        
        for user_id_str, user_settings in data.items():
            if user_settings.get(setting_key, False):
                try:
                    user_id = int(user_id_str)
                    user = self.bot.get_user(user_id)
                    if not user:
                        try:
                            user = await self.bot.fetch_user(user_id)
                        except Exception:
                            continue
                            
                    view = discord.ui.LayoutView()
                    c = discord.ui.Container()
                    title = "Scratch" if setting_key == "scratch_reminder" else "Fish Boosts" if setting_key == "fish_boosts" else "Happy Hour"
                    c.add_item(discord.ui.TextDisplay(content=f"### **{title} Reminder**"))
                    c.add_item(discord.ui.Separator())
                    c.add_item(discord.ui.TextDisplay(content=text))
                    view.add_item(c)
                    from cogs.reminder_views import SnoozeReminderButton
                    ar = discord.ui.ActionRow()
                    ar.add_item(SnoozeReminderButton(user_id=int(user_id_str), original_text=text))
                    c.add_item(discord.ui.Separator())
                    c.add_item(ar)
                    
                    await user.send(view=view)
                except Exception:
                    pass

    @tasks.loop(time=SCRATCH_TIMES)
    async def scratch_task(self):
        next_ts = get_next_scratch_occurrence()
        text = f"Its time you can scratch again {CAT_SCRATCH}\n\nNext scratch <t:{next_ts}:R> {CAT_SCRATCH} "
        await self._dispatch_dm("scratch_reminder", text)

    @tasks.loop(time=HH_PM_TIMES)
    async def hh_pm_task(self):
        end_ts = get_hh_end(is_pm=True)
        text = f"### **Happy Hour is live now**\n\n > Ending <t:{end_ts}:R>"
        await self._dispatch_dm("happy_hour_reminder", text)

    @tasks.loop(time=HH_AM_TIMES)
    async def hh_am_task(self):
        end_ts = get_hh_end(is_pm=False)
        text = f"### **Happy Hour is live now**\n\n > Ending <t:{end_ts}:R>"
        await self._dispatch_dm("happy_hour_reminder", text)

    @tasks.loop(time=FISH_BOOST_TIMES)
    async def fish_boost_task(self):
        text = f"## Its time to check new Fih Boosts {TRAUMA}\n\n### > </fish boosts:1011560371078832206>"
        await self._dispatch_dm("fish_boost_reminder", text)

    @scratch_task.before_loop
    @hh_pm_task.before_loop
    @hh_am_task.before_loop
    @fish_boost_task.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(DMReminders(bot))
