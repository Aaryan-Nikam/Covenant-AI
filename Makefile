.PHONY: up down logs test lint clean db-shell redis-shell

# --------------------------------------------------------------------------
# Development Environment
# --------------------------------------------------------------------------

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

rebuild:
	docker compose up -d --build

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

db-shell:
	docker compose exec db psql -U ironpass -d ironpass

redis-shell:
	docker compose exec redis redis-cli

# --------------------------------------------------------------------------
# Testing
# --------------------------------------------------------------------------

test:
	cd engine && python -m pytest tests/ -v

test-unit:
	cd engine && python -m pytest tests/unit/ -v

test-integration:
	cd engine && python -m pytest tests/integration/ -v

# --------------------------------------------------------------------------
# Code Quality
# --------------------------------------------------------------------------

lint:
	cd engine && python -m ruff check .

format:
	cd engine && python -m ruff format .

# --------------------------------------------------------------------------
# Cleanup
# --------------------------------------------------------------------------

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
