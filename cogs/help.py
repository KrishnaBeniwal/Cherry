import discord
from discord.ext import commands
from discord import app_commands
from emojis import CHERRY_BOT, TRAUMA_JORM, TRAUMA, BOT_TAG, INTRESTING, THINK, FLAME

# Important links.
INVITE_LINK = "https://discord.com/oauth2/authorize?client_id=1511268577058095195&permissions=8&integration_type=0&scope=bot+applications.commands"
SUPPORT_SERVER_LINK = "https://discord.gg/XTZKqZNq47"
TOP_GG_LINK = "https://top.gg/bot/123456789"
DBL_LINK = "https://discordbotlist.com/bots/123456789"
DISBOARD_LINK = "https://disboard.org/server/123456789"

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def generate_help_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{CHERRY_BOT} Cherry Bot Help",
            description=(
                f"**Important Links**\n"
                f"• [Invite Cherry to your server]({INVITE_LINK})\n"
                f"• [Cherry Support Server]({SUPPORT_SERVER_LINK})\n"
                f"• [Vote on Top.gg]({TOP_GG_LINK})\n"
                f"• [Vote on Discord Bot List]({DBL_LINK})\n"
                f"• [Review on Disboard]({DISBOARD_LINK})\n\n"
                f"**Commands**\n"
                f"Here are the main commands you can use with Cherry:"
            ),
            color=discord.Color.red()
        )

        embed.add_field(
            name=f"{TRAUMA_JORM} `/fish simulator`",
            value="Simulate fishing to see what you can catch with different combinations.",
            inline=False
        )
        embed.add_field(
            name=f"{TRAUMA} `/peak hour`",
            value="Check the peak hours for a specific fish, and find the best tools and locations.",
            inline=False
        )
        embed.add_field(
            name=f"{BOT_TAG} `/roleids`",
            value="Get the IDs of up to 5 roles at once in a copyable format.",
            inline=False
        )
        embed.add_field(
            name=f"{INTRESTING} `/server settings`",
            value="Configure role pings for server-wide events.",
            inline=False
        )
        embed.add_field(
            name=f"{INTRESTING} `/settings`",
            value="Configure your personal reminder and assistant settings.",
            inline=False
        )
        embed.add_field(
            name=f"{THINK} `/unscramble`",
            value="Unscramble a string of text to find Dank Memer items.",
            inline=False
        )
        embed.add_field(
            name=f"{FLAME} `/help`",
            value="Shows this help menu.",
            inline=False
        )
        
        embed.set_footer(text="Cherry Bot • Your ultimate Dank Memer companion!")
        return embed

    @commands.command(name="help")
    async def help_prefix(self, ctx):
        await ctx.reply(embed=self.generate_help_embed(), mention_author=False)

    @app_commands.command(name="help", description="Show the Cherry Bot help menu and important links")
    async def help_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self.generate_help_embed())

    @app_commands.command(name="privacy", description="View the bot's Terms of Service and Privacy Policy.")
    async def privacy_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📜 Privacy Policy & Terms of Service",
            description="You can read our full Terms of Service and Privacy Policy here:\n\n🔗 [Cherry Bot TOS & Privacy](https://dynam2009.github.io/cherry-the-bot/)",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    # Remove default help command.
    bot.remove_command("help")
    await bot.add_cog(Help(bot))
