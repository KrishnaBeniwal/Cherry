import discord
from discord.ext import commands
from discord import app_commands
import json
import datetime
import os
import emojis
import functools

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FISH_PEAK_PATH = os.path.join(BASE_DIR, "fish_peak.json")
FISH_LOOKUP_PATH = os.path.join(BASE_DIR, "fish_lookup.json")

def load_json(filepath):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load {filepath}: {e}")
        return {}

fish_peak = load_json(FISH_PEAK_PATH)
fish_lookup = load_json(FISH_LOOKUP_PATH)

LOCATION_NAMES = {
    "deep-ocean": "Underwater Sanctuary",
    "lake": "Camp Guillermo",
    "pond": "Mystic Pond",
    "shallow-ocean": "Vertigo Beach",
    "river": "Wily River",
    "scurvy-waters": "Scurvy Waters"
}

FISH_KEYS = list(fish_peak.keys())
LOCATION_KEYS = list(LOCATION_NAMES.keys())
TOOLS = ["bare-hand", "dynamite", "fishing-bow", "fishing-rod", "harpoon", "net"]
BAITS = ["none", "lucky-bait", "deadly-bait", "deadly-bait+lucky-bait"]

from core.fuzzy import get_fuzzy_matches as _get_fuzzy_matches, fuzzy_find as _fuzzy_find

def get_fuzzy_matches(query, options):
    return _get_fuzzy_matches(query, options, format_name)

def fuzzy_find(query, options):
    return _fuzzy_find(query, options, format_name)

@functools.lru_cache(maxsize=1024)
def format_name(name):
    if not name:
        return "None"
    name_lower = name.lower()
    if name_lower in LOCATION_NAMES:
        return LOCATION_NAMES[name_lower]
    return name.title().replace("-", " ")

def unformat_name(formatted):
    if not formatted:
        return "none"
    formatted_lower = formatted.lower()
    for raw, fmt in LOCATION_NAMES.items():
        if fmt.lower() == formatted_lower:
            return raw
    if formatted.lower() == "none":
        return "none"
    return formatted.lower().replace(" ", "-")

def to_choices(matches):
    choices = []
    seen = set()
    for m in matches:
        name = format_name(m)
        if name not in seen:
            seen.add(name)
            choices.append(app_commands.Choice(name=name, value=m))
    return choices




def generate_peak_embed(fish, location, tool, bait):
    emoji = emojis.FISH_EMOJIS.get(fish.lower(), "🐟")
    embed = discord.Embed(title=f"{emoji} Peak Hours - {format_name(fish)}", color=discord.Color.green())
    desc = f"**Location:** {format_name(location)}\n"
    desc += f"**Tool:** {format_name(tool)}\n"
    desc += f"**Bait:** {'None' if bait == 'none' else format_name(bait)}\n\n"
    
    data = fish_peak.get(fish, {}).get(location, {}).get(tool, {}).get(bait, {})
    footer_text = f"⚙️ State: {format_name(fish)} • {format_name(location)} • {format_name(tool)} • {'None' if bait == 'none' else format_name(bait)}"
    
    if not data:
        embed.description = desc + "No data found for this combination."
        embed.set_footer(text=footer_text)
        return embed
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    current_hour = now_utc.hour
    
    max_chance = max((float(c) for c in data.values()), default=0)
    
    lines = []
    for h in range(24):
        c = float(data.get(str(h), 0))
        base_date = now_utc.replace(minute=0, second=0, microsecond=0, hour=h)
        ts = int(base_date.timestamp())
        
        line = f"<t:{ts}:t> — `{c:.3f}%`"
        is_peak = c > 0 and abs(c - max_chance) < 1e-6
        is_current = h == current_hour
        
        if is_peak and is_current:
            line += " (peak)(current)"
        elif is_peak:
            line += " (peak)"
        elif is_current:
            line += " (current)"
            
        lines.append(line)
            
    embed.description = desc + "\n".join(lines)
    embed.set_footer(text=footer_text)
    return embed

