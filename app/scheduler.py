"""Scheduler utilities for periodic notification checks."""
from telegram.ext import Application, ContextTypes
from telegram import Bot
from app.database import get_db, get_or_create_settings, User
from app.notifications import NotificationService
from app.config import Config
import asyncio

class NotificationScheduler:
    """Scheduler helper that uses Telegram Application's job queue."""

    def __init__(self, application: Application):
        self.application = application
        self.job = None

    def _compute_interval_seconds(self) -> int:
        """Derive poll interval based on global + per-user settings."""
        db_gen = get_db()
        db = next(db_gen)
        try:
            settings = get_or_create_settings(db)
            base_period = settings.notify_period_seconds or Config.NOTIFICATION_CHECK_INTERVAL
            user_periods = [
                u.notify_period_seconds for u in db.query(User).all()
                if u.notify_period_seconds and u.notify_period_seconds > 0
            ]
            effective_period = min(user_periods) if user_periods else base_period
        except Exception:
            effective_period = Config.NOTIFICATION_CHECK_INTERVAL
        finally:
            db.close()

        if not effective_period or effective_period <= 0:
            effective_period = Config.NOTIFICATION_CHECK_INTERVAL
        half_period = int(effective_period / 2)
        if half_period <= 0:
            half_period = int(effective_period)
        return max(15, half_period)

    async def _job_callback(self, context: ContextTypes.DEFAULT_TYPE):
        """Background job entry point."""
        await self.check_deadlines(context.bot)

    def start(self):
        """Register repeating job in Telegram job queue."""
        interval = self._compute_interval_seconds()
        if self.job:
            self.job.schedule_removal()
        self.job = self.application.job_queue.run_repeating(
            self._job_callback,
            interval=interval,
            first=interval,
            name="deadline_notifications",
        )
        print(f"Notification scheduler started (interval={interval}s)")

    def stop(self):
        """Remove scheduled job if present."""
        if self.job:
            self.job.schedule_removal()
            self.job = None
            print("Notification scheduler stopped")

    async def check_deadlines(self, bot: Bot):
        """Check for upcoming deadlines."""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                notification_service = NotificationService(bot, db)
                await notification_service.check_upcoming_deadlines()
            finally:
                db.close()
        except Exception as e:
            print(f"Error checking deadlines: {e}")

