import discord
from discord.ext import commands
import time
import json
from core.database import db
import emojis

class PersistentButtonsHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _extract_text(self, components) -> str:
        if not components:
            return ""
        text_parts = []
        for comp in components:
            if hasattr(comp, 'content') and comp.content:
                text_parts.append(str(comp.content))
            elif hasattr(comp, 'to_dict'):
                try:
                    d = comp.to_dict()
                    if 'content' in d and d['content']:
                        text_parts.append(str(d['content']))
                    elif d.get('type') == 9: # Separator type might be 9 or similar, let's just use class name
                        pass
                except Exception:
                    pass
            if comp.__class__.__name__ == 'Separator':
                text_parts.append("|||SEPARATOR|||")
            if hasattr(comp, 'children') and comp.children:
                text_parts.append(self._extract_text(comp.children))
        return "\n".join(text_parts)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
            
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id:
            return

        # System snooze.
        if custom_id.startswith("snooze_btn_"):
            parts = custom_id.split("_")
            if len(parts) >= 3:
                owner_id = int(parts[2])
                if interaction.user.id != owner_id:
                    await interaction.response.send_message("This isn't your reminder!", ephemeral=True)
                    return
                
                raw_text = ""
                if interaction.message and interaction.message.components:
                    raw_text = self._extract_text(interaction.message.components)
                
                # Filter out snooze labels.
                valid_lines = [
                    l for l in raw_text.split('\n') 
                    if l and "Snooze 5 Minutes" not in l and "Snoozed for 5 minutes" not in l and not l.startswith("### **") and l != "---" and "This is a snoozed reminder from" not in l
                ]
                text = "\n".join(valid_lines).strip()
                
                now = int(time.time())
                snooze_target = now + 300
                
                original_title = "Reminder"
                for l in raw_text.split('\n'):
                    if l.startswith("### **"):
                        original_title = l.replace("### **", "").replace("**", "").strip()
                        break
                        
                snooze_extra = {
                    'repeat_type': 'none',
                    'is_snoozed': True,
                    'message': text,
                    'series_id': "SYSTEM_SNOOZE",
                    'original_title': original_title
                }
                
                if interaction.message:
                    snooze_extra['snooze_url'] = interaction.message.jump_url
                    snooze_extra['snooze_msg_id'] = interaction.message.id
                    snooze_extra['snooze_channel_id'] = interaction.channel.id
                    
                await db.add_reminder(owner_id, interaction.channel_id, "custom", snooze_target, snooze_extra)
                
                try:
                    from cogs.reminder_views import rebuild_reminder_view
                    new_view = rebuild_reminder_view(interaction, status_text=f"{emojis.TICK} Snoozed for 5 minutes.")
                    await interaction.response.edit_message(view=new_view)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"[SNOOZE ERROR] {e}")
                    try:
                        await interaction.response.defer()
                    except:
                        pass
                return

        # Custom snooze.
        elif custom_id.startswith("cus_snooze_"):
            parts = custom_id.split("_", 3)
            if len(parts) >= 4:
                owner_id = int(parts[2])
                series_id = parts[3]
                
                if interaction.user.id != owner_id:
                    await interaction.response.send_message("This isn't your reminder!", ephemeral=True)
                    return
                    
                raw_text = ""
                if interaction.message and interaction.message.components:
                    raw_text = self._extract_text(interaction.message.components)
                
                # Extract reminder message from UI format.
                lines = raw_text.split('\n')
                msg_lines = []
                for l in lines:
                    if l.startswith("### **") or l.startswith("Reminder ID") or l.startswith("Next reminder:") or "Snooze 5 Minutes" in l or "Cancel Reminder" in l or "Snoozed for 5 minutes" in l or l == "---" or "This is a snoozed reminder from" in l:
                        continue
                    if l.startswith("> "):
                        msg_lines.append(l[2:])
                    else:
                        msg_lines.append(l)
                
                msg = "\n".join(msg_lines).strip()
                
                original_title = "Reminder"
                for l in raw_text.split('\n'):
                    if l.startswith("### **"):
                        original_title = l.replace("### **", "").replace("**", "").strip()
                        break
                        
                now = int(time.time())
                snooze_target = now + 300
                
                snooze_extra = {
                    'repeat_type': 'none',
                    'is_snoozed': True,
                    'message': msg,
                    'series_id': series_id,
                    'original_title': original_title
                }
                
                if interaction.message:
                    snooze_extra['snooze_url'] = interaction.message.jump_url
                    snooze_extra['snooze_msg_id'] = interaction.message.id
                    snooze_extra['snooze_channel_id'] = interaction.channel.id
                    
                await db.add_reminder(owner_id, interaction.channel_id, "custom", snooze_target, snooze_extra)
                
                try:
                    from cogs.reminder_views import rebuild_reminder_view
                    new_view = rebuild_reminder_view(interaction, status_text=f"{emojis.TICK} Snoozed for 5 minutes.")
                    await interaction.response.edit_message(view=new_view)
                except Exception:
                    try:
                        await interaction.response.defer()
                    except:
                        pass
                return
                
        # Custom cancel.
        elif custom_id.startswith("cus_cancel_"):
            parts = custom_id.split("_", 3)
            if len(parts) >= 4:
                owner_id = int(parts[2])
                series_id = parts[3]
                
                if interaction.user.id != owner_id:
                    await interaction.response.send_message("This isn't your reminder!", ephemeral=True)
                    return
                    
                deleted_count = 0
                cursor = await db.pool.execute("SELECT id, extra_data FROM reminders WHERE user_id = ? AND reminder_type = ?", (owner_id, "custom"))
                reminders = await cursor.fetchall()
                for rem in reminders:
                    try:
                        extra = json.loads(rem['extra_data'])
                        if extra.get('series_id') == series_id:
                            if extra.get('is_snoozed'):
                                continue
                            await db.remove_reminder_by_id(rem['id'])
                            deleted_count += 1
                    except Exception:
                        pass
                
                try:
                    from cogs.reminder_views import rebuild_reminder_view
                    new_view = rebuild_reminder_view(interaction, status_text=f"{emojis.CROSS} Reminder cancelled.")
                    await interaction.response.edit_message(view=new_view)
                    
                    if deleted_count == 0:
                        await interaction.followup.send(f"{emojis.CROSS} Reminder `{series_id}` was already cancelled.", ephemeral=True)
                    else:
                        await interaction.followup.send(f"{emojis.TICK} Reminder `{series_id}` has been cancelled.", ephemeral=True)
                except Exception:
                    try:
                        await interaction.response.defer()
                    except:
                        pass
                return

        # List pagination.
        elif custom_id.startswith("remlist_"):
            parts = custom_id.split("_")
            if len(parts) >= 3:
                owner_id = int(parts[2])
                if interaction.user.id != owner_id:
                    await interaction.response.send_message("Not yours!", ephemeral=True)
                    return
                    
                try:
                    from cogs.custom_reminders import PaginatedReminderListView
                    import re
                    
                    cursor = await db.pool.execute("SELECT * FROM reminders WHERE user_id = ? ORDER BY target_time ASC", (owner_id,))
                    rems = await cursor.fetchall()
                    active_rems = [r for r in rems if r['target_time'] >= int(time.time())]
                    
                    view = PaginatedReminderListView(active_rems, owner_id)
                    
                    current_page = 0
                    raw_text = self._extract_text(interaction.message.components) if interaction.message else ""
                    match = re.search(r"Page (\d+) of (\d+)", raw_text)
                    if match:
                        current_page = int(match.group(1)) - 1
                        
                    if "prev" in custom_id:
                        current_page -= 1
                    elif "next" in custom_id:
                        current_page += 1
                        
                    view.current_page = max(0, min(current_page, view.max_pages - 1))
                    view.update_view()
                    
                    await interaction.response.edit_message(view=view)
                except Exception:
                    try:
                        await interaction.response.defer()
                    except:
                        pass
                return

async def setup(bot):
    await bot.add_cog(PersistentButtonsHandler(bot))
