"""Main entry point for the Omega Classroom bot."""
from app.bot import main as bot_main


def run():
    """Run the bot (scheduler is initialized inside bot.main)."""
    bot_main()


if __name__ == '__main__':
    run()