def generate_simulator_embed(location, tool, bait, time):
    time_str = str(time)
    fish_chances = fish_lookup.get(location, {}).get(tool, {}).get(bait, {}).get(time_str, {})
    
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    base_date = now_utc.replace(minute=0, second=0, microsecond=0, hour=time)
    
    embed = discord.Embed(title=f"{emojis.TRAUMA} Fish Simulator", color=discord.Color.green())
    desc = f"**Location:** {format_name(location)}\n"
    desc += f"**Tool:** {format_name(tool)}\n"
    desc += f"**Bait:** {'None' if bait == 'none' else format_name(bait)}\n"
    desc += f"**Time:** {time:02d}:00 UTC (<t:{int(base_date.timestamp())}:t>)\n\n"
    
    footer_text = f"⚙️ State: {format_name(location)} • {format_name(tool)} • {'None' if bait == 'none' else format_name(bait)} • {time}"
    
    if not fish_chances:
        embed.description = desc + "No fish can be caught with this combination."
        embed.set_footer(text=footer_text)
        return embed
        
    sorted_fish = sorted(fish_chances.items(), key=lambda x: float(x[1]), reverse=True)
    fish_lines = []
    for f, c in sorted_fish[:25]:
        emoji = emojis.FISH_EMOJIS.get(f.lower(), "🐟")
        fish_lines.append(f"`{float(c):.3f}%` - {emoji} {format_name(f)}")
        
    embed.description = desc + "\n".join(fish_lines)
    if len(sorted_fish) > 25:
        footer_text = f"Showing top 25 out of {len(sorted_fish)} fish.\n" + footer_text
        
    embed.set_footer(text=footer_text)
    return embed

class PeakHourSelect(discord.ui.Select):
    def __init__(self, row, options, select_type):
        self.select_type = select_type
        super().__init__(options=options, row=row)
        
    async def callback(self, interaction: discord.Interaction):
        view: PeakHourView = self.view
        val = self.values[0]
        if self.select_type == "location": 
            view.location = val
        elif self.select_type == "tool": 
            view.tool = val
            valid_baits = get_valid_baits(view.tool)
            if view.bait not in valid_baits:
                view.bait = "none"
        elif self.select_type == "bait": 
            view.bait = val
            
        embed = generate_peak_embed(view.fish, view.location, view.tool, view.bait)
        new_view = PeakHourView(view.fish, view.location, view.tool, view.bait, view.author_id)
        await interaction.response.edit_message(embed=embed, view=new_view)

