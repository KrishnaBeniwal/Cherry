import aiosqlite
import json
import logging
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = "reminders.db"

class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.pool = None
        
    async def initialize(self):
        self.pool = await aiosqlite.connect(self.db_path)
        self.pool.row_factory = aiosqlite.Row
        
        # Enable WAL mode for performance.
        await self.pool.execute("PRAGMA journal_mode=WAL")
        await self.pool.execute("PRAGMA synchronous=NORMAL")
        
        # Meta table for schema versioning.
        await self.pool.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        # Reminders table with snowflake IDs.
        await self.pool.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id INTEGER,
                reminder_type TEXT NOT NULL,
                target_time INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                extra_data TEXT
            )
        """)
        
        await self.pool.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id INTEGER NOT NULL,
                event_key TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT 0,
                role_id INTEGER,
                channel_id INTEGER,
                PRIMARY KEY (guild_id, event_key)
            )
        """)
        
        # Indexes for faster queries.
        await self.pool.execute("CREATE INDEX IF NOT EXISTS idx_target_time ON reminders(target_time)")
        await self.pool.execute("CREATE INDEX IF NOT EXISTS idx_user_type ON reminders(user_id, reminder_type)")
        
        # Set schema version.
        await self.pool.execute(
            "INSERT OR IGNORE INTO scheduler_meta (key, value) VALUES ('schema_version', '1')"
        )
        await self.pool.commit()

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def add_reminder(self, user_id: int, channel_id: Optional[int], reminder_type: str, target_time: int, extra_data: Dict[str, Any] = None) -> int:
        extra_str = json.dumps(extra_data) if extra_data else None
        created_at = int(time.time())
        
        cursor = await self.pool.execute(
            """
            INSERT INTO reminders (user_id, channel_id, reminder_type, target_time, created_at, extra_data)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, channel_id, reminder_type, target_time, created_at, extra_str)
        )
        await self.pool.commit()
        
        # Notify scheduler of new reminder.
        from core.scheduler import scheduler
        if scheduler:
            scheduler.wake_if_needed(target_time)
        
        return cursor.lastrowid
        
    async def add_reminder_or_update(self, user_id: int, channel_id: Optional[int], reminder_type: str, target_time: int, extra_data: Dict[str, Any] = None) -> int:
        """
        Adds a new reminder, or updates an existing one if it's the exact same type.
        Returns:
            -1 if ignored (duplicate within 15 seconds)
            1 if inserted or updated
        """
        cursor = await self.pool.execute(
            "SELECT id, target_time FROM reminders WHERE user_id = ? AND reminder_type = ? ORDER BY target_time DESC",
            (user_id, reminder_type)
        )
        existing = await cursor.fetchall()
        
        if existing:
            latest = existing[0]
            latest_id = latest['id']
            latest_target = latest['target_time']
            
            # Clean up legacy duplicates.
            if len(existing) > 1:
                duplicate_ids = [row['id'] for row in existing[1:]]
                placeholders = ','.join('?' * len(duplicate_ids))
                await self.pool.execute(f"DELETE FROM reminders WHERE id IN ({placeholders})", tuple(duplicate_ids))
                await self.pool.commit()
            
            # Ignore rapid duplicate spam.
            if abs(latest_target - target_time) <= 15:
                return -1
                
            # Update time for extended reminders.
            extra_str = json.dumps(extra_data) if extra_data else None
            await self.pool.execute(
                "UPDATE reminders SET target_time = ?, extra_data = ? WHERE id = ?",
                (target_time, extra_str, latest_id)
            )
            await self.pool.commit()
            
            from core.scheduler import scheduler
            if scheduler:
                scheduler.wake_if_needed(target_time)
            return 1
            
        await self.add_reminder(user_id, channel_id, reminder_type, target_time, extra_data)
        return 1

    async def clear_item_reminders(self, user_id: int):
        async with self.pool.execute("DELETE FROM reminders WHERE user_id = ? AND reminder_type LIKE 'item_%'", (user_id,)) as cursor:
            await self.pool.commit()

    async def remove_reminder_by_id(self, reminder_id: int):
        await self.pool.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        await self.pool.commit()

    async def remove_reminders(self, user_id: int, reminder_type: str):
        await self.pool.execute(
            "DELETE FROM reminders WHERE user_id = ? AND reminder_type = ?",
            (user_id, reminder_type)
        )
        await self.pool.commit()
        
    async def remove_single_farm_reminder(self, user_id: int, target_time: int):
        # Farm logic tracks individual timestamps.
        await self.pool.execute(
            "DELETE FROM reminders WHERE user_id = ? AND reminder_type = 'farm' AND target_time = ?",
            (user_id, target_time)
        )
        await self.pool.commit()

    async def remove_all_for_user(self, user_id: int):
        await self.pool.execute("DELETE FROM reminders WHERE user_id = ?", (user_id,))
        await self.pool.commit()

    async def get_next_reminder(self) -> Optional[aiosqlite.Row]:
        """Fetch the single next closest reminder."""
        cursor = await self.pool.execute(
            "SELECT * FROM reminders ORDER BY target_time ASC LIMIT 1"
        )
        return await cursor.fetchone()

    async def get_due_reminders(self, current_time: int) -> List[aiosqlite.Row]:
        """Fetch all reminders due up to the specified time."""
        cursor = await self.pool.execute(
            "SELECT * FROM reminders WHERE target_time <= ? ORDER BY target_time ASC",
            (current_time,)
        )
        return await cursor.fetchall()
        
    async def delete_due_reminders(self, current_time: int):
        """Batch delete all reminders that have just been fetched/processed."""
        await self.pool.execute(
            "DELETE FROM reminders WHERE target_time <= ?", (current_time,)
        )
        await self.pool.commit()

    async def get_server_setting(self, guild_id: int, event_key: str) -> Optional[aiosqlite.Row]:
        cursor = await self.pool.execute(
            "SELECT * FROM server_settings WHERE guild_id = ? AND event_key = ?", (guild_id, event_key)
        )
        return await cursor.fetchone()

    async def get_all_server_settings(self) -> List[aiosqlite.Row]:
        cursor = await self.pool.execute("SELECT * FROM server_settings WHERE enabled = 1")
        return await cursor.fetchall()

    async def set_server_setting(self, guild_id: int, event_key: str, enabled: bool, role_id: Optional[int], channel_id: Optional[int]):
        await self.pool.execute(
            """
            INSERT INTO server_settings (guild_id, event_key, enabled, role_id, channel_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, event_key) DO UPDATE SET
                enabled = excluded.enabled,
                role_id = excluded.role_id,
                channel_id = excluded.channel_id
            """,
            (guild_id, event_key, int(enabled), role_id, channel_id)
        )
        await self.pool.commit()

db = DatabaseManager()
