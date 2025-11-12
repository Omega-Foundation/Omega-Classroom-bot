"""Configuration management for the Omega Classroom bot."""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration."""
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TEACHER_ACCESS_PASSWORD = os.getenv('TEACHER_ACCESS_PASSWORD', '')
    
    # GitHub
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
    
    # Database
    # Support Docker PostgreSQL connection
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'omega_classroom')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
    
    @classmethod
    def get_database_url(cls):
        """Get database URL, constructing it if needed."""
        # Use DATABASE_URL if provided
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            return database_url
        
        # Check if we're in Docker (PostgreSQL) or local (SQLite)
        if os.getenv('USE_POSTGRESQL', 'false').lower() == 'true' or os.getenv('DB_HOST'):
            return f'postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}'
        else:
            return 'sqlite:///omega_classroom.db'
    
    # Property to access database URL
    @property
    def DATABASE_URL(self):
        return self.get_database_url()
    
    # Notifications
    NOTIFICATION_CHECK_INTERVAL = int(os.getenv('NOTIFICATION_CHECK_INTERVAL', 3600))
    DEADLINE_WARNING_HOURS = int(os.getenv('DEADLINE_WARNING_HOURS', 24))
    
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present."""
        required = [
            ('TELEGRAM_BOT_TOKEN', cls.TELEGRAM_BOT_TOKEN),
            ('TEACHER_ACCESS_PASSWORD', cls.TEACHER_ACCESS_PASSWORD),
        ]
        
        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        # GITHUB_TOKEN is now optional (users provide their own tokens)
        
        return True

