"""Database setup script."""
from app.database import init_db
from app.config import Config

def main():
    """Initialize the database."""
    try:
        Config.validate()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please check your .env file and ensure all required variables are set.")
        return
    
    print("Initializing database...")
    init_db()
    print("Database initialized successfully!")
    print(f"Database location: {Config.get_database_url()}")

if __name__ == '__main__':
    main()

