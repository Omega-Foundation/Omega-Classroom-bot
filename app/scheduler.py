"""Scheduler for periodic notification checks."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot
from sqlalchemy.orm import Session
from app.database import get_db, get_or_create_settings
from app.notifications import NotificationService
from app.config import Config
import asyncio

class NotificationScheduler:
    """Scheduler for periodic notification tasks."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
    
    def start(self):
        """Start the scheduler."""
        # Read period from DB settings
        db_gen = get_db()
        db = next(db_gen)
        try:
            settings = get_or_create_settings(db)
            period_seconds = settings.notify_period_seconds
        except Exception:
            period_seconds = Config.NOTIFICATION_CHECK_INTERVAL
        finally:
            db.close()

        # Schedule deadline checks
        self.scheduler.add_job(
            self.check_deadlines,
            trigger=IntervalTrigger(seconds=period_seconds),
            id='check_deadlines',
            replace_existing=True
        )
        
        self.scheduler.start()
        print("Notification scheduler started")
    
    async def check_deadlines(self):
        """Check for upcoming deadlines."""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                notification_service = NotificationService(self.bot, db)
                await notification_service.check_upcoming_deadlines()
            finally:
                db.close()
        except Exception as e:
            print(f"Error checking deadlines: {e}")
    
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()

