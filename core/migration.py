import os
import json
import logging
from core.database import db

logger = logging.getLogger(__name__)

REMINDERS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reminders.json")
SERVER_REMINDERS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server_reminders.json")

async def run_migration():
    """Migrates JSON reminders to SQLite, then renames the files to prevent double-migration."""
    migrated_count = 0
    
    if os.path.exists(REMINDERS_FILE):
        try:
            with open(REMINDERS_FILE, "r") as f:
                data = json.load(f)
                
            for user_id_str, reminders in data.items():
                try:
                    user_id = int(user_id_str)
                except ValueError:
                    continue
                    
                for rem_type, rem_data in reminders.items():
                    # Legacy simple timestamp format.
                    if isinstance(rem_data, (int, float, str)):
                        try:
                            ts = int(rem_data)
                            await db.add_reminder(user_id, None, rem_type, ts)
                            migrated_count += 1
                        except (ValueError, TypeError):
                            pass
                            
                    # Legacy dict format.
                    elif isinstance(rem_data, dict):
                        try:
                            ts = int(rem_data.get("timestamp", 0))
                            channel_id_raw = rem_data.get("channel_id")
                            channel_id = int(channel_id_raw) if channel_id_raw else None
                            if ts > 0:
                                await db.add_reminder(user_id, channel_id, rem_type, ts)
                                migrated_count += 1
                        except (ValueError, TypeError):
                            pass
                            
                    # Legacy list format.
                    elif isinstance(rem_data, list):
                        for item in rem_data:
                            try:
                                if isinstance(item, (int, float, str)):
                                    ts = int(item)
                                    channel_id = None
                                elif isinstance(item, dict):
                                    ts = int(item.get("timestamp", 0))
                                    channel_id_raw = item.get("channel_id")
                                    channel_id = int(channel_id_raw) if channel_id_raw else None
                                else:
                                    continue
                                    
                                if ts > 0:
                                    await db.add_reminder(user_id, channel_id, rem_type, ts)
                                    migrated_count += 1
                            except (ValueError, TypeError):
                                pass

            # Prevent double-migration.
            os.rename(REMINDERS_FILE, REMINDERS_FILE + ".migrated")
            logger.info(f"Successfully migrated {REMINDERS_FILE}")
            
        except Exception as e:
            logger.error(f"Failed to migrate {REMINDERS_FILE}: {e}", exc_info=True)

    if os.path.exists(SERVER_REMINDERS_FILE):
        try:
            with open(SERVER_REMINDERS_FILE, "r") as f:
                server_data = json.load(f)
                
            for server_id_str, reminders in server_data.items():
                try:
                    server_id = int(server_id_str)
                except ValueError:
                    continue
                    
                for rem_type, rem_data in reminders.items():
                    if isinstance(rem_data, dict):
                        enabled = rem_data.get("enabled", False)
                        role_id = rem_data.get("role_id")
                        channel_id = rem_data.get("channel_id")
                        await db.set_server_setting(server_id, rem_type, enabled, role_id, channel_id)
                        migrated_count += 1

            os.rename(SERVER_REMINDERS_FILE, SERVER_REMINDERS_FILE + ".migrated")
            logger.info(f"Successfully migrated {SERVER_REMINDERS_FILE}")
            
        except Exception as e:
            logger.error(f"Failed to migrate {SERVER_REMINDERS_FILE}: {e}", exc_info=True)

    if migrated_count > 0:
        logger.info(f"Total reminders migrated to SQLite: {migrated_count}")
