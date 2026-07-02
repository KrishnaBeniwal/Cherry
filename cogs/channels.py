import discord
from discord.ext import commands

DANK_MEMER_ID = 270904126974590976
EXCLUDED_SERVER_ID = 1438233304867278870

ALLOWED_USER_IDS = frozenset({
    1379896339189596342,
    853877922666512384,
    483217929177923585,
    957609809794977804,
    951119258979532820,
    1447906044029435945,
    1472012262217617418,
    1416771785348747384,
    955802095276138576
})

PRIVATE_CHANNEL_NAMES = frozenset({"pvt1", "pvt2", "pvt3"})

class Channels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Ignore excluded server.
        if guild.id == EXCLUDED_SERVER_ID:
            return
            
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            discord.Object(id=DANK_MEMER_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        for uid in ALLOWED_USER_IDS:
            overwrites[discord.Object(id=uid)] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        for name in PRIVATE_CHANNEL_NAMES:
            try:
                await guild.create_text_channel(name, overwrites=overwrites)
            except discord.Forbidden:
                pass
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id == EXCLUDED_SERVER_ID:
            return
            
        if member.id in ALLOWED_USER_IDS:
            for channel in member.guild.text_channels:
                if channel.name in PRIVATE_CHANNEL_NAMES:
                    try:
                        await channel.set_permissions(member, read_messages=True, send_messages=True)
                    except discord.Forbidden:
                        pass
                    except Exception:
                        pass


async def setup(bot):
    await bot.add_cog(Channels(bot))
