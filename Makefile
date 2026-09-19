.PHONY: up down logs test lint typecheck seed e2e format

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	cd apps/api && python -m pytest
	cd apps/web && npm test

lint:
	cd apps/api && python -m ruff check . && python -m mypy src
	cd apps/web && npm run lint && npm run typecheck

format:
	cd apps/api && python -m ruff format .
	cd apps/web && npm run format:write

seed:
	cd apps/api && python -m macenplast.db.seed

e2e:
	cd apps/web && npx playwright test
