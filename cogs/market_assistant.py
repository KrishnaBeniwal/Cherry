import discord
from discord.ext import commands
import re

DANK_MEMER_ID = 270904126974590976

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

class MarketAssistant(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.processed_messages = set()

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
        if message.id in self.processed_messages:
            return

        content = message.content or ""
        
        if message.components:
            for comp in message.components:
                try:
                    content += "\n" + str(comp.to_dict())
                except Exception:
                    content += "\n" + str(comp)

        match = re.search(r"Offer ID:\s*[\*\_]*([A-Z0-9]+)", content, re.IGNORECASE)
        if not match:
            return

        offer_id = match.group(1)
        self.processed_messages.add(message.id)

        try:
            await message.reply(f"`pls market accept {offer_id}`")
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(MarketAssistant(bot))