class PeakBestToolButton(discord.ui.Button):
    def __init__(self, row):
        super().__init__(style=discord.ButtonStyle.primary, label="Best Tool", row=row)
        
    async def callback(self, interaction: discord.Interaction):
        view: PeakHourView = self.view
        
        tool_maxes = {}
        fish_data = fish_peak.get(view.fish, {})
        for l, l_data in fish_data.items():
            for t, t_data in l_data.items():
                for b, b_data in t_data.items():
                    mx = max((float(c) for c in b_data.values()), default=-1)
                    if mx > tool_maxes.get(t, -1):
                        tool_maxes[t] = mx
                        
        valid_tools = {t: m for t, m in tool_maxes.items() if m > 0}
        if not valid_tools:
            return await interaction.response.send_message("No tools available for this fish.", ephemeral=True)
            
        sorted_tools = sorted(valid_tools.items(), key=lambda x: x[1], reverse=True)
        
        desc = ""
        for i, (t, mx) in enumerate(sorted_tools, 1):
            desc += f"{i}. {format_name(t)} — `{mx:.3f}%`\n"
            
        embed = discord.Embed(title=f"🏆 Best Tools for {format_name(view.fish)}", description=desc, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class PeakBestLocationButton(discord.ui.Button):
    def __init__(self, row):
        super().__init__(style=discord.ButtonStyle.primary, label="Best Location", row=row)
        
    async def callback(self, interaction: discord.Interaction):
        view: PeakHourView = self.view
        
        loc_maxes = {}
        fish_data = fish_peak.get(view.fish, {})
        for l, l_data in fish_data.items():
            l_max = -1
            for t, t_data in l_data.items():
                for b, b_data in t_data.items():
                    mx = max((float(c) for c in b_data.values()), default=-1)
                    if mx > l_max:
                        l_max = mx
            if l_max > 0:
                loc_maxes[l] = l_max
                
        if not loc_maxes:
            return await interaction.response.send_message("No locations available for this fish.", ephemeral=True)
            
        sorted_locs = sorted(loc_maxes.items(), key=lambda x: x[1], reverse=True)
        
        desc = ""
        for i, (l, mx) in enumerate(sorted_locs, 1):
            desc += f"{i}. {format_name(l)} — `{mx:.3f}%`\n"
            
        embed = discord.Embed(title=f"🏆 Best Locations for {format_name(view.fish)}", description=desc, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class PeakHourView(discord.ui.View):
    def __init__(self, fish: str, location: str, tool: str, bait: str, author_id: int):
        super().__init__(timeout=None)
        self.fish = fish
        self.location = location
        self.tool = tool
        self.bait = bait
        self.author_id = author_id
        
        loc_options = [discord.SelectOption(label=format_name(k), value=k, default=(k==location)) for k in LOCATION_KEYS]
        self.add_item(PeakHourSelect(0, loc_options, "location"))
        
        tool_options = [discord.SelectOption(label=format_name(k), value=k, default=(k==tool)) for k in TOOLS]
        self.add_item(PeakHourSelect(1, tool_options, "tool"))
        
        baits = get_valid_baits(self.tool)
        bait_options = [discord.SelectOption(label=format_name(k), value=k, default=(k==bait)) for k in baits]
        self.add_item(PeakHourSelect(2, bait_options, "bait"))
        
        self.add_item(PeakBestToolButton(row=3))
        self.add_item(PeakBestLocationButton(row=3))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This isn't your command!", ephemeral=True)
            return False
        return True

def get_valid_baits(tool):
    if tool in ["bare-hand", "dynamite"]:
        return ["none"]
    elif tool in ["fishing-rod", "net"]:
        return ["none", "lucky-bait"]
    return ["none", "lucky-bait", "deadly-bait", "deadly-bait+lucky-bait"]

class FishSimSelect(discord.ui.Select):
    def __init__(self, row, options, select_type):
        self.select_type = select_type
        super().__init__(options=options, row=row)
        
    async def callback(self, interaction: discord.Interaction):
        view: FishSimulatorView = self.view
        val = self.values[0]
        if self.select_type == "location": 
            view.location = val
        elif self.select_type == "tool": 
            view.tool = val
            valid_baits = get_valid_baits(view.tool)
            if view.bait not in valid_baits:
                view.bait = "none"
        elif self.select_type == "bait": 
            view.bait = val
        elif self.select_type == "time": 
            view.time = int(val)
        
        embed = generate_simulator_embed(view.location, view.tool, view.bait, view.time)
        new_view = FishSimulatorView(view.location, view.tool, view.bait, view.time, view.author_id)
        await interaction.response.edit_message(embed=embed, view=new_view)

class FishSimulatorView(discord.ui.View):
    def __init__(self, location: str, tool: str, bait: str, time: int, author_id: int):
        super().__init__(timeout=None)
        self.location = location
        self.tool = tool
        self.bait = bait
        self.time = time
        self.author_id = author_id
        
        loc_options = [discord.SelectOption(label=format_name(k), value=k, default=(k==location)) for k in LOCATION_KEYS]
        self.add_item(FishSimSelect(0, loc_options, "location"))
        
        tool_options = [discord.SelectOption(label=format_name(k), value=k, default=(k==tool)) for k in TOOLS]
        self.add_item(FishSimSelect(1, tool_options, "tool"))
        
        baits = get_valid_baits(self.tool)
        bait_options = [discord.SelectOption(label=format_name(k), value=k, default=(k==bait)) for k in baits]
        self.add_item(FishSimSelect(2, bait_options, "bait"))
        
        time_options = [discord.SelectOption(label=f"{t:02d}:00 UTC", value=str(t), default=(t==time)) for t in range(24)]
        self.add_item(FishSimSelect(3, time_options, "time"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This isn't your command!", ephemeral=True)
            return False
        return True

class FishingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    peak_group = app_commands.Group(name="peak", description="Peak hours commands")
    fish_group = app_commands.Group(name="fish", description="Fishing simulator commands")

    async def fish_autocomplete(self, interaction: discord.Interaction, current: str):
        return to_choices(get_fuzzy_matches(current, FISH_KEYS))

    async def location_autocomplete(self, interaction: discord.Interaction, current: str):
        return to_choices(get_fuzzy_matches(current, LOCATION_KEYS))

    async def tool_autocomplete(self, interaction: discord.Interaction, current: str):
        return to_choices(get_fuzzy_matches(current, TOOLS))

    async def bait_autocomplete(self, interaction: discord.Interaction, current: str):
        return to_choices(get_fuzzy_matches(current, BAITS))

    async def time_autocomplete(self, interaction: discord.Interaction, current: int):
        options = [app_commands.Choice(name=f"{t:02d}:00 UTC", value=t) for t in range(24)]
        if current is not None:
            options = [o for o in options if str(current) in str(o.value)]
        return options[:25]

    @commands.command(name="peak")
    async def peak_prefix(self, ctx: commands.Context, *, args: str = ""):
        args_lower = args.lower()
        words = args_lower.split()
        
        fish_key = None
        for k in FISH_KEYS:
            if k.lower() in args_lower or format_name(k).lower() in args_lower:
                fish_key = k
                break
        if not fish_key:
            for w in words:
                match = fuzzy_find(w, FISH_KEYS)
                if match:
                    fish_key = match
                    break
                    
        if not fish_key:
            return await ctx.reply("Could not find a matching fish in your query.", mention_author=False)
            
        loc_key = None
        for w in words:
            match = fuzzy_find(w, LOCATION_KEYS)
            if match: loc_key = match; break
        if not loc_key: loc_key = "pond"
        
        tool_key = None
        for w in words:
            match = fuzzy_find(w, TOOLS)
            if match: tool_key = match; break
        if not tool_key: tool_key = "fishing-rod"
        
        bait_key = None
        for w in words:
            match = fuzzy_find(w, BAITS)
            if match: bait_key = match; break
        if not bait_key: bait_key = "none"
        
        data = fish_peak.get(fish_key, {}).get(loc_key, {}).get(tool_key, {}).get(bait_key, {})
        if not data:
            found = False
            for l, l_data in fish_peak.get(fish_key, {}).items():
                for t, t_data in l_data.items():
                    for b, b_data in t_data.items():
                        if b_data:
                            loc_key = l
                            tool_key = t
                            bait_key = b
                            found = True
                            break
                    if found: break
                if found: break
        
        embed = generate_peak_embed(fish_key, loc_key, tool_key, bait_key)
        await ctx.reply(embed=embed, view=PeakHourView(fish_key, loc_key, tool_key, bait_key, ctx.author.id), mention_author=False)

    @commands.command(name="sim", aliases=["simulator"])
    async def fish_simulator_prefix(self, ctx: commands.Context, *, args: str = ""):
        args_lower = args.lower()
        words = args_lower.split()
        
        loc_key = None
        for w in words:
            match = fuzzy_find(w, LOCATION_KEYS)
            if match: loc_key = match; break
        if not loc_key: loc_key = "pond"
        
        tool_key = None
        for w in words:
            match = fuzzy_find(w, TOOLS)
            if match: tool_key = match; break
        if not tool_key: tool_key = "fishing-rod"
        
        bait_key = None
        for w in words:
            match = fuzzy_find(w, BAITS)
            if match: bait_key = match; break
        if not bait_key: bait_key = "none"
        
        time_val = None
        import re
        matches = re.findall(r'\b(\d{1,2})\b', args_lower)
        for m in matches:
            if 0 <= int(m) <= 23:
                time_val = int(m)
                break
                
        if time_val is None:
            time_val = datetime.datetime.now(datetime.timezone.utc).hour
            
        embed = generate_simulator_embed(loc_key, tool_key, bait_key, time_val)
        await ctx.reply(embed=embed, view=FishSimulatorView(loc_key, tool_key, bait_key, time_val, ctx.author.id), mention_author=False)

    @peak_group.command(name="hour", description="Check the peak hours for a specific fish.")
    @app_commands.autocomplete(
        fish=fish_autocomplete,
        location=location_autocomplete,
        tool=tool_autocomplete,
        bait=bait_autocomplete
    )
    async def peak_hour_slash(self, interaction: discord.Interaction, fish: str, location: str = "pond", tool: str = "fishing-rod", bait: str = "none"):
        fish_key = fuzzy_find(fish, FISH_KEYS)
        if not fish_key:
            return await interaction.response.send_message("Fish not found.", ephemeral=True)
            
        loc_key = fuzzy_find(location, LOCATION_KEYS)
        if not loc_key: loc_key = "pond"
        
        tool_key = fuzzy_find(tool, TOOLS)
        if not tool_key: tool_key = "fishing-rod"
        
        bait_key = fuzzy_find(bait, BAITS)
        if not bait_key: bait_key = "none"
        
        data = fish_peak.get(fish_key, {}).get(loc_key, {}).get(tool_key, {}).get(bait_key, {})
        if not data:
            found = False
            for l, l_data in fish_peak.get(fish_key, {}).items():
                for t, t_data in l_data.items():
                    for b, b_data in t_data.items():
                        if b_data:
                            loc_key = l
                            tool_key = t
                            bait_key = b
                            found = True
                            break
                    if found: break
                if found: break
        
        embed = generate_peak_embed(fish_key, loc_key, tool_key, bait_key)
        await interaction.response.send_message(embed=embed, view=PeakHourView(fish_key, loc_key, tool_key, bait_key, interaction.user.id), ephemeral=False)

    @fish_group.command(name="simulator", description="Simulate fishing to see what you can catch.")
    @app_commands.autocomplete(
        location=location_autocomplete,
        tool=tool_autocomplete,
        bait=bait_autocomplete,
        time=time_autocomplete
    )
    async def fish_simulator_slash(self, interaction: discord.Interaction, location: str, tool: str, bait: str, time: int):
        if time < 0 or time > 23:
            return await interaction.response.send_message("Time must be between 0 and 23.", ephemeral=True)
            
        loc_key = fuzzy_find(location, LOCATION_KEYS)
        if not loc_key: loc_key = "pond"
        
        tool_key = fuzzy_find(tool, TOOLS)
        if not tool_key: tool_key = "fishing-rod"
        
        bait_key = fuzzy_find(bait, BAITS)
        if not bait_key: bait_key = "none"
        
        embed = generate_simulator_embed(loc_key, tool_key, bait_key, time)
        await interaction.response.send_message(embed=embed, view=FishSimulatorView(loc_key, tool_key, bait_key, time, interaction.user.id), ephemeral=False)

async def setup(bot):
    await bot.add_cog(FishingCog(bot))
