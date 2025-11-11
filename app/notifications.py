"""Notification system for deadlines."""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database import Assignment, User, Notification
from app.github_client import GitHubClient
from telegram import Bot
from app.config import Config

class NotificationService:
    """Service for handling notifications."""
    
    def __init__(self, bot: Bot, db: Session):
        self.bot = bot
        self.db = db
    
    def check_upcoming_deadlines(self):
        """Check for upcoming deadlines and notify users about their assignments."""
        warning_time = datetime.utcnow() + timedelta(hours=Config.DEADLINE_WARNING_HOURS)
        
        # Find assignments with deadlines approaching
        upcoming_assignments = self.db.query(Assignment).filter(
            and_(
                Assignment.deadline <= warning_time,
                Assignment.deadline > datetime.utcnow()
            )
        ).all()
        
        for assignment in upcoming_assignments:
            # Get the user who owns this assignment
            user = self.db.query(User).filter(User.id == assignment.user_id).first()
            
            if not user:
                continue
            
            # Check if notification was already sent
            existing_notification = self.db.query(Notification).filter(
                and_(
                    Notification.user_id == user.id,
                    Notification.assignment_id == assignment.id,
                    Notification.notification_type == 'deadline_warning'
                )
            ).first()
            
            if not existing_notification:
                hours_until_deadline = (assignment.deadline - datetime.utcnow()).total_seconds() / 3600
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
                    self.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message
                    )
                    
                    # Record notification
                    notification = Notification(
                        user_id=user.id,
                        assignment_id=assignment.id,
                        notification_type='deadline_warning',
                        message=message
                    )
                    self.db.add(notification)
                    self.db.commit()
                except Exception as e:
                    print(f"Error sending notification to {user.telegram_id}: {e}")
