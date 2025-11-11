"""Notification system for deadlines."""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database import Assignment, Submission, User, Notification, AppSettings, get_or_create_settings
from app.github_client import GitHubClient
from telegram import Bot
from app.config import Config

class NotificationService:
    """Service for handling notifications."""
    
    def __init__(self, bot: Bot, db: Session):
        self.bot = bot
        self.db = db
    
    async def check_upcoming_deadlines(self):
        """Check for upcoming deadlines and notify users about their assignments (per-user settings)."""
        # App-wide defaults
        app_settings = get_or_create_settings(self.db)

        now = datetime.utcnow()

        # For each user with assignments, compute threshold and period and send if due
        users = self.db.query(User).all()
        for user in users:
            threshold_hours = user.notify_threshold_hours if user.notify_threshold_hours is not None else app_settings.notify_threshold_hours
            period_seconds = user.notify_period_seconds if user.notify_period_seconds is not None else app_settings.notify_period_seconds

            warning_time = now + timedelta(hours=threshold_hours)

            # Only consider this user's assignments
            upcoming = self.db.query(Assignment).filter(
                and_(
                    Assignment.user_id == user.id,
                    Assignment.deadline <= warning_time,
                    Assignment.deadline > now
                )
            ).all()

            for assignment in upcoming:
                # Check last notification time for this user/assignment
                last = self.db.query(Notification).filter(
                    and_(
                        Notification.user_id == user.id,
                        Notification.assignment_id == assignment.id,
                        Notification.notification_type == 'deadline_warning'
                    )
                ).order_by(Notification.sent_at.desc()).first()

                should_send = False
                if not last:
                    should_send = True
                else:
                    elapsed = (now - last.sent_at).total_seconds()
                    if elapsed >= period_seconds:
                        should_send = True

                if not should_send:
                    continue

                hours_until_deadline = (assignment.deadline - now).total_seconds() / 3600
                days = int(hours_until_deadline // 24)
                hours = int(hours_until_deadline % 24)
                time_remaining = f"{days}d {hours}h" if days > 0 else f"{hours}h"

                message = (
                    f"⏰ Deadline Reminder\n\n"
                    f"Assignment: {assignment.name}\n"
                    f"Deadline: {assignment.deadline.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                    f"Time remaining: {time_remaining}\n"
                    f"Repository: {assignment.github_repo_url or assignment.github_repo_name}"
                )

                try:
                    await self.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message
                    )
                    note = Notification(
                        user_id=user.id,
                        assignment_id=assignment.id,
                        notification_type='deadline_warning',
                        message=message
                    )
                    self.db.add(note)
                    self.db.commit()
                except Exception as e:
                    print(f"Error sending notification to {user.telegram_id}: {e}")
