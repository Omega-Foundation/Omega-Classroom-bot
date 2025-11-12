# Omega Classroom Bot

A Telegram bot for tracking assignments in GitHub Classroom. It automatically monitors deadlines and assignment statuses, sending notifications to users about upcoming due dates.

## Features

- 📚 **Assignment Management**: Track assignments with deadlines
- 🔔 **Automatic Notifications**: 
  - Students receive reminders about upcoming deadlines
  - Teachers receive reports about unsubmitted assignments

## Setup

### Prerequisites

- Docker and Docker Compose (for Docker deployment)
- OR Python 3.8 or higher (for local development)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Teacher access password (shared secret for granting teacher role)
- GitHub Personal Access Token with appropriate permissions

## Deployment with Docker (Recommended)

### Quick Start

1. **Clone the repository** (or navigate to the project directory)

2. **Configure environment variables**:
   ```bash
   cp env.example .env
   ```
   
   Edit `.env` and fill in:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
   - `TEACHER_ACCESS_PASSWORD`: Shared secret teachers must enter
   - `GITHUB_TOKEN`: Your GitHub personal access token
   - Database settings (PostgreSQL will be used automatically in Docker)

3. **Build and start services**:
   ```bash
   docker compose up -d
   ```

4. **Initialize the database**:
   ```bash
   docker compose exec bot python -m app.setup_db
   ```
   
   Or use the Makefile:
   ```bash
   make init-db
   ```

5. **Check logs**:
   ```bash
   docker compose logs -f bot
   ```

### Docker Commands

Using Makefile (recommended):
```bash
make build      # Build Docker images
make up         # Start all services
make down       # Stop all services
make restart    # Restart all services
make logs       # Show logs from all services
make init-db    # Initialize database
make shell      # Open shell in bot container
make clean      # Remove containers, volumes, and images
make rebuild    # Rebuild and restart services
```

Or using docker compose directly:
```bash
docker compose up -d          # Start services
docker compose down           # Stop services
docker compose logs -f bot    # View bot logs
docker compose exec bot bash  # Access bot container shell
docker compose exec db psql -U postgres -d omega_classroom  # Access database
```

## Local Development (Without Docker)

1. **Clone the repository** (or navigate to the project directory)

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**:
   ```bash
   cp env.example .env
   ```
   
   Edit `.env` and fill in:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
   - `TEACHER_ACCESS_PASSWORD`: Shared secret teachers must enter
   - `GITHUB_TOKEN`: Your GitHub personal access token
   - `DATABASE_URL`: Use SQLite for local development: `sqlite:///omega_classroom.db`
   - `NOTIFICATION_CHECK_INTERVAL`: How often to check for notifications (in seconds)
   - `DEADLINE_WARNING_HOURS`: Hours before deadline to warn students

4. **Initialize the database**:
   ```bash
   python -m app.setup_db
   ```

5. **Run the bot**:
   ```bash
   python -m app.main
   ```

## Usage

1. **Start the bot**: `/start`
   - If you don't have a GitHub token, the bot will ask you to register one

2. **Register your GitHub token**: `/register_token <your_github_token>`
   - Create a token at: https://github.com/settings/tokens
   - Required permissions: `repo`, `read:org`
   - The bot will automatically detect your GitHub username from the token when possible. Otherwise, set it manually with `/set_github_username <username>`.

3. **Set your GitHub username (if needed)**: `/set_github_username <username>`
   - Required if the bot could not detect your username from the token

4. **Choose your role**: `/set_role <student|teacher> [password]`
   - Teachers must supply the shared password defined in `TEACHER_ACCESS_PASSWORD`

5. **View your assignments**: `/assignments`
   - Lists all assignments you've added
   - Shows deadline and time remaining

6. **Teacher-only** – Add an assignment: `/add_assignment <name> <repo_link> <deadline>`
   - Example: `/add_assignment "Homework 1" https://github.com/org/repo "Nov 11, 2025, 22:33 UTC"`
   - Or with repo path: `/add_assignment "Project" org/repo-name "Dec 31, 2024, 23:59 UTC"`
   - The bot will validate the repository exists and is accessible with your token
   - The bot will automatically monitor the deadline and notify you

7. **Teacher-only** – Delete an assignment: `/delete_assignment <assignment_name>`
   - Example: `/delete_assignment "Homework 1"`
   - Deletes the assignment and stops monitoring it
   - Use `/assignments` to see your assignments

8. **Get help**: `/help`
   - Shows all available commands

## Database Schema

The bot uses SQLAlchemy ORM with the following models:

- **User**: Telegram users (students and teachers)
- **Assignment**: Assignments with deadlines
- **Submission**: Student submission tracking
- **Notification**: Notification history

## Configuration

### Database

**With Docker**: PostgreSQL is automatically configured and used. The database connection is set up via environment variables in `docker-compose.yml`.

**Local Development**: By default, the bot uses SQLite. To use PostgreSQL locally, update `DATABASE_URL` in `.env`:

```
DATABASE_URL=postgresql://user:password@localhost/omega_classroom
```

Or set individual components:
```
USE_POSTGRESQL=true
DB_HOST=localhost
DB_PORT=5432
DB_NAME=omega_classroom
DB_USER=postgres
DB_PASSWORD=postgres
```

### Notifications

- `NOTIFICATION_CHECK_INTERVAL`: How often the bot checks for notifications (default: 3600 seconds = 1 hour)
- `DEADLINE_WARNING_HOURS`: Hours before deadline to send warning (default: 24 hours)

## GitHub Integration

The bot integrates with GitHub Classroom API to:
- Retrieve repository information
- Check student commit activity
- Verify submission status
- Monitor repository updates

Make sure your GitHub token has the following permissions:
- `repo` (full control of private repositories)
- `read:org` (read organization membership - optional)

