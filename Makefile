.PHONY: help build up down restart logs init-db shell clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build Docker images
	docker compose build

up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

logs: ## Show logs from all services
	docker compose logs -f

logs-bot: ## Show logs from bot service
	docker compose logs -f bot

logs-db: ## Show logs from database service
	docker compose logs -f db

init-db: ## Initialize database
	docker compose exec bot python -m app.setup_db

shell: ## Open shell in bot container
	docker compose exec bot /bin/bash

shell-db: ## Open PostgreSQL shell
	docker compose exec db psql -U postgres -d omega_classroom

clean: ## Remove containers, volumes, and images
	docker compose down -v --rmi all

rebuild: ## Rebuild and restart services
	docker compose down
	docker compose build --no-cache
	docker compose up -d
	@echo "Waiting for database to be ready..."
	sleep 5
	make init-db

