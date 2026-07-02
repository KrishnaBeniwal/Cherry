import discord
from discord.ext import commands
from discord import app_commands
from core.fuzzy import fuzzy_find
import emojis

def parse_color(color_str: str) -> discord.Color:
    if not color_str:
        return discord.Color.default()
        
    color_str = color_str.strip().lower()
    
    if hasattr(discord.Color, color_str) and callable(getattr(discord.Color, color_str)):
        try:
            return getattr(discord.Color, color_str)()
        except:
            pass
            
    if color_str.startswith('#'):
        color_str = color_str[1:]
    
    if len(color_str) == 6:
        try:
            return discord.Color(int(color_str, 16))
        except ValueError:
            pass
            
    if ',' in color_str:
        parts = color_str.replace('(', '').replace(')', '').split(',')
        if len(parts) == 3:
            try:
                r, g, b = [int(p.strip()) for p in parts]
                return discord.Color.from_rgb(r, g, b)
            except ValueError:
                pass
                
    return discord.Color.default()

class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(name="roleids", aliases=["giveroleid", "roleid"])
    async def roleids_prefix(self, ctx, *, roles_data: str):
        role_names = [r.strip().lower() for r in roles_data.split(',')]
        found_roles = []
        
        for r_name in role_names:
            if not r_name: continue
            
            r_id = None
            if r_name.startswith('<@&') and r_name.endswith('>'):
                try:
                    r_id = int(r_name[3:-1])
                except: pass
            elif r_name.isdigit():
                r_id = int(r_name)
                
            role = None
            if r_id:
                role = ctx.guild.get_role(r_id)
                
            if not role:
                role = discord.utils.find(lambda r: r.name.lower() == r_name, ctx.guild.roles)
                
            if not role:
                # Fallback to fuzzy matching.
                guild_role_names = [r.name for r in ctx.guild.roles]
                best_match = fuzzy_find(r_name, guild_role_names)
                if best_match:
                    role = discord.utils.find(lambda r: r.name == best_match, ctx.guild.roles)
                
            if role and role not in found_roles:
                found_roles.append(role)
                
        if not found_roles:
            await ctx.reply(f"{emojis.CROSS} Could not find any roles matching your input.", mention_author=False)
            return
            
        response = "\n".join([f"{role.name}: {role.id}" for role in found_roles])
        await ctx.reply(f"**Role IDs:**\n```\n{response}\n```", mention_author=False)

    @app_commands.command(name="roleids", description="Get the IDs of up to 5 roles at once in a copyable format")
    @app_commands.describe(role1="First role", role2="Second role (optional)", role3="Third role (optional)", role4="Fourth role (optional)", role5="Fifth role (optional)")
    async def roleids_slash(self, interaction: discord.Interaction, role1: discord.Role, role2: discord.Role = None, role3: discord.Role = None, role4: discord.Role = None, role5: discord.Role = None):
        roles = [r for r in [role1, role2, role3, role4, role5] if r is not None]
        
        response = "\n".join([f"{role.name}: {role.id}" for role in roles])
        await interaction.response.send_message(f"**Role IDs:**\n```\n{response}\n```", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Roles(bot))
