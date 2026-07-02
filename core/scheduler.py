import asyncio
import time
import logging
from typing import Optional
from core.database import db

logger = logging.getLogger(__name__)

# Grace period (5 minutes).
GRACE_PERIOD_SECONDS = 300

class AdaptiveScheduler:
    def __init__(self, bot):
        self.bot = bot
        self._task: Optional[asyncio.Task] = None
        self._wake_event = asyncio.Event()
        self._current_target_time: Optional[int] = None
        self._stop_event = asyncio.Event()

    def start(self):
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = self.bot.loop.create_task(self._run())
            logger.info("AdaptiveScheduler started.")

    def stop(self):
        self._stop_event.set()
        self._wake_event.set()
        if self._task:
            self._task.cancel()

    def wake_if_needed(self, new_target_time: int):
        """Called by the DB layer when a new reminder is added."""
        if self._current_target_time is None or new_target_time < self._current_target_time:
            self._wake_event.set()

    async def _process_due_reminders(self, current_time: int):
        """Fetch, dispatch, and delete due reminders."""
        due_reminders = await db.get_due_reminders(current_time)
        if not due_reminders:
            return

        for row in due_reminders:
            target_time = row['target_time']
            # Handle offline missed reminders.
            if current_time - target_time <= GRACE_PERIOD_SECONDS:
                # Dispatch event to cogs.
                self.bot.dispatch("reminder_due", dict(row))
            else:
                logger.info(f"Dropped stale reminder {row['id']} (type: {row['reminder_type']}) - {current_time - target_time}s old.")

        # Batch delete processed reminders.
        await db.delete_due_reminders(current_time)

    async def _run(self):
        # Process immediate/missed reminders on startup.
        await self._process_due_reminders(int(time.time()) + 2)

        while not self._stop_event.is_set():
            try:
                self._wake_event.clear()
                
                next_reminder = await db.get_next_reminder()
                
                if next_reminder is None:
                    self._current_target_time = None
                    # Wait indefinitely if no reminders.
                    await self._wake_event.wait()
                    continue

                self._current_target_time = next_reminder['target_time']
                current_time = int(time.time())
                
                # Wake up 2s early for API latency.
                sleep_time = (self._current_target_time - 2) - current_time
                
                if sleep_time <= 0:
                    await self._process_due_reminders(current_time + 2)
                    continue
                
                # Wait for sleep or wake event.
                try:
                    await asyncio.wait_for(self._wake_event.wait(), timeout=sleep_time)
                    # Loop restarts on wake event.
                except asyncio.TimeoutError:
                    # Process reminder after sleep.
                    await self._process_due_reminders(int(time.time()) + 2)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                # Prevent infinite crash loops on error.
                await asyncio.sleep(5)

scheduler = None

def init_scheduler(bot):
    global scheduler
    scheduler = AdaptiveScheduler(bot)
    return scheduler
