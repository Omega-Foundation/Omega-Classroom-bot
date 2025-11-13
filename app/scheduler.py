"""Scheduler for periodic notification checks."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot
from sqlalchemy.orm import Session
from app.database import get_db, get_or_create_settings, User
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
            base_period = settings.notify_period_seconds or Config.NOTIFICATION_CHECK_INTERVAL
            user_periods = [
                u.notify_period_seconds for u in db.query(User).all()
                if u.notify_period_seconds and u.notify_period_seconds > 0
            ]
            if user_periods:
                effective_period = min(base_period, min(user_periods))
            else:
                effective_period = base_period
        except Exception:
            effective_period = Config.NOTIFICATION_CHECK_INTERVAL
        finally:
            db.close()

        # Ensure scheduler runs at a reasonable cadence
        if not effective_period or effective_period <= 0:
            effective_period = Config.NOTIFICATION_CHECK_INTERVAL
        half_period = int(effective_period / 2)
        if half_period <= 0:
            half_period = int(effective_period)
        period_seconds = max(15, half_period)

        # Schedule deadline checks
        self.scheduler.add_job(
            self.check_deadlines,
            trigger=IntervalTrigger(seconds=period_seconds),
            id='check_deadlines',
            replace_existing=True
        )
        
        # Schedule PR comment checks (every 5 minutes)
        self.scheduler.add_job(
            self.check_pr_comments,
            trigger=IntervalTrigger(seconds=300),  # 5 minutes
            id='check_pr_comments',
            replace_existing=True
        )
        
        # Schedule PR label change checks (every 5 minutes)
        self.scheduler.add_job(
            self.check_pr_labels,
            trigger=IntervalTrigger(seconds=300),  # 5 minutes
            id='check_pr_labels',
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
    
    async def check_pr_comments(self):
        """Check for new PR comments."""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                notification_service = NotificationService(self.bot, db)
                await notification_service.check_pr_messages()
            finally:
                db.close()
        except Exception as e:
            print(f"Error checking PR comments: {e}")
    
    async def check_pr_labels(self):
        """Check for PR label changes."""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                notification_service = NotificationService(self.bot, db)
                await notification_service.check_label_change()
            finally:
                db.close()
        except Exception as e:
            print(f"Error checking PR labels: {e}")
    
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()

