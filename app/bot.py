"""Telegram bot handlers and commands."""
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from sqlalchemy import and_
from app.database import User, Assignment, get_db, init_db
from app.github_client import GitHubClient
from datetime import datetime, timezone
from app.config import Config
from dateutil import parser as date_parser
import re

class HomeworkTrackerBot:
    """Main bot class."""
    
    def __init__(self):
        pass
    
    def get_db(self):
        """Get database session."""
        db_gen = get_db()
        return next(db_gen)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        db = self.get_db()
        try:
            # Check if user exists
            db_user = db.query(User).filter(User.telegram_id == chat_id).first()
            
            if not db_user:
                # Create new user
                db_user = User(
                    telegram_id=chat_id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
                db.add(db_user)
                db.commit()
                db.refresh(db_user)
            
            # Check if user has GitHub token
            if not db_user.github_token:
                welcome_message = (
                    f"👋 Welcome, {user.first_name}!\n\n"
                    f"I'm your Omega Classroom tracking bot.\n\n"
                    f"To get started, please provide your GitHub personal access token:\n"
                    f"/register_token <your_github_token>\n\n"
                    f"You can create a token at: https://github.com/settings/tokens\n"
                    f"Required permissions: repo, read:org"
                )
            else:
                welcome_message = (
                    f"Welcome back, {user.first_name}!\n\n"
                    f"Available commands:\n"
                    f"/assignments - List all your assignments\n"
                    f"/add_assignment - Add a new assignment\n"
                    f"/help - Show help\n"
                )
            
            await update.message.reply_text(welcome_message)
        finally:
            db.close()
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = (
            "📚 Omega Classroom Bot Commands\n\n"
            "/start - Start the bot\n"
            "/register_token <token> - Register your GitHub personal access token\n"
            "/assignments - List all your assignments\n"
            "/add_assignment - Add a new assignment to track\n"
            "/delete_assignment - Delete an assignment\n"
            "/help - Show this help message\n"
        )
        await update.message.reply_text(help_text)
    
    async def register_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /register_token command."""
        chat_id = update.effective_chat.id
        
        if not context.args:
            await update.message.reply_text(
                "Please provide your GitHub personal access token:\n"
                "/register_token <your_github_token>\n\n"
                "You can create a token at: https://github.com/settings/tokens\n"
                "Required permissions: repo, read:org"
            )
            return
        
        github_token = context.args[0]
        
        # Validate token by trying to create a GitHub client
        try:
            test_client = GitHubClient(token=github_token)
            # Try to get user info to validate token
            test_user = test_client.github.get_user()
            github_username = test_user.login
        except Exception as e:
            await update.message.reply_text(
                f"❌ Invalid GitHub token. Please check your token and try again.\n"
                f"Error: {str(e)}\n\n"
                f"Create a token at: https://github.com/settings/tokens"
            )
            return
        
        db = self.get_db()
        try:
            # Update user
            db_user = db.query(User).filter(User.telegram_id == chat_id).first()
            if db_user:
                db_user.github_token = github_token
                db_user.github_username = github_username
                db.commit()
                await update.message.reply_text(
                    f"✅ GitHub token registered successfully!\n\n"
                    f"GitHub username: {github_username}\n"
                    f"Your token has been saved securely.\n\n"
                    f"Now you can:\n"
                    f"/assignments - View your assignments\n"
                    f"/add_assignment - Add a new assignment"
                )
            else:
                await update.message.reply_text(
                    "Please use /start first to register."
                )
        finally:
            db.close()
    
    async def list_assignments(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /assignments command - get assignments from GitHub Classroom API."""
        chat_id = update.effective_chat.id
        
        db = self.get_db()
        try:
            db_user = db.query(User).filter(User.telegram_id == chat_id).first()
            
            if not db_user:
                await update.message.reply_text("Please use /start first.")
                return
            
            if not db_user.github_token:
                await update.message.reply_text(
                    "Please register your GitHub token first:\n"
                    "/register_token <your_github_token>"
                )
                return
            
            # Get assignments from GitHub Classroom API
            message = ""
            classroom_assignments = []
            try:
                github_client = GitHubClient(token=db_user.github_token)
                classroom_assignments = github_client.get_classroom_assignments()
                
                if classroom_assignments:
                    message = "📋 Assignments from GitHub Classroom\n\n"
                    for i, assignment in enumerate(classroom_assignments[:10], 1):  # Limit to 10
                        message += (
                            f"{i}. {assignment['name']}\n"
                            f"   URL: {assignment['url']}\n"
                            f"   Description: {assignment.get('description', 'N/A')}\n\n"
                        )
                    
                    if len(classroom_assignments) > 10:
                        message += f"... and {len(classroom_assignments) - 10} more assignments\n\n"
            except Exception as e:
                message = f"⚠️ Could not fetch assignments from GitHub Classroom:\n{str(e)}\n\n"
            
            # Also show user's saved assignments with deadlines
            saved_assignments = db.query(Assignment).filter(
                Assignment.user_id == db_user.id
            ).order_by(Assignment.deadline).all()
            
            if saved_assignments:
                message += "📋 Your Saved Assignments (with Deadlines)\n\n"
                for assignment in saved_assignments:
                    status = "✅ Past" if assignment.deadline < datetime.utcnow() else "⏰ Active"
                    time_remaining = ""
                    if assignment.deadline > datetime.utcnow():
                        delta = assignment.deadline - datetime.utcnow()
                        days = delta.days
                        hours = delta.seconds // 3600
                        time_remaining = f" ({days}d {hours}h remaining)"
                    
                    message += (
                        f"{status} {assignment.name}\n"
                        f"Deadline: {assignment.deadline.strftime('%Y-%m-%d %H:%M:%S UTC')}{time_remaining}\n"
                        f"Repository: {assignment.github_repo_url or assignment.github_repo_name}\n\n"
                    )
            
            if not message or (not classroom_assignments and not saved_assignments):
                await update.message.reply_text(
                    "No assignments found.\n"
                    "You can add assignments with: /add_assignment"
                )
            else:
                await update.message.reply_text(message)
        finally:
            db.close()
    
    async def add_assignment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add_assignment command - user provides repo link and deadline."""
        chat_id = update.effective_chat.id
        
        db = self.get_db()
        try:
            db_user = db.query(User).filter(User.telegram_id == chat_id).first()
            
            if not db_user:
                await update.message.reply_text("Please use /start first.")
                return
            
            if not db_user.github_token:
                await update.message.reply_text(
                    "Please register your GitHub token first:\n"
                    "/register_token <your_github_token>"
                )
                return
            
            if not context.args or len(context.args) < 3:
                await update.message.reply_text(
                    "Usage: /add_assignment <name> <repo_link> <deadline>\n\n"
                    "Example: /add_assignment \"Homework 1\" https://github.com/org/repo \"Nov 11, 2025, 22:33 UTC\"\n\n"
                    "Or: /add_assignment \"Project\" org/repo-name \"Dec 31, 2024, 23:59 UTC\""
                )
                return
            
            name = context.args[0]
            repo_link = context.args[1]
            deadline_str = ' '.join(context.args[2:])
            
            # Remove quotes if present
            deadline_str = deadline_str.strip('"\'')
            
            try:
                # Parse date in format like "Nov 11, 2025, 22:33 UTC"
                deadline = date_parser.parse(deadline_str)
                # Ensure it's timezone-aware (UTC)
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                # Convert to UTC naive datetime for storage
                deadline = deadline.astimezone(timezone.utc).replace(tzinfo=None)
            except (ValueError, TypeError) as e:
                await update.message.reply_text(
                    "Invalid deadline format. Use: \"Month Day, Year, HH:MM UTC\"\n"
                    "Example: \"Nov 11, 2025, 22:33 UTC\"\n"
                    "Or: \"Dec 31, 2024, 23:59 UTC\""
                )
                return
            
            # Parse repository name from link
            try:
                github_client = GitHubClient(token=db_user.github_token)
                repo_name = github_client.parse_repo_url(repo_link)
                
                if not repo_name:
                    await update.message.reply_text(
                        f"❌ Invalid repository link: {repo_link}\n"
                        f"Please provide a valid GitHub repository URL or org/repo format."
                    )
                    return
                
                # Validate repository exists using user's token
                repo_info = github_client.get_repository_activity(repo_name)
                
                if not repo_info['exists']:
                    await update.message.reply_text(
                        f"❌ Repository '{repo_name}' not found or not accessible.\n"
                        f"Please check the repository link and your token permissions."
                    )
                    return
                
                repo_url = repo_info.get('url', repo_link if repo_link.startswith('http') else f"https://github.com/{repo_name}")
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Error accessing repository: {str(e)}\n"
                    f"Please check the repository link and your token permissions."
                )
                return
            
            # Create assignment
            assignment = Assignment(
                name=name,
                github_repo_name=repo_name,
                github_repo_url=repo_url,
                deadline=deadline,
                user_id=db_user.id
            )
            db.add(assignment)
            db.commit()
            
            await update.message.reply_text(
                f"✅ Assignment '{name}' added successfully!\n\n"
                f"Repository: {repo_name}\n"
                f"URL: {repo_url}\n"
                f"Deadline: {deadline.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                f"The bot will monitor this assignment and notify you about the deadline."
            )
        finally:
            db.close()
    
    async def delete_assignment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /delete_assignment command - delete an assignment by name."""
        chat_id = update.effective_chat.id
        
        db = self.get_db()
        try:
            db_user = db.query(User).filter(User.telegram_id == chat_id).first()
            
            if not db_user:
                await update.message.reply_text("Please use /start first.")
                return
            
            if not context.args:
                await update.message.reply_text(
                    "Usage: /delete_assignment <assignment_name>\n\n"
                    "Example: /delete_assignment \"Homework 1\"\n\n"
                    "Use /assignments to see your assignments."
                )
                return
            
            assignment_name = ' '.join(context.args)
            
            # Find assignment by name (case-insensitive) that belongs to this user
            assignment = db.query(Assignment).filter(
                and_(
                    Assignment.user_id == db_user.id,
                    Assignment.name.ilike(f"%{assignment_name}%")
                )
            ).first()
            
            if not assignment:
                await update.message.reply_text(
                    f"❌ Assignment '{assignment_name}' not found.\n\n"
                    f"Use /assignments to see your assignments."
                )
                return
            
            # Store assignment name for confirmation message
            deleted_name = assignment.name
            
            # Delete the assignment (cascade will handle related submissions)
            db.delete(assignment)
            db.commit()
            
            await update.message.reply_text(
                f"✅ Assignment '{deleted_name}' deleted successfully!"
            )
        finally:
            db.close()

def main():
    """Main function to run the bot."""
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        print(f"Configuration error: {e}")
        return
    
    # Initialize database
    init_db()
    
    # Create bot application
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    # Create bot instance
    bot_instance = HomeworkTrackerBot()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot_instance.start))
    application.add_handler(CommandHandler("help", bot_instance.help_command))
    application.add_handler(CommandHandler("register_token", bot_instance.register_token))
    application.add_handler(CommandHandler("assignments", bot_instance.list_assignments))
    application.add_handler(CommandHandler("add_assignment", bot_instance.add_assignment))
    application.add_handler(CommandHandler("delete_assignment", bot_instance.delete_assignment))
    
    # Start the bot
    print("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
