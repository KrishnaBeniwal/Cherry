import discord
import emojis

class UnifiedReminderView(discord.ui.LayoutView):
    def __init__(self, title: str, text: str, reminder_id: str = None, next_target: int = 0, buttons: list = None, action_rows: list = None, snooze_url: str = None):
        super().__init__(timeout=86400) # Buttons expire after 24h
        
        self.title_str = title
        self.text = text
        self.reminder_id = reminder_id
        self.next_target = next_target
        
        self.container = discord.ui.Container()
        
        # Add header.
        if reminder_id:
            self.container.add_item(discord.ui.TextDisplay(f"### **{title}**\nID : `{reminder_id}`"))
        else:
            self.container.add_item(discord.ui.TextDisplay(f"### **{title}**"))
        self.container.add_item(discord.ui.Separator())
        
        # Add content.
        body = ""
        if snooze_url:
            body += f"> *This is a snoozed reminder from [here]({snooze_url})*\n\n"
            
        if text:
            # Preserve exact text format.
            body += f"{text}\n\n"
            
        if next_target > 0:
            body += f"Next reminder: <t:{next_target}:F> (<t:{next_target}:R>)"
            
        if body.strip():
            self.container.add_item(discord.ui.TextDisplay(content=body.strip()))
            
        self.container.add_item(discord.ui.Separator())
        
        # Add buttons and action rows.
        if buttons:
            row = discord.ui.ActionRow()
            for btn in buttons:
                row.add_item(btn)
            self.container.add_item(row)
            
        if action_rows:
            for row in action_rows:
                self.container.add_item(row)
                
        self.add_item(self.container)

def rebuild_reminder_view(interaction: discord.Interaction, status_text: str = None) -> discord.ui.LayoutView:
    """
    Extracts semantic metadata from the interaction message's components,
    and regenerates the reminder using the UnifiedReminderView builder.
    """
    title = "Reminder"
    reminder_id = None
    next_target = 0
    text_lines = []
    snooze_url = None
    
    # Extract components.
    components = interaction.message.components if interaction.message else []
    
    # Extract text recursively.
    def get_texts(comp):
        parts = []
        if hasattr(comp, 'content') and comp.content:
            parts.append(str(comp.content))
        elif hasattr(comp, 'to_dict'):
            try:
                d = comp.to_dict()
                if 'content' in d and d['content']:
                    parts.append(str(d['content']))
            except:
                pass
        if hasattr(comp, 'children') and comp.children:
            for child in comp.children:
                parts.extend(get_texts(child))
        return parts

    raw_texts = []
    for c in components:
        # Extract raw text from components.
        raw_texts.extend(get_texts(c))
        
    for raw in raw_texts:
        lines = raw.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("### **"):
                title = line.replace("### **", "").replace("**", "")
            elif line.startswith("ID : `"):
                reminder_id = line.replace("ID : `", "").replace("`", "")
            elif line.startswith("Next reminder: <t:"):
                try:
                    ts_part = line.split("<t:")[1]
                    next_target = int(ts_part.split(":")[0])
                except:
                    pass
            elif line.startswith("> *This is a snoozed reminder from [here]("):
                snooze_url = line.split("]({")[1].split("})*")[0] if "]({" in line else line.split("](")[1].split(")*")[0]
            elif "Snoozed for 5 minutes" in line or "Reminder cancelled" in line:
                continue
            else:
                text_lines.append(line)
                
    content_text = "\n".join(text_lines)
    
    # Copy buttons as disabled.
    action_rows = []
    if components:
        for comp in components:
            if comp.__class__.__name__ == 'ActionRow':
                new_row = discord.ui.ActionRow()
                has_buttons = False
                for btn in comp.children:
                    if hasattr(btn, 'custom_id') and btn.custom_id:
                        b = discord.ui.Button(
                            style=btn.style,
                            label=btn.label,
                            disabled=True,
                            custom_id=btn.custom_id,
                            emoji=btn.emoji
                        )
                        new_row.add_item(b)
                        has_buttons = True
                if has_buttons:
                    action_rows.append(new_row)
            elif hasattr(comp, 'children'):
                # Search inside containers.
                for child in comp.children:
                    if child.__class__.__name__ == 'ActionRow':
                        new_row = discord.ui.ActionRow()
                        has_buttons = False
                        for btn in child.children:
                            if hasattr(btn, 'custom_id') and btn.custom_id:
                                b = discord.ui.Button(
                                    style=btn.style,
                                    label=btn.label,
                                    disabled=True,
                                    custom_id=btn.custom_id,
                                    emoji=btn.emoji
                                )
                                new_row.add_item(b)
                                has_buttons = True
                        if has_buttons:
                            action_rows.append(new_row)
                            
    view = UnifiedReminderView(
        title=title,
        text=content_text,
        reminder_id=reminder_id,
        next_target=next_target,
        action_rows=action_rows,
        snooze_url=snooze_url
    )
    
    if status_text:
        view.container.add_item(discord.ui.Separator())
        view.container.add_item(discord.ui.TextDisplay(content=status_text))
        
    return view

class SnoozeReminderButton(discord.ui.Button):
    def __init__(self, user_id: int):
        super().__init__(label="Snooze 5 Minutes", style=discord.ButtonStyle.secondary, emoji=discord.PartialEmoji.from_str(emojis.TIMER), custom_id=f"snooze_btn_{user_id}")
        self.user_id = user_id

