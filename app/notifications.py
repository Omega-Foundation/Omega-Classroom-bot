"""Notification system for deadlines."""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
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
            upcoming = (
                self.db.query(Assignment)
                .options(joinedload(Assignment.submissions))
                .outerjoin(Submission, Submission.assignment_id == Assignment.id)
                .filter(
                    and_(
                        Assignment.deadline <= warning_time,
                        Assignment.deadline > now,
                        or_(
                            Assignment.user_id == user.id,
                            Submission.user_id == user.id
                        )
                    )
                )
                .distinct()
                .all()
            )

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

                submission = next(
                    (s for s in assignment.submissions or [] if s.user_id == user.id),
                    None
                )
                repo_ref = ''
                if submission and submission.github_repo_url:
                    repo_ref = submission.github_repo_url
                else:
                    repo_ref = assignment.github_repo_url or assignment.github_repo_name or ''

                message = (
                    f"⏰ Deadline Reminder\n\n"
                    f"Assignment: {assignment.name}\n"
                    f"Deadline: {assignment.deadline.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                    f"Time remaining: {time_remaining}\n"
                    f"Repository: {repo_ref}"
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

    async def check_pr_messages(self):
        """Check for new comments on Pull Requests in tracked repositories."""
        try:
            from app.database import TrackedRepository
            now = datetime.utcnow()
            
            # Get all tracked repositories
            tracked_repos = self.db.query(TrackedRepository).all()
            
            for tracked_repo in tracked_repos:
                user = tracked_repo.user
                if not user or not user.telegram_id:
                    continue
                
                # Skip if user doesn't have GitHub token
                if not user.github_token:
                    continue
                
                repo_full_name = tracked_repo.repo_full_name
                
                try:
                    # Use user's GitHub token
                    github_client = GitHubClient(token=user.github_token)
                    
                    # Get open PRs for this repository
                    prs = github_client.get_pull_requests(repo_full_name, state='open')
                    
                    for pr in prs:
                        pr_number = pr.get('number')
                        pr_title = pr.get('title', 'Untitled')
                        pr_url = pr.get('html_url', '')
                        
                        # Get comments for this PR
                        comments = github_client.get_pr_comments(repo_full_name, pr_number)
                        
                        for comment in comments:
                            comment_id = comment.get('id')
                            comment_author = comment.get('user', 'Unknown')
                            comment_body = comment.get('body', '')
                            comment_url = comment.get('html_url', '')
                            comment_created = comment.get('created_at')
                            
                            # Check if we've already notified about this comment
                            existing = self.db.query(Notification).filter(
                                and_(
                                    Notification.user_id == user.id,
                                    Notification.notification_type == 'pr_comment',
                                    Notification.message.contains(f"PR #{pr_number}")
                                )
                            ).filter(
                                Notification.message.contains(str(comment_id))
                            ).first()
                            
                            if existing:
                                continue  # Already notified
                            
                            # Only notify about comments created in the last 24 hours (to avoid old comments)
                            if comment_created:
                                # Handle both datetime objects and strings
                                if isinstance(comment_created, str):
                                    from dateutil import parser as date_parser
                                    comment_created = date_parser.parse(comment_created)
                                
                                # Convert to naive datetime for comparison
                                if hasattr(comment_created, 'replace'):
                                    comment_created_naive = comment_created.replace(tzinfo=None)
                                else:
                                    comment_created_naive = comment_created
                                
                                hours_ago = (now - comment_created_naive).total_seconds() / 3600
                                if hours_ago > 24:
                                    continue  # Comment is too old
                            
                            # Truncate comment if too long
                            comment_preview = comment_body[:300]
                            if len(comment_body) > 300:
                                comment_preview += "..."
                            
                            message = (
                                f"💬 New Comment on Pull Request\n\n"
                                f"Repository: {repo_full_name}\n"
                                f"PR #{pr_number}: {pr_title}\n"
                                f"Comment by: {comment_author}\n\n"
                                f"Comment:\n{comment_preview}\n\n"
                                f"PR Link: {pr_url}\n"
                                f"Comment Link: {comment_url}"
                            )
                            
                            try:
                                await self.bot.send_message(
                                    chat_id=user.telegram_id,
                                    text=message
                                )
                                
                                # Log notification
                                note = Notification(
                                    user_id=user.id,
                                    notification_type='pr_comment',
                                    message=f"Comment ID {comment_id} on PR #{pr_number} in {repo_full_name}"
                                )
                                self.db.add(note)
                                self.db.commit()
                            except Exception as e:
                                print(f"Error sending PR comment notification to {user.telegram_id}: {e}")
                
                except Exception as e:
                    print(f"Error checking PR comments for {repo_full_name}: {e}")
                    continue
        
        except Exception as e:
            print(f"Error in check_pr_messages: {e}")

    async def check_label_change(self):
        """Check for label changes on Pull Requests in tracked repositories."""
        try:
            from app.database import TrackedRepository
            
            # Get all tracked repositories
            tracked_repos = self.db.query(TrackedRepository).all()
            
            for tracked_repo in tracked_repos:
                user = tracked_repo.user
                if not user or not user.telegram_id:
                    continue
                
                # Skip if user doesn't have GitHub token
                if not user.github_token:
                    continue
                
                repo_full_name = tracked_repo.repo_full_name
                
                try:
                    # Use user's GitHub token
                    github_client = GitHubClient(token=user.github_token)
                    
                    # Get open PRs for this repository
                    prs = github_client.get_pull_requests(repo_full_name, state='open')
                    
                    for pr in prs:
                        pr_number = pr.get('number')
                        pr_title = pr.get('title', 'Untitled')
                        pr_url = pr.get('html_url', '')
                        current_labels = pr.get('labels', [])
                        current_label_names = sorted([lbl.get('name', '') for lbl in current_labels if lbl.get('name')])
                        current_labels_str = ','.join(current_label_names)
                        
                        # Check if we've already notified about the current label state
                        # Get the last notification for this PR
                        last_notification = self.db.query(Notification).filter(
                            and_(
                                Notification.user_id == user.id,
                                Notification.notification_type == 'pr_label',
                                Notification.message.contains(f"PR #{pr_number}")
                            )
                        ).order_by(Notification.sent_at.desc()).first()
                        
                        if last_notification:
                            # Extract previous labels from notification message
                            # Format: "Labels: label1,label2 on PR #123 in repo"
                            prev_labels_str = None
                            if 'Labels:' in last_notification.message:
                                try:
                                    parts = last_notification.message.split('Labels:')[1].split(' on PR')[0].strip()
                                    prev_labels = [label.strip() for label in parts.split(',') if label.strip()]
                                    prev_labels_str = ','.join(sorted(prev_labels))
                                except Exception:
                                    pass
                            
                            # If labels haven't changed, skip
                            if prev_labels_str == current_labels_str:
                                continue
                            
                            # Determine what changed
                            prev_labels_set = set(prev_labels_str.split(',')) if prev_labels_str else set()
                            current_labels_set = set(current_label_names)
                            
                            added_labels = current_labels_set - prev_labels_set
                            removed_labels = prev_labels_set - current_labels_set
                            
                            if not added_labels and not removed_labels:
                                continue
                            
                            # Build change message
                            changes = []
                            if added_labels:
                                changes.append(f"Added: {', '.join(added_labels)}")
                            if removed_labels:
                                changes.append(f"Removed: {', '.join(removed_labels)}")
                            
                            change_text = ' | '.join(changes)
                            labels_text = ', '.join(current_label_names) if current_label_names else 'None'
                            
                            message = (
                                f"🏷️ Label Change on Pull Request\n\n"
                                f"Repository: {repo_full_name}\n"
                                f"PR #{pr_number}: {pr_title}\n"
                                f"Changes: {change_text}\n"
                                f"Current labels: {labels_text}\n"
                                f"Link: {pr_url}"
                            )
                        else:
                            # First time checking this PR - notify about current labels if any
                            if not current_label_names:
                                continue  # No labels to report
                            
                            labels_text = ', '.join(current_label_names)
                            message = (
                                f"🏷️ Labels on Pull Request\n\n"
                                f"Repository: {repo_full_name}\n"
                                f"PR #{pr_number}: {pr_title}\n"
                                f"Current labels: {labels_text}\n"
                                f"Link: {pr_url}"
                            )
                        
                        try:
                            await self.bot.send_message(
                                chat_id=user.telegram_id,
                                text=message
                            )
                            
                            # Log notification with current label state
                            note = Notification(
                                user_id=user.id,
                                notification_type='pr_label',
                                message=f"Labels: {current_labels_str} on PR #{pr_number} in {repo_full_name}"
                            )
                            self.db.add(note)
                            self.db.commit()
                        except Exception as e:
                            print(f"Error sending PR label notification to {user.telegram_id}: {e}")
                
                except Exception as e:
                    print(f"Error checking PR labels for {repo_full_name}: {e}")
                    continue
        
        except Exception as e:
            print(f"Error in check_label_change: {e}")
