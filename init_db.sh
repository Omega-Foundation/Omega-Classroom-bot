#!/bin/bash
# Initialize database in Docker container

echo "Waiting for database to be ready..."
sleep 5

echo "Initializing database..."
docker compose exec bot python -m app.setup_db

echo "Database initialized successfully!"

