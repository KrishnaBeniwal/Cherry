import discord
from discord.ext import commands
from discord import app_commands
from dank_data import ANAGRAM_KNOWLEDGE
import os
import json
import time

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_settings.json")
class SettingsManager:
    def __init__(self):
        self.data = {}
        self.last_saved = 0
        self.dirty = False
        self.load()

    def load(self):
        if not os.path.exists(SETTINGS_FILE):
            self.data = {}
            return
        try:
            with open(SETTINGS_FILE, "r") as f:
                self.data = json.load(f)
        except Exception:
            self.data = {}

    def save(self, force=False):
        if not self.dirty and not force:
            return
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.data, f, indent=4)
            self.dirty = False
            self.last_saved = time.time()
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get_data(self):
        return self.data

    def set_data(self, new_data):
        self.data = new_data
        self.dirty = True
        if time.time() - self.last_saved > 2:
            self.save()

settings_manager = SettingsManager()



class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def do_unscramble(self, text: str):
        sorted_scramble = "".join(sorted(text.lower().replace(" ", "")))
        if sorted_scramble in ANAGRAM_KNOWLEDGE:
            return ANAGRAM_KNOWLEDGE[sorted_scramble]
        return None

    @commands.command(name="unscramble")
    async def unscramble_prefix(self, ctx, *, text: str):
        """Unscrambles a string of text to find Dank Memer items."""
        ans = self.do_unscramble(text)
        if ans:
            await ctx.reply(f"Unscrambled: `{ans}`", mention_author=False)
        else:
            await ctx.reply("Could not find a matching item in the database for those letters.", mention_author=False)

    @app_commands.command(name="unscramble", description="Unscramble a string of text to find Dank Memer items")
    @app_commands.describe(text="The scrambled text to solve")
    async def unscramble_slash(self, interaction: discord.Interaction, text: str):
        ans = self.do_unscramble(text)
        if ans:
            await interaction.response.send_message(f"Unscrambled: `{ans}`")
        else:
            await interaction.response.send_message("Could not find a matching item in the database for those letters.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Utils(bot))
