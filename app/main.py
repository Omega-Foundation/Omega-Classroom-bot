"""Main entry point for the Omega Classroom bot."""
from telegram import Bot
from app.bot import HomeworkTrackerBot, main as bot_main
from app.scheduler import NotificationScheduler
from app.config import Config
import asyncio

def run_with_scheduler():
    """Run bot with notification scheduler."""
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        print(f"Configuration error: {e}")
        return
    
    # Create bot
    bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
    
    # Start scheduler
    scheduler = NotificationScheduler(bot)
    scheduler.start()
    
    # Run bot (this will block)
    bot_main()

if __name__ == '__main__':
    run_with_scheduler()

