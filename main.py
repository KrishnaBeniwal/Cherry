import discord
from discord.ext import commands
import os
import json
import asyncio
from dotenv import load_dotenv

# Load the bot token.
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

PREFIX = ("cherry ", "Cherry ")

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
bot.remove_command('help')

TOS_FILE = os.path.join(os.path.dirname(__file__), "agreed_tos.json")
if not os.path.exists(TOS_FILE):
    with open(TOS_FILE, "w") as f:
        json.dump([], f)

with open(TOS_FILE, "r") as f:
    try:
        agreed_users = set(json.load(f))
    except:
        agreed_users = set()

async def check_tos(interaction: discord.Interaction) -> bool:
    # Enforce ToS for slash commands only.
    if interaction.type != discord.InteractionType.application_command:
        return True
        
    user_id = str(interaction.user.id)
    if user_id not in agreed_users:
        agreed_users.add(user_id)
        with open(TOS_FILE, "w") as f:
            json.dump(list(agreed_users), f)
        
        embed = discord.Embed(
            title="📜 Terms of Service & Privacy Policy",
            description="Welcome to Cherry Bot!\n\nBy continuing to use this bot, you acknowledge and agree to our [Terms of Service & Privacy Policy](https://dynam2009.github.io/cherry-the-bot/).",
            color=discord.Color.red()
        )
        
        async def send_followup():
            for _ in range(100):
                if interaction.response.is_done():
                    break
                await asyncio.sleep(0.1)
                
            # Wait for Discord to process the initial response.
            await asyncio.sleep(1.5)
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                print(f"ToS Followup Error: {e}")
                
        bot.loop.create_task(send_followup())
        
    return True

bot.tree.interaction_check = check_tos

@bot.check
async def check_tos_prefix(ctx: commands.Context) -> bool:
    user_id = str(ctx.author.id)
    if user_id not in agreed_users:
        agreed_users.add(user_id)
        with open(TOS_FILE, "w") as f:
            json.dump(list(agreed_users), f)
            
        embed = discord.Embed(
            title="📜 Terms of Service & Privacy Policy",
            description="Welcome to Cherry Bot!\n\nBy continuing to use this bot, you acknowledge and agree to our [Terms of Service & Privacy Policy](https://dynam2009.github.io/cherry-the-bot/).",
            color=discord.Color.red()
        )
        
        async def send_reply():
            await asyncio.sleep(1.5)
            try:
                await ctx.reply(embed=embed, mention_author=True)
            except Exception:
                pass
                
        bot.loop.create_task(send_reply())
        
    return True

EXCLUDED_SERVER_ID = 1438233304867278870

@bot.event
async def setup_hook():
    # Initialize database and scheduler.
    from core.database import db
    from core.scheduler import init_scheduler
    from core.migration import run_migration
    
    await db.initialize()
    await run_migration()
    scheduler = init_scheduler(bot)
    scheduler.start()

    await bot.load_extension("cogs.roles")
    await bot.load_extension("cogs.channels")
    await bot.load_extension("cogs.fishing")
    await bot.load_extension("cogs.server_reminders")
    await bot.load_extension("cogs.work_reminders")
    await bot.load_extension("cogs.adventure_reminders")
    await bot.load_extension("cogs.custom_reminders")
    await bot.load_extension("cogs.travel_reminders")
    await bot.load_extension("cogs.prestige_reminders")
    await bot.load_extension("cogs.help")
    await bot.load_extension("cogs.farm_reminders")
    await bot.load_extension("cogs.pet_reminders")
    await bot.load_extension("cogs.giveaway_reminders")
    await bot.load_extension("cogs.market_assistant")
    await bot.load_extension("cogs.dmreminders")
    await bot.load_extension("cogs.daily_reminders")
    await bot.load_extension("cogs.utils")
    await bot.load_extension("cogs.settings")
    await bot.load_extension("cogs.item_reminders")
    await bot.load_extension("cogs.persistent_views")
    await bot.load_extension("cogs.stream_reminders")
    
    settings_cog = bot.get_cog("Settings")
    if settings_cog:
        for v in settings_cog.get_persistent_views():
            bot.add_view(v)
            
    v = discord.ui.View(timeout=None)
    from cogs.work_reminders import ToggleButton
    from cogs.adventure_reminders import ToggleAdventureButton
    from cogs.travel_reminders import ToggleTravelButton
    from cogs.prestige_reminders import TogglePrestigeButton
    from cogs.farm_reminders import ToggleFarmButton
    from cogs.giveaway_reminders import ToggleGiveawayButton
    from cogs.pet_reminders import TogglePetButton
    from cogs.stream_reminders import ToggleStreamButton
    
    v.add_item(ToggleButton())
    v.add_item(ToggleAdventureButton())
    v.add_item(ToggleTravelButton())
    v.add_item(TogglePrestigeButton())
    v.add_item(ToggleFarmButton())
    v.add_item(ToggleGiveawayButton())
    v.add_item(TogglePetButton())
    v.add_item(ToggleStreamButton())
    bot.add_view(v)

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        await bot.tree.sync(guild=discord.Object(id=EXCLUDED_SERVER_ID))
    except Exception:
        pass

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

if __name__ == "__main__":
    bot.run(os.getenv('BOT_TOKEN'))
